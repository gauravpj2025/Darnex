-- Seed Data for Railway Simulation System (Idempotent)

-- Insert Stations
INSERT INTO stations (code, name, lat, lon, attributes) VALUES
('JP', 'Jaipur Junction', 26.9124, 75.7873, '{"city": "Jaipur", "state": "Rajasthan"}'),
('AII', 'Ajmer Junction', 26.4683, 74.6399, '{"city": "Ajmer", "state": "Rajasthan"}'),
('NDLS', 'New Delhi', 28.6436, 77.2222, '{"city": "Delhi", "state": "Delhi"}')
ON CONFLICT (code) DO NOTHING;

-- Insert Platforms for Jaipur
INSERT INTO platforms (station_id, platform_no, length_m) VALUES
((SELECT id FROM stations WHERE code = 'JP'), '1', 550),
((SELECT id FROM stations WHERE code = 'JP'), '2', 550),
((SELECT id FROM stations WHERE code = 'JP'), '3', 600),
((SELECT id FROM stations WHERE code = 'JP'), '4', 550),
((SELECT id FROM stations WHERE code = 'JP'), '5', 550),
((SELECT id FROM stations WHERE code = 'JP'), '6', 600),
((SELECT id FROM stations WHERE code = 'JP'), '7', 550),
((SELECT id FROM stations WHERE code = 'JP'), '8', 550)
ON CONFLICT (station_id, platform_no) DO NOTHING;

-- Insert Tracks (Corrected Version)
INSERT INTO tracks (from_station, to_station, length_m, type, allowed_speed) VALUES
((SELECT id FROM stations WHERE code = 'JP'), (SELECT id FROM stations WHERE code = 'AII'), 135000, 'double-line', 120),
((SELECT id FROM stations WHERE code = 'JP'), (SELECT id FROM stations WHERE code = 'NDLS'), 309000, 'double-line', 140)
ON CONFLICT (from_station, to_station) DO NOTHING; -- <-- SPECIFY THE COLUMNS HERE

-- Insert Trains
INSERT INTO trains (train_no, name, type, priority, length_m) VALUES
('12986', 'Ajmer Shatabdi Express', 'express', 1, 300),
('FRT7890', 'Freight Train 7890', 'freight', 5, 600)
ON CONFLICT (train_no) DO NOTHING;
-- Insert Timetable Events for Ajmer Shatabdi Express (Train No: 12986)
INSERT INTO timetable_events (train_id, station_id, scheduled_arrival, scheduled_departure, platform_no, order_no) VALUES
(
    (SELECT id FROM trains WHERE train_no = '12986'), 
    (SELECT id FROM stations WHERE code = 'NDLS'), 
    NULL, -- No arrival time at the starting station
    '2025-09-24 06:00:00+05:30', -- Departs New Delhi at 6:00 AM
    '1', 
    1
),
(
    (SELECT id FROM trains WHERE train_no = '12986'), 
    (SELECT id FROM stations WHERE code = 'JP'), 
    '2025-09-24 10:45:00+05:30', -- Arrives at Jaipur at 10:45 AM
    '2025-09-24 10:50:00+05:30', -- Departs Jaipur at 10:50 AM
    '2', 
    2
),
(
    (SELECT id FROM trains WHERE train_no = '12986'), 
    (SELECT id FROM stations WHERE code = 'AII'), 
    '2025-09-24 12:40:00+05:30', -- Arrives at Ajmer at 12:40 PM
    NULL, -- No departure from the final station
    '3', 
    3
)
ON CONFLICT (train_id, order_no) DO NOTHING;
-- Insert Crossings
-- Adds a level crossing near Jaipur station
INSERT INTO crossings (station_id, name, type, controlled) VALUES
(
    (SELECT id FROM stations WHERE code = 'JP'), 
    'Jaipur-Phulera Crossing', 
    'Level Crossing', 
    true
)
ON CONFLICT (id) DO NOTHING; -- Using a placeholder conflict target as no other unique constraint exists


-- Insert Signals
-- Adds signals on the track between Jaipur and Ajmer
INSERT INTO signals (signal_code, track_id, location_m, status, type) VALUES
(
    'JP_SIG_01',
    (SELECT id FROM tracks WHERE from_station = (SELECT id FROM stations WHERE code = 'JP') AND to_station = (SELECT id FROM stations WHERE code = 'AII')),
    500, -- 500m from the start of the track
    'GREEN',
    'Automatic'
),
(
    'JP_SIG_02',
    (SELECT id FROM tracks WHERE from_station = (SELECT id FROM stations WHERE code = 'JP') AND to_station = (SELECT id FROM stations WHERE code = 'AII')),
    50000, -- 50km from the start of the track
    'GREEN',
    'Automatic'
)
ON CONFLICT (signal_code) DO NOTHING;