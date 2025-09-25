import pandas as pd
import numpy as np
from faker import Faker
from sqlalchemy import create_engine, text
import random
from datetime import datetime, timedelta

# --- CONFIGURATION ---
NUM_STATIONS = 50
NUM_TRAINS = 100
MOVEMENTS_PER_TRIP = 10

# --- DATABASE CONNECTION ---
DB_USER = 'postgres'
DB_PASS = 'pj925fhpp5' # Your password
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'railway_ai'

db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(db_url)
print("✅ SQLAlchemy engine created.")

# --- INITIALIZE FAKER ---
fake = Faker()

# --- DATA GENERATION ---
def generate_and_insert_data():
    # 1. GENERATE STATIONS
    print(f"🔄 Generating {NUM_STATIONS} stations...")
    stations_data = [{'code': ''.join(fake.unique.pystr(min_chars=3, max_chars=4).upper()),
                      'name': fake.city() + " " + random.choice(["Junction", "Central", "Station"]),
                      'lat': fake.latitude(), 'lon': fake.longitude()} for _ in range(NUM_STATIONS)]
    stations_df = pd.DataFrame(stations_data)
    stations_df.to_sql('stations', engine, if_exists='append', index=False)
    print("✅ Stations inserted.")

    # 2. GENERATE TRAINS
    print(f"🔄 Generating {NUM_TRAINS} trains...")
    trains_data = [{'train_no': str(fake.unique.random_number(digits=5, fix_len=True)),
                    'name': fake.word().capitalize() + " Express",
                    'type': random.choice(['express', 'freight', 'passenger']),
                    'priority': random.randint(1, 5),
                    'length_m': random.randint(200, 700)} for _ in range(NUM_TRAINS)]
    trains_df = pd.DataFrame(trains_data)
    trains_df.to_sql('trains', engine, if_exists='append', index=False)
    print("✅ Trains inserted.")

    # 3. RETRIEVE IDs FROM DB TO USE AS FOREIGN KEYS
    station_ids = pd.read_sql("SELECT id FROM stations", engine)['id'].tolist()
    train_ids = pd.read_sql("SELECT id FROM trains", engine)['id'].tolist()

    # 4. GENERATE TRACKS
    print(f"🔄 Generating tracks between stations...")
    tracks_data = []
    # Create a simple, connected network
    for i in range(len(station_ids) - 1):
        tracks_data.append({
            'from_station': station_ids[i],
            'to_station': station_ids[i+1],
            'length_m': random.randint(50000, 200000),
            'type': 'double-line',
            'allowed_speed': random.choice([100, 120, 140, 160])
        })
    tracks_df = pd.DataFrame(tracks_data)
    tracks_df.to_sql('tracks', engine, if_exists='append', index=False)
    print("✅ Tracks inserted.")

    # 5. GENERATE TIMETABLE AND MOVEMENTS
    print("🔄 Generating timetables and movements (this may take a moment)...")
    timetable_events_data = []
    train_movements_data = []
    
    for train_id in train_ids:
        num_stops = random.randint(3, 7)
        route_station_ids = random.sample(station_ids, num_stops)
        current_time = datetime.now() + timedelta(hours=random.randint(1, 24))
        
        for i in range(num_stops):
            # ... (Timetable and movement generation logic remains the same)
            station_id = route_station_ids[i]
            arrival_time = current_time if i > 0 else None
            stop_duration = timedelta(minutes=random.randint(2, 10))
            departure_time = current_time + stop_duration if i < num_stops - 1 else None
            
            timetable_events_data.append({'train_id': train_id, 'station_id': station_id,
                                          'scheduled_arrival': arrival_time, 'scheduled_departure': departure_time,
                                          'platform_no': str(random.randint(1, 8)), 'order_no': i + 1})
            
            if departure_time:
                next_station_id = route_station_ids[i+1]
                trip_duration_minutes = random.randint(30, 180)
                delay = timedelta(minutes=random.randint(0, 20) if random.random() > 0.7 else 0)
                actual_departure_time = departure_time + delay
                
                for _ in range(MOVEMENTS_PER_TRIP):
                    train_movements_data.append({'train_id': train_id, 'current_station': station_id, 'next_station': next_station_id,
                                                 'status': 'IN_TRANSIT', 'speed_kmph': random.randint(60, 120),
                                                 'position_m': random.uniform(1000, 90000), 'delayed_minutes': delay.total_seconds() / 60,
                                                 'actual_departure': actual_departure_time,
                                                 'eta': (arrival_time + timedelta(minutes=trip_duration_minutes) + delay) if arrival_time else None})
                current_time = departure_time + timedelta(minutes=trip_duration_minutes)

    pd.DataFrame(timetable_events_data).to_sql('timetable_events', engine, if_exists='append', index=False)
    print("✅ Timetable events inserted.")
    pd.DataFrame(train_movements_data).to_sql('train_movements', engine, if_exists='append', index=False)
    print("✅ Train movements inserted.")

# --- RUN THE SCRIPT ---
if __name__ == "__main__":
    with engine.connect() as connection:
        print("🗑️ Clearing old data...")
        connection.execute(text("TRUNCATE TABLE stations, trains, tracks, timetable_events, train_movements CASCADE;"))
        connection.commit()
        
    generate_and_insert_data()
    print("\n🎉 Massive data generation complete!")