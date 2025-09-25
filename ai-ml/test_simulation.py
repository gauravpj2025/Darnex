
#!/usr/bin/env python3
"""
Test script for the enhanced railway simulation.
This script demonstrates how to run and analyze the simulation results.
"""

import sys
import os
from datetime import datetime
import json

def create_sample_data():
    """Creates sample data files for testing if they don't exist."""

    # Create sample tracks.csv if it doesn't exist
    if not os.path.exists('tracks.csv'):
        import pandas as pd
        import random

        print("📁 Creating sample tracks.csv for testing...")

        # Generate sample track data
        stations = list(range(1, 21))  # 20 stations
        tracks = []

        for i in stations:
            for j in stations:
                if i != j and random.random() < 0.3:  # 30% connectivity
                    distance = random.randint(25000, 150000)  # 25-150 km in meters
                    tracks.append({
                        'station_from': i,
                        'station_to': j,
                        'length_m': distance,
                        'track_type': random.choice(['main', 'branch', 'high_speed'])
                    })

        tracks_df = pd.DataFrame(tracks)
        tracks_df.to_csv('tracks.csv', index=False)
        print(f"   ✅ Created tracks.csv with {len(tracks)} track segments")

def create_sample_models():
    """Creates dummy model files for testing if they don't exist."""

    import joblib
    import pickle
    import networkx as nx
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    import pandas as pd
    import numpy as np

    # Create models directory
    os.makedirs('models', exist_ok=True)

    # Create sample decision maker model
    if not os.path.exists('models/decision_maker.pkl'):
        print("🤖 Creating sample decision_maker.pkl for testing...")

        # Generate sample training data
        np.random.seed(42)
        n_samples = 1000

        data = []
        for _ in range(n_samples):
            train_type = np.random.choice(['high-speed', 'express', 'passenger', 'local', 'freight'])
            weather = np.random.choice(['Clear', 'Rain', 'Fog', 'Snow'])
            delay_minutes = np.random.uniform(0, 30)
            current_speed = np.random.uniform(0, 320)
            priority = np.random.randint(1, 6)
            disruption_impact = np.random.uniform(0, 1)

            # Simple decision logic for sample model
            if disruption_impact > 0.7:
                decision = 'reroute'
            elif delay_minutes > 20 or disruption_impact > 0.3:
                decision = 'hold'
            else:
                decision = 'proceed'

            data.append({
                'train_type': train_type,
                'weather': weather, 
                'delay_minutes': delay_minutes,
                'current_speed': current_speed,
                'priority': priority,
                'disruption_impact': disruption_impact,
                'decision': decision
            })

        df = pd.DataFrame(data)

        # Prepare features and target
        X = pd.get_dummies(df.drop('decision', axis=1), columns=['train_type', 'weather'])
        y = df['decision']

        # Train model
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        # Save model
        joblib.dump(model, 'models/decision_maker.pkl')
        print("   ✅ Created decision_maker.pkl")

    # Create sample delay predictor model  
    if not os.path.exists('models/delay_predictor.pkl'):
        print("🤖 Creating sample delay_predictor.pkl for testing...")

        # Generate sample training data for delay prediction
        data = []
        for _ in range(1000):
            train_type = np.random.choice(['high-speed', 'express', 'passenger', 'local', 'freight'])
            current_speed = np.random.uniform(0, 320)
            distance_remaining = np.random.uniform(0, 150)
            priority = np.random.randint(1, 6)
            current_delay = np.random.uniform(0, 20)

            # Simple delay prediction logic
            predicted_delay = (
                current_delay * 0.5 + 
                (150 - current_speed) * 0.1 + 
                distance_remaining * 0.05 + 
                priority * 2 +
                np.random.normal(0, 3)
            )
            predicted_delay = max(0, predicted_delay)

            data.append({
                'train_type': train_type,
                'current_speed': current_speed,
                'distance_remaining': distance_remaining,
                'priority': priority,
                'current_delay': current_delay,
                'predicted_delay': predicted_delay
            })

        df = pd.DataFrame(data)

        # Prepare features and target
        X = pd.get_dummies(df.drop('predicted_delay', axis=1), columns=['train_type'])
        y = df['predicted_delay']

        # Train model
        model = RandomForestRegressor(n_estimators=50, random_state=42)
        model.fit(X, y)

        # Save model
        joblib.dump(model, 'models/delay_predictor.pkl')
        print("   ✅ Created delay_predictor.pkl")

    # Create sample railway graph
    if not os.path.exists('models/railway_graph.gpickle'):
        print("🗺️  Creating sample railway_graph.gpickle for testing...")

        # Create a sample railway network graph
        G = nx.Graph()

        # Add stations (nodes)
        stations = list(range(1, 21))  # 20 stations
        G.add_nodes_from(stations)

        # Add tracks (edges) - create a connected network
        edges = []

        # Create a base connected network (ring topology)
        for i in range(len(stations)):
            next_station = stations[(i + 1) % len(stations)]
            edges.append((stations[i], next_station))

        # Add some additional random connections
        import random
        random.seed(42)
        for i in stations:
            for j in stations:
                if i < j and random.random() < 0.15:  # 15% chance of direct connection
                    edges.append((i, j))

        G.add_edges_from(edges)

        # Save graph
        with open('models/railway_graph.gpickle', 'wb') as f:
            pickle.dump(G, f)

        print(f"   ✅ Created railway_graph.gpickle with {len(G.nodes())} stations and {len(G.edges())} tracks")

def run_simulation():
    """Runs the enhanced simulation."""

    print("\n🚄 RUNNING ENHANCED RAILWAY SIMULATION TEST")
    print("="*60)

    try:
        # Import and run the enhanced simulation
        import enhanced_simulation
        print("\n✅ Simulation completed successfully!")

    except ImportError as e:
        print(f"❌ Could not import enhanced_simulation.py: {e}")
        print("   Make sure enhanced_simulation.py is in the current directory")

    except Exception as e:
        print(f"❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()

def analyze_results():
    """Provides guidance on analyzing simulation results."""

    print("\n📊 SIMULATION ANALYSIS GUIDE")
    print("="*60)
    print("\n🔍 Key Metrics to Analyze:")
    print("   • Total delay minutes across all trains")
    print("   • Percentage of completed journeys")
    print("   • AI decision effectiveness (holds vs reroutes)")
    print("   • Disruption impact on different train types")
    print("   • Weather effect on network performance")

    print("\n📈 Performance Indicators:")
    print("   • Low average delay per train (<5 minutes = excellent)")
    print("   • High completion rate (>80% = good)")
    print("   • Appropriate AI responses to disruptions")
    print("   • Efficient use of holds vs reroutes")

    print("\n🎯 Testing Scenarios to Try:")
    print("   • Run multiple simulations to test consistency")
    print("   • Modify disruption probabilities to stress-test")
    print("   • Compare performance with different train mixes")
    print("   • Test weather impact by forcing severe weather")

if __name__ == "__main__":
    print("🧪 ENHANCED RAILWAY SIMULATION TEST RUNNER")
    print("="*60)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create sample data if needed
    print("\n1️⃣  Setting up test environment...")
    create_sample_data()
    create_sample_models()

    # Run the simulation
    print("\n2️⃣  Running simulation...")
    run_simulation()

    # Provide analysis guidance
    analyze_results()

    print("\n✅ Test run completed!")
    print("="*60)
