import pickle
import pandas as pd
import numpy as np
import joblib
import networkx as nx
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, accuracy_score
from sklearn.preprocessing import LabelEncoder
import psycopg2
import os
import warnings
import xgboost as xgb

# --- CONFIGURATION ---
DB_PARAMS = {
    'dbname': 'railway_ai',
    'user': 'postgres',
    'password': 'pj925fhpp5',  # your password
    'host': 'localhost',
    'port': 5432
}
MODELS_DIR = 'models'
os.makedirs(MODELS_DIR, exist_ok=True)

# --- DATABASE CONNECTION ---
try:
    conn = psycopg2.connect(**DB_PARAMS)
    print("Database connection successful.")
except psycopg2.OperationalError as e:
    print(f"Database connection failed: {e}")
    exit()

# Helper function to load data from SQL
def load_data(query, db_conn):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.read_sql_query(query, db_conn)

# --- DATA LOADING ---
train_movements = load_data("SELECT * FROM train_movements;", conn)
trains = load_data("SELECT * FROM trains;", conn)
tracks = load_data("SELECT * FROM tracks;", conn)
# CORRECTLY load timetable_events
timetable_events = load_data("SELECT * FROM timetable_events;", conn)

if train_movements.empty or trains.empty or timetable_events.empty:
    print("Error: One or more essential tables are empty. Please run generate_data.py.")
    exit()

# --- 1. PREPROCESSING AND FEATURE ENGINEERING ---
# Merge train movement with train info
df = train_movements.merge(trains, left_on='train_id', right_on='id', how='left', suffixes=('_move', '_train'))

# Merge timetable data onto the main dataframe
df = df.merge(timetable_events,
              left_on=['train_id', 'current_station'],
              right_on=['train_id', 'station_id'],
              how='left', suffixes=('_move', '_event'))

# Convert time columns to timezone-aware UTC
df['actual_arrival'] = pd.to_datetime(df['actual_arrival'], utc=True)
df['scheduled_arrival'] = pd.to_datetime(df['scheduled_arrival'], utc=True)

# Calculate delay
df['delay_minutes'] = (df['actual_arrival'] - df['scheduled_arrival']).dt.total_seconds() / 60.0
df['delay_minutes'].fillna(0, inplace=True)

# Time-based features
df['hour_of_day'] = df['actual_arrival'].dt.hour.fillna(0)
df['day_of_week'] = df['actual_arrival'].dt.dayofweek.fillna(0)
df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)

# Fill missing values for key columns before creating more features
df['speed_kmph'].fillna(df['speed_kmph'].mean(), inplace=True)
df['priority'].fillna(df['priority'].mean(), inplace=True)
df['type'].fillna('Unknown', inplace=True)

# Lag features
df = df.sort_values(by=['train_id', 'actual_arrival']).reset_index(drop=True)
df['previous_delay'] = df.groupby('train_id')['delay_minutes'].shift(1).fillna(0)
df['previous_speed'] = df.groupby('train_id')['speed_kmph'].shift(1).fillna(0)

# --- 2. TRAIN DELAY PREDICTOR MODEL ---
print("Training delay prediction model...")

feature_cols = ['speed_kmph', 'priority', 'hour_of_day', 'day_of_week', 'is_weekend',
                'previous_delay', 'previous_speed']
target_col = 'delay_minutes'

# Create a clean DataFrame for the model
model_df = df[feature_cols + [target_col]].copy()
model_df.fillna(0, inplace=True)

X_delay = model_df[feature_cols]
y_delay = model_df[target_col]

# Use TimeSeriesSplit for more robust validation
tscv = TimeSeriesSplit(n_splits=5)
train_idx, test_idx = list(tscv.split(X_delay))[-1]
X_train, X_test = X_delay.iloc[train_idx], X_delay.iloc[test_idx]
y_train, y_test = y_delay.iloc[train_idx], y_delay.iloc[test_idx]

# Train Random Forest
rf_regressor = RandomForestRegressor(n_estimators=100, n_jobs=-1, random_state=42)
rf_regressor.fit(X_train, y_train)
preds_rf = rf_regressor.predict(X_test)
mae_rf = mean_absolute_error(y_test, preds_rf)
print(f"Random Forest MAE: {mae_rf:.2f} minutes")
joblib.dump(rf_regressor, os.path.join(MODELS_DIR, 'delay_predictor.pkl'))

# Train XGBoost
xgb_model = xgb.XGBRegressor(objective='reg:squarederror', n_estimators=100, random_state=42)
xgb_model.fit(X_train, y_train)
preds_xgb = xgb_model.predict(X_test)
mae_xgb = mean_absolute_error(y_test, preds_xgb)
print(f"XGBoost MAE: {mae_xgb:.2f} minutes")
joblib.dump(xgb_model, os.path.join(MODELS_DIR, 'delay_xgb_model.pkl'))


# --- 3. BUILD AND SAVE ROUTE OPTIMIZATION GRAPH ---
print("Building and saving route optimization graph...")
G = nx.Graph()
for index, row in tracks.iterrows():
    G.add_edge(row['from_station'], row['to_station'], length=row['length_m'])

with open(os.path.join(MODELS_DIR, 'railway_graph.gpickle'), 'wb') as f:
    pickle.dump(G, f)

print("\nAll models trained and saved successfully.")

# --- ADD THIS ENTIRE BLOCK TO YOUR model.py FILE ---

# --- 4. TRAIN DECISION MAKING MODEL ---
print("Training decision making model...")

# First, create the features the model needs
df['disruption_impact'] = np.random.uniform(0, 1, size=len(df)) # Simulate a disruption score

# Create a more intelligent function to generate the decision labels
def generate_decision_label(row):
    """Generates realistic decision labels with a clear 'proceed' condition."""
    delay = row['delay_minutes']
    priority = row['priority']
    disruption = row['disruption_impact']

    # Rule 0: The "All Clear" rule. If there's no disruption and minimal delay, ALWAYS proceed.
    if disruption < 0.1 and delay < 5:
        return 'proceed'

    # Rule 1: High-priority trains should try to reroute for major disruptions
    if priority <= 2 and disruption > 0.7:
        return 'reroute'
    
    # Rule 2: If a track is fully blocked (max disruption), always try to reroute
    if disruption > 0.95:
        return 'reroute'

    # Rule 3: If delay is getting high and there's a moderate disruption, hold
    if delay > 30 and disruption > 0.4:
        return 'hold'
    
    # Rule 4: If already very delayed, hold to avoid causing more problems
    if delay > 60:
        return 'hold'
        
    # Rule 5: Default to proceed if no other rules match
    else:
        return 'proceed'

# Apply the function to create the labels
df['decision_label'] = df.apply(generate_decision_label, axis=1)

# Encode the text labels into numbers for the model
le_decision = LabelEncoder()
df['decision_enc'] = le_decision.fit_transform(df['decision_label'])

# Select the features for the decision model
decision_features = ['type', 'delay_minutes', 'speed_kmph', 'priority', 
                     'hour_of_day', 'day_of_week', 'disruption_impact']

# One-hot encode categorical features like 'type'
X_decision = pd.get_dummies(df[decision_features], columns=['type'], dummy_na=True)
y_decision = df['decision_enc']

# Fill any missing values
X_decision.fillna(0, inplace=True)

# Split the data for training and testing
X_decision_train, X_decision_test, y_decision_train, y_decision_test = train_test_split(
    X_decision, y_decision, test_size=0.2, shuffle=False) # shuffle=False is good for time-based data

# Train the classifier
decision_clf = RandomForestClassifier(n_estimators=100, n_jobs=-1, random_state=42)
decision_clf.fit(X_decision_train, y_decision_train)

# Evaluate the model's accuracy
pred_decision = decision_clf.predict(X_decision_test)
acc_decision = accuracy_score(y_decision_test, pred_decision)
print(f"Decision Model accuracy: {acc_decision:.2f}")

# Save the newly trained, smarter decision model
joblib.dump(decision_clf, os.path.join(MODELS_DIR, 'decision_maker.pkl'))
joblib.dump(le_decision, os.path.join(MODELS_DIR, 'label_encoder_decision.pkl')) # Save the encoder too!

# --- END OF THE BLOCK TO ADD ---
# Close the database connection
conn.close()