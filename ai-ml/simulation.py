
import pandas as pd
import joblib
import pickle
import networkx as nx
from datetime import datetime, timedelta
import time
import random
import json
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import os

# --- CONFIGURATION ---
SIMULATION_TICKS = 120         # How many minutes the simulation will run for
SECONDS_PER_TICK = 0.3        # How fast the simulation runs in real-time (lower is faster)
MIN_TRAINS = 20               # Minimum number of trains in simulation
MAX_TRAINS = 30               # Maximum number of trains in simulation

# Train type configurations with realistic speeds and priorities
TRAIN_TYPES = {
    'high-speed': {'base_speed_kmph': 320, 'priority': 1, 'color': '🚄'},
    'express': {'base_speed_kmph': 160, 'priority': 2, 'color': '🚆'},
    'passenger': {'base_speed_kmph': 120, 'priority': 3, 'color': '🚉'},
    'local': {'base_speed_kmph': 80, 'priority': 4, 'color': '🚂'},
    'freight': {'base_speed_kmph': 60, 'priority': 5, 'color': '🚛'}
}

# Weather impact multipliers for train speeds
WEATHER_EFFECTS = {
    'Clear': 1.0,
    'Light_Rain': 0.95,
    'Rain': 0.85,
    'Heavy_Rain': 0.7,
    'Fog': 0.6,
    'Snow': 0.5,
    'Storm': 0.3
}

class DisruptionType(Enum):
    TRACK_BLOCKAGE = "track_blockage"
    STATION_CONGESTION = "station_congestion" 
    SIGNAL_FAILURE = "signal_failure"
    WEATHER_EVENT = "weather_event"

@dataclass
class Disruption:
    disruption_type: DisruptionType
    location: str  # Station ID or Track ID
    start_tick: int
    duration_ticks: int
    severity: float  # 0.0 to 1.0
    description: str

# --- 1. ENHANCED ASSET LOADING ---
def load_assets():
    """Loads all the trained models and the railway graph from disk."""
    try:
        decision_maker = joblib.load('models/decision_maker.pkl')
        delay_predictor = joblib.load('models/delay_predictor.pkl')
        with open('models/railway_graph.gpickle', 'rb') as f:
            railway_graph = pickle.load(f)
        print("✅ Models and railway graph loaded successfully.")
        return decision_maker, delay_predictor, railway_graph
    except FileNotFoundError as e:
        print(f"🚨 Error: Could not find a model file. {e}")
        print("Please make sure you have run 'model.py' successfully first.")
        exit()

def load_track_distances():
    """Loads real track distances from the database."""
    track_distances = {}
    try:
        # Try to load from CSV files first
        if os.path.exists('tracks.csv'):
            tracks_df = pd.read_csv('tracks.csv')
            for _, row in tracks_df.iterrows():
                if 'station_from' in row and 'station_to' in row and 'length_m' in row:
                    track_key = f"{row['station_from']}-{row['station_to']}"
                    track_distances[track_key] = row['length_m'] / 1000.0  # Convert to km
                    # Add reverse direction
                    reverse_key = f"{row['station_to']}-{row['station_from']}"
                    track_distances[reverse_key] = row['length_m'] / 1000.0
            print(f"✅ Loaded {len(track_distances)} track distances from tracks.csv")
        else:
            print("⚠️  tracks.csv not found, using default distances")
            # Default distances for fallback
            for i in range(1, 21):
                for j in range(i+1, 21):
                    distance = random.uniform(25, 150)  # 25-150 km realistic range
                    track_distances[f"{i}-{j}"] = distance
                    track_distances[f"{j}-{i}"] = distance
    except Exception as e:
        print(f"⚠️  Could not load track distances: {e}")
        # Fallback to default distances
        for i in range(1, 21):
            for j in range(i+1, 21):
                distance = random.uniform(25, 150)
                track_distances[f"{i}-{j}"] = distance
                track_distances[f"{j}-{i}"] = distance

    return track_distances

# --- 2. ENHANCED TRAIN OBJECT ---
class Train:
    """An enhanced train class with realistic behaviors and states."""

    def __init__(self, train_id: int, name: str, train_type: str, priority: int, route: List[int], track_distances: Dict[str, float]):
        self.id = train_id
        self.name = name
        self.type = train_type
        self.priority = priority
        self.route = route
        self.track_distances = track_distances
        self.route_index = 0

        # Set initial state randomly for variety
        if random.choice([True, False]):
            # Start AT_STATION
            self.current_station = route[0]
            self.next_station = route[1] if len(route) > 1 else None
            self.status = "AT_STATION"
            self.distance_to_next_station = self._get_track_distance(self.current_station, self.next_station)
            self.distance_covered = 0
        else:
            # Start IN_TRANSIT
            self.route_index = random.randint(0, len(route) - 2)
            self.current_station = route[self.route_index]
            self.next_station = route[self.route_index + 1]
            self.status = "IN_TRANSIT"
            self.distance_to_next_station = self._get_track_distance(self.current_station, self.next_station)
            self.distance_covered = random.uniform(0, self.distance_to_next_station * 0.8)

        # Speed and operational parameters
        self.base_speed_kmph = TRAIN_TYPES[train_type]['base_speed_kmph']
        self.current_speed_kmph = 0
        self.max_speed_kmph = self.base_speed_kmph

        # AI and delay tracking
        self.current_delay_minutes = 0
        self.total_delay_minutes = 0
        self.last_ai_decision = None
        self.wait_ticks_remaining = 0

        # Status tracking
        self.holds_applied = 0
        self.reroutes_applied = 0

    def _get_track_distance(self, from_station: int, to_station: int) -> float:
        """Gets the real track distance between two stations."""
        if from_station is None or to_station is None:
            return 0

        track_key = f"{from_station}-{to_station}"
        return self.track_distances.get(track_key, 100.0)  # Default 100km if not found

    def apply_weather_effects(self, weather: str):
        """Applies weather effects to train speed."""
        weather_multiplier = WEATHER_EFFECTS.get(weather, 1.0)
        self.max_speed_kmph = self.base_speed_kmph * weather_multiplier

    def depart(self):
        """Enhanced departure logic with realistic acceleration."""
        if self.next_station is None:
            return False

        self.status = "IN_TRANSIT"
        self.current_speed_kmph = min(self.max_speed_kmph, 80)  # Start at moderate speed
        print(f"    🚀 {TRAIN_TYPES[self.type]['color']} {self.name} departing from Station {self.current_station} → Station {self.next_station}")
        return True

    def move(self, time_delta_hours: float):
        """Enhanced movement with realistic physics."""
        if self.status == "IN_TRANSIT" and self.wait_ticks_remaining <= 0:
            # Gradual speed increase to simulate acceleration
            if self.current_speed_kmph < self.max_speed_kmph:
                acceleration = min(20, self.max_speed_kmph - self.current_speed_kmph)  # 20 km/h per tick max acceleration
                self.current_speed_kmph = min(self.max_speed_kmph, self.current_speed_kmph + acceleration)

            distance_moved = self.current_speed_kmph * time_delta_hours
            self.distance_covered += distance_moved

            # Check for arrival with gradual deceleration
            distance_remaining = self.distance_to_next_station - self.distance_covered
            if distance_remaining <= 10:  # Start decelerating 10km before station
                deceleration_factor = max(0.3, distance_remaining / 10)
                self.current_speed_kmph *= deceleration_factor

            if self.distance_covered >= self.distance_to_next_station:
                self.arrive()
        elif self.wait_ticks_remaining > 0:
            self.wait_ticks_remaining -= 1
            self.current_delay_minutes += 1

    def arrive(self):
        """Enhanced arrival logic."""
        self.status = "AT_STATION"
        self.current_speed_kmph = 0
        self.distance_covered = 0
        self.route_index += 1

        if self.route_index >= len(self.route) - 1:
            self.current_station = self.route[self.route_index]
            self.next_station = None
            print(f"    🏁 {TRAIN_TYPES[self.type]['color']} {self.name} reached final destination: Station {self.current_station}")
        else:
            self.current_station = self.route[self.route_index]
            self.next_station = self.route[self.route_index + 1]
            self.distance_to_next_station = self._get_track_distance(self.current_station, self.next_station)
            print(f"    📍 {TRAIN_TYPES[self.type]['color']} {self.name} arrived at Station {self.current_station}")

    def apply_hold(self, duration_ticks: int, reason: str):
        """Apply a hold to the train."""
        self.wait_ticks_remaining = duration_ticks
        self.holds_applied += 1
        self.status = "HOLD"
        print(f"    ⏸️  {TRAIN_TYPES[self.type]['color']} {self.name} HELD for {duration_ticks} ticks - {reason}")

# --- 3. ENHANCED AI AND SIMULATION LOGIC ---

def get_delay_prediction(train, delay_predictor):
    """Uses the delay predictor model to estimate potential delays."""
    try:
        # Create input for delay predictor
        delay_input = pd.DataFrame([{
            'train_type': train.type,
            'current_speed': train.current_speed_kmph,
            'distance_remaining': train.distance_to_next_station - train.distance_covered if train.status == "IN_TRANSIT" else train.distance_to_next_station,
            'priority': train.priority,
            'current_delay': train.current_delay_minutes
        }])

        # Handle categorical encoding
        delay_input_encoded = pd.get_dummies(delay_input, columns=['train_type'])

        # Align columns with model
        model_columns = delay_predictor.feature_names_in_
        for col in model_columns:
            if col not in delay_input_encoded.columns:
                delay_input_encoded[col] = 0

        delay_input_encoded = delay_input_encoded[model_columns]
        predicted_delay = delay_predictor.predict(delay_input_encoded)[0]
        return max(0, predicted_delay)  # Ensure non-negative delay

    except Exception as e:
        print(f"    ⚠️  Delay prediction failed: {e}")
        return random.uniform(0, 15)  # Fallback to random delay

def get_ai_decision(train, decision_model, delay_predictor, weather: str, disruptions: List[Disruption]):
    """Enhanced AI decision making with delay prediction integration."""

    # First get delay prediction
    predicted_delay = get_delay_prediction(train, delay_predictor)

    # Check for disruptions affecting this train
    disruption_impact = 0
    for disruption in disruptions:
        if disruption.disruption_type == DisruptionType.STATION_CONGESTION:
            if disruption.location == str(train.next_station):
                disruption_impact = disruption.severity
        elif disruption.disruption_type == DisruptionType.TRACK_BLOCKAGE:
            # Check if train's route uses this track
            if disruption.location in [f"{train.current_station}-{train.next_station}", 
                                     f"{train.next_station}-{train.current_station}"]:
                disruption_impact = disruption.severity

    # Create decision model input
    decision_input = pd.DataFrame([{
        'train_type': train.type,
        'delay_minutes': predicted_delay,
        'current_speed': train.current_speed_kmph,
        'weather': weather,
        'priority': train.priority,
        'disruption_impact': disruption_impact
    }])

    # Handle categorical encoding
    decision_input_encoded = pd.get_dummies(decision_input, columns=['train_type', 'weather'])

    # Align columns with model
    try:
        model_columns = decision_model.feature_names_in_
        for col in model_columns:
            if col not in decision_input_encoded.columns:
                decision_input_encoded[col] = 0

        decision_input_encoded = decision_input_encoded[model_columns]
        decision = decision_model.predict(decision_input_encoded)[0]
    except Exception as e:
        print(f"    ⚠️  AI decision failed: {e}")
        # Fallback logic based on disruption impact
        if disruption_impact > 0.7:
            decision = 'reroute'
        elif disruption_impact > 0.3:
            decision = 'hold'
        else:
            decision = 'proceed'

    train.last_ai_decision = decision
    return decision

def reroute_train(train, graph, disruptions: List[Disruption]):
    """Enhanced rerouting with multiple disruption handling."""
    try:
        temp_graph = graph.copy()

        # Remove all disrupted nodes/edges
        for disruption in disruptions:
            if disruption.disruption_type == DisruptionType.STATION_CONGESTION:
                if disruption.location in temp_graph.nodes:
                    temp_graph.remove_node(int(disruption.location))
            elif disruption.disruption_type == DisruptionType.TRACK_BLOCKAGE:
                # Remove edge if it exists
                parts = disruption.location.split('-')
                if len(parts) == 2:
                    try:
                        if temp_graph.has_edge(int(parts[0]), int(parts[1])):
                            temp_graph.remove_edge(int(parts[0]), int(parts[1]))
                    except:
                        pass

        new_path = nx.shortest_path(temp_graph,
                                   source=train.current_station,
                                   target=train.route[-1])

        print(f"    🔄 REROUTING: {train.name} new path: {' → '.join(map(str, new_path))}")
        train.route = new_path
        train.route_index = 0
        train.next_station = new_path[1] if len(new_path) > 1 else None
        train.distance_to_next_station = train._get_track_distance(train.current_station, train.next_station)
        train.distance_covered = 0
        train.reroutes_applied += 1

        return True

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        print(f"    ❌ REROUTING: No alternative path found for {train.name}. Applying hold.")
        train.apply_hold(random.randint(3, 8), "No alternative route available")
        return False

# --- 4. DISRUPTION MANAGEMENT SYSTEM ---

class DisruptionManager:
    """Manages dynamic disruptions throughout the simulation."""

    def __init__(self, railway_graph):
        self.graph = railway_graph
        self.active_disruptions: List[Disruption] = []
        self.disruption_history: List[Disruption] = []

    def generate_random_disruption(self, current_tick: int) -> Optional[Disruption]:
        """Generates random disruptions based on realistic probabilities."""

        # Disruption probabilities per tick (realistic values)
        disruption_chances = {
            DisruptionType.TRACK_BLOCKAGE: 0.008,      # ~1% chance per simulation
            DisruptionType.STATION_CONGESTION: 0.012,  # ~1.4% chance per simulation
            DisruptionType.SIGNAL_FAILURE: 0.006,      # ~0.7% chance per simulation
            DisruptionType.WEATHER_EVENT: 0.004        # ~0.5% chance per simulation
        }

        for disruption_type, probability in disruption_chances.items():
            if random.random() < probability:
                return self._create_disruption(disruption_type, current_tick)

        return None

    def _create_disruption(self, disruption_type: DisruptionType, current_tick: int) -> Disruption:
        """Creates a specific type of disruption."""

        if disruption_type == DisruptionType.TRACK_BLOCKAGE:
            # Select random track between stations
            nodes = list(self.graph.nodes())
            station1, station2 = random.sample(nodes, 2)
            location = f"{station1}-{station2}"
            duration = random.randint(8, 25)  # 8-25 minutes
            severity = random.uniform(0.8, 1.0)
            description = f"Track blocked between Station {station1} and Station {station2} - infrastructure failure"

        elif disruption_type == DisruptionType.STATION_CONGESTION:
            # Select random station
            location = str(random.choice(list(self.graph.nodes())))
            duration = random.randint(5, 15)  # 5-15 minutes
            severity = random.uniform(0.5, 0.9)
            description = f"Station {location} congested - no available platforms"

        elif disruption_type == DisruptionType.SIGNAL_FAILURE:
            # Signal failures affect tracks
            nodes = list(self.graph.nodes())
            station1, station2 = random.sample(nodes, 2)
            location = f"{station1}-{station2}"
            duration = random.randint(10, 30)  # 10-30 minutes
            severity = random.uniform(0.6, 0.95)
            description = f"Signal failure on track {station1}-{station2} - stuck on red"

        elif disruption_type == DisruptionType.WEATHER_EVENT:
            # Weather affects entire network
            location = "GLOBAL"
            duration = random.randint(15, 45)  # 15-45 minutes
            severity = random.uniform(0.3, 0.8)
            description = f"Severe weather event - reduced speed limits network-wide"

        return Disruption(
            disruption_type=disruption_type,
            location=location,
            start_tick=current_tick,
            duration_ticks=duration,
            severity=severity,
            description=description
        )

    def update_disruptions(self, current_tick: int):
        """Updates active disruptions and removes expired ones."""
        expired_disruptions = []

        for disruption in self.active_disruptions:
            if current_tick >= disruption.start_tick + disruption.duration_ticks:
                expired_disruptions.append(disruption)
                print(f"    ✅ RESOLVED: {disruption.description}")

        for expired in expired_disruptions:
            self.active_disruptions.remove(expired)
            self.disruption_history.append(expired)

    def add_disruption(self, disruption: Disruption):
        """Adds a new disruption."""
        self.active_disruptions.append(disruption)
        print(f"    🚨 NEW DISRUPTION: {disruption.description} (Duration: {disruption.duration_ticks} ticks)")

# --- 5. WEATHER SYSTEM ---

class WeatherSystem:
    """Manages dynamic weather changes."""

    def __init__(self):
        self.current_weather = 'Clear'
        self.weather_change_probability = 0.015  # 1.5% chance per tick
        self.weather_duration = 0

    def update_weather(self, current_tick: int) -> str:
        """Updates weather conditions."""

        if self.weather_duration > 0:
            self.weather_duration -= 1
        else:
            if random.random() < self.weather_change_probability:
                old_weather = self.current_weather
                weather_options = list(WEATHER_EFFECTS.keys())
                weather_weights = [0.4, 0.2, 0.15, 0.1, 0.08, 0.05, 0.02]  # Clear weather most common
                self.current_weather = random.choices(weather_options, weights=weather_weights)[0]
                self.weather_duration = random.randint(10, 30)  # Weather lasts 10-30 ticks

                if old_weather != self.current_weather:
                    print(f"    🌦️  WEATHER CHANGE: {old_weather} → {self.current_weather}")

        return self.current_weather

# --- 6. TRAIN GENERATOR ---

def generate_varied_trains(railway_graph, track_distances, min_trains=MIN_TRAINS, max_trains=MAX_TRAINS) -> List[Train]:
    """Generates a varied fleet of trains with realistic configurations."""

    num_trains = random.randint(min_trains, max_trains)
    trains = []
    nodes = list(railway_graph.nodes())

    # Define realistic train names and types
    train_names = {
        'high-speed': ['Velocity Express', 'Lightning Bolt', 'Speed Demon', 'Thunder Strike'],
        'express': ['Regional Express', 'City Connector', 'Metro Link', 'Urban Express'],
        'passenger': ['Morning Commuter', 'Evening Service', 'Local Passenger', 'City Service'],
        'local': ['Local Shuttle', 'Branch Line', 'Community Service', 'Rural Connection'],
        'freight': ['Cargo Hauler', 'Freight Express', 'Industrial Transport', 'Heavy Goods']
    }

    # Distribution of train types (realistic proportions)
    type_distribution = ['passenger'] * 8 + ['local'] * 5 + ['express'] * 4 + ['freight'] * 2 + ['high-speed'] * 1

    for i in range(num_trains):
        train_type = random.choice(type_distribution)

        # Generate route (3-8 stations)
        route_length = random.randint(3, min(8, len(nodes)))
        route = random.sample(nodes, route_length)

        # Ensure route connectivity
        if len(route) > 2:
            # Sort route to create a more realistic path
            route.sort()

        # Select train name
        available_names = train_names[train_type]
        name = f"{random.choice(available_names)} {i+1:03d}"

        priority = TRAIN_TYPES[train_type]['priority']

        train = Train(
            train_id=i+1,
            name=name,
            train_type=train_type,
            priority=priority,
            route=route,
            track_distances=track_distances
        )

        trains.append(train)

    return trains

# --- 7. ENHANCED LOGGING AND STATISTICS ---

def print_simulation_status(tick: int, total_ticks: int, trains: List[Train], weather: str, disruptions: List[Disruption]):
    """Provides comprehensive status logging."""

    # Header
    print(f"\n{'='*80}")
    print(f"🕐 TICK {tick+1:03d}/{total_ticks:03d} | ⛅ Weather: {weather} | 🚨 Active Disruptions: {len(disruptions)}")
    print(f"{'='*80}")

    # Active disruptions
    if disruptions:
        print("\n📢 ACTIVE DISRUPTIONS:")
        for disruption in disruptions:
            remaining = disruption.start_tick + disruption.duration_ticks - tick
            print(f"   ⚠️  {disruption.description} (Remaining: {remaining} ticks)")

    # Train status summary
    status_counts = {'AT_STATION': 0, 'IN_TRANSIT': 0, 'HOLD': 0, 'COMPLETED': 0}
    type_counts = {t: 0 for t in TRAIN_TYPES.keys()}

    print("\n🚂 TRAIN STATUS SUMMARY:")
    for train in trains:
        if train.next_station is None:
            status_counts['COMPLETED'] += 1
        else:
            status_counts[train.status] += 1
        type_counts[train.type] += 1

        # Individual train status
        if train.status == "IN_TRANSIT":
            progress = (train.distance_covered / train.distance_to_next_station) * 100
            print(f"   {TRAIN_TYPES[train.type]['color']} {train.name:20s} | "
                  f"📍 {train.current_station}→{train.next_station} | "
                  f"🏃 {train.current_speed_kmph:3.0f}km/h | "
                  f"📊 {progress:4.1f}% | "
                  f"⏰ {train.current_delay_minutes:2.0f}min delay")
        else:
            print(f"   {TRAIN_TYPES[train.type]['color']} {train.name:20s} | "
                  f"📍 Station {train.current_station:2d} | "
                  f"📋 {train.status:10s} | "
                  f"⏰ {train.current_delay_minutes:2.0f}min delay | "
                  f"🤖 {train.last_ai_decision or 'N/A':8s}")

    # Summary statistics
    print(f"\n📊 SUMMARY: "
          f"🚉 At Station: {status_counts['AT_STATION']:2d} | "
          f"🚄 In Transit: {status_counts['IN_TRANSIT']:2d} | "
          f"⏸️  On Hold: {status_counts['HOLD']:2d} | "
          f"🏁 Completed: {status_counts['COMPLETED']:2d}")

def print_final_statistics(trains: List[Train], disruption_history: List[Disruption]):
    """Prints comprehensive final simulation statistics."""

    print("\n" + "="*80)
    print("📈 FINAL SIMULATION STATISTICS")
    print("="*80)

    # Train performance metrics
    total_delay = sum(train.total_delay_minutes + train.current_delay_minutes for train in trains)
    completed_journeys = len([t for t in trains if t.next_station is None])
    total_holds = sum(train.holds_applied for train in trains)
    total_reroutes = sum(train.reroutes_applied for train in trains)

    print(f"\n🚂 TRAIN PERFORMANCE:")
    print(f"   📋 Total Trains: {len(trains)}")
    print(f"   🏁 Completed Journeys: {completed_journeys}")
    print(f"   ⏰ Total Delay Minutes: {total_delay:.1f}")
    print(f"   📊 Average Delay per Train: {total_delay/len(trains):.2f} min")
    print(f"   ⏸️  Total Holds Applied: {total_holds}")
    print(f"   🔄 Total Reroutes Applied: {total_reroutes}")

    # Disruption statistics
    print(f"\n🚨 DISRUPTION SUMMARY:")
    print(f"   📊 Total Disruptions: {len(disruption_history)}")

    disruption_types = {}
    for d in disruption_history:
        disruption_types[d.disruption_type.value] = disruption_types.get(d.disruption_type.value, 0) + 1

    for d_type, count in disruption_types.items():
        print(f"   🔹 {d_type.replace('_', ' ').title()}: {count}")

    # Train type performance
    print(f"\n📈 PERFORMANCE BY TRAIN TYPE:")
    for train_type in TRAIN_TYPES.keys():
        type_trains = [t for t in trains if t.type == train_type]
        if type_trains:
            avg_delay = sum(t.total_delay_minutes + t.current_delay_minutes for t in type_trains) / len(type_trains)
            completed = len([t for t in type_trains if t.next_station is None])
            print(f"   {TRAIN_TYPES[train_type]['color']} {train_type.title():12s}: "
                  f"{len(type_trains):2d} trains | "
                  f"{completed:2d} completed | "
                  f"Avg delay: {avg_delay:4.1f}min")

# --- 8. MAIN SIMULATION ---
if __name__ == "__main__":
    print("\n🚄 STARTING ENHANCED RAILWAY SIMULATION")
    print("="*80)

    # Load AI models and infrastructure
    decision_maker_model, delay_predictor_model, railway_graph = load_assets()
    track_distances = load_track_distances()

    # Initialize systems
    disruption_manager = DisruptionManager(railway_graph)
    weather_system = WeatherSystem()

    # Generate diverse train fleet
    trains = generate_varied_trains(railway_graph, track_distances)
    print(f"\n✅ Generated {len(trains)} trains with varied configurations")

    # Simulation state
    simulation_start_time = datetime(2025, 9, 24, 10, 0, 0)
    current_time = simulation_start_time

    print(f"\n🎯 Simulation Parameters:")
    print(f"   ⏱️  Duration: {SIMULATION_TICKS} ticks ({SIMULATION_TICKS} minutes)")
    print(f"   🏃 Speed: {SECONDS_PER_TICK}s per tick")
    print(f"   🚂 Trains: {len(trains)} ({', '.join(f'{sum(1 for t in trains if t.type == tt)} {tt}' for tt in TRAIN_TYPES.keys() if sum(1 for t in trains if t.type == tt) > 0)})")

    # Main simulation loop
    try:
        for tick in range(SIMULATION_TICKS):
            # Update weather
            current_weather = weather_system.update_weather(tick)

            # Apply weather effects to all trains
            for train in trains:
                train.apply_weather_effects(current_weather)

            # Generate and manage disruptions
            new_disruption = disruption_manager.generate_random_disruption(tick)
            if new_disruption:
                disruption_manager.add_disruption(new_disruption)

            disruption_manager.update_disruptions(tick)

            # Update each train
            for train in trains:
                if train.next_station is None:  # Journey complete
                    continue

                if train.status == "AT_STATION":
                    # Get AI decision
                    decision = get_ai_decision(
                        train, 
                        decision_maker_model, 
                        delay_predictor_model,
                        current_weather, 
                        disruption_manager.active_disruptions
                    )

                    # Execute AI decision
                    if decision == 'reroute':
                        reroute_train(train, railway_graph, disruption_manager.active_disruptions)
                    elif decision == 'hold':
                        train.apply_hold(random.randint(2, 6), "AI preventive hold")
                    elif decision == 'proceed' and train.next_station:
                        train.depart()

                elif train.status == "IN_TRANSIT":
                    train.move(time_delta_hours=1/60)  # 1 minute per tick

                elif train.status == "HOLD":
                    train.move(time_delta_hours=0)  # No movement while on hold
                    if train.wait_ticks_remaining <= 0:
                        train.status = "AT_STATION"  # Release from hold

            # Print status every 10 ticks for readability
            if tick % 10 == 0 or len(disruption_manager.active_disruptions) > 0:
                print_simulation_status(tick, SIMULATION_TICKS, trains, current_weather, disruption_manager.active_disruptions)

            # Advance simulation time
            current_time += timedelta(minutes=1)
            time.sleep(SECONDS_PER_TICK)

        # Final statistics
        print_final_statistics(trains, disruption_manager.disruption_history)
        print("\n✅ SIMULATION COMPLETED SUCCESSFULLY!")
        print("="*80)

    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user")
        print_final_statistics(trains, disruption_manager.disruption_history)
    except Exception as e:
        print(f"\n\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
