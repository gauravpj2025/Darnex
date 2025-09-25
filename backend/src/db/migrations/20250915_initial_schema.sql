-- Initial Schema for Railway Simulation System

-- Table: stations
CREATE TABLE IF NOT EXISTS stations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    lat NUMERIC(10, 8),
    lon NUMERIC(11, 8),
    attributes JSONB
);

-- Table: platforms
CREATE TABLE IF NOT EXISTS platforms (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    platform_no VARCHAR(10) NOT NULL,
    length_m INTEGER,
    UNIQUE (station_id, platform_no)
);

-- Table: tracks (Corrected Version)
CREATE TABLE IF NOT EXISTS tracks (
    id SERIAL PRIMARY KEY,
    from_station INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    to_station INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    length_m INTEGER NOT NULL,
    type VARCHAR(50),
    allowed_speed INTEGER,
    UNIQUE (from_station, to_station) -- <-- ADD THIS LINE
);
-- Table: crossings
CREATE TABLE IF NOT EXISTS crossings (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    name VARCHAR(255),
    type VARCHAR(50),
    controlled BOOLEAN DEFAULT TRUE
);

-- Table: signals
-- This new table stores all the signals on the tracks.
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    signal_code VARCHAR(20) UNIQUE NOT NULL,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    location_m INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,
    type VARCHAR(50)
);

-- Table: trains
-- This is the CORRECT version
CREATE TABLE IF NOT EXISTS tracks (
    id SERIAL PRIMARY KEY,
    from_station INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    to_station INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE, -- <-- COMMA ADDED
    length_m INTEGER NOT NULL,
    type VARCHAR(50),
    allowed_speed INTEGER
);
-- Table: timetable_events
-- Updated to include delayed_minutes
CREATE TABLE IF NOT EXISTS timetable_events (
    id SERIAL PRIMARY KEY,
    train_id INTEGER NOT NULL REFERENCES trains(id) ON DELETE CASCADE,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    scheduled_arrival TIMESTAMP WITH TIME ZONE,
    scheduled_departure TIMESTAMP WITH TIME ZONE,
    delayed_minutes INTEGER,
    platform_no VARCHAR(10),
    order_no INTEGER NOT NULL
);

-- Table: train_movements
-- Updated to include delayed_minutes and actual arrival/departure times
CREATE TABLE IF NOT EXISTS train_movements (
    id SERIAL PRIMARY KEY,
    train_id INTEGER NOT NULL REFERENCES trains(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    current_station INTEGER REFERENCES stations(id),
    next_station INTEGER REFERENCES stations(id),
    status VARCHAR(50),
    speed_kmph NUMERIC(5, 2),
    position_m NUMERIC(10, 2),
    delayed_minutes INTEGER,
    actual_arrival TIMESTAMP WITH TIME ZONE,
    actual_departure TIMESTAMP WITH TIME ZONE,
    eta TIMESTAMP WITH TIME ZONE,
    etd TIMESTAMP WITH TIME ZONE
);