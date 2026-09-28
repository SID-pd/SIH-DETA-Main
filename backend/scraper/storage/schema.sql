-- ==============================================================================
-- DARPAN & SIH Train ETA Prediction Database Schema
-- Unified schema incorporating erail.in and CRIS NTES scraped telemetry
-- ==============================================================================

CREATE TABLE IF NOT EXISTS stations (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    state       TEXT,
    zone        TEXT,
    address     TEXT,
    lat         REAL,
    lon         REAL,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(name);
CREATE INDEX IF NOT EXISTS idx_stations_zone ON stations(zone);

CREATE TABLE IF NOT EXISTS trains (
    number          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT,
    from_code       TEXT,
    from_name       TEXT,
    to_code         TEXT,
    to_name         TEXT,
    departure       TEXT,
    arrival         TEXT,
    duration_min    INTEGER,
    distance_km     REAL,
    zone            TEXT,
    classes         TEXT,
    running_days    TEXT,       -- 7-char mask e.g. 1111111 or Mon,Tue...
    rake_type       TEXT,       -- LHB, ICF, TRAIN18 (Vande Bharat), etc.
    total_coaches   INTEGER,
    pantry_status   TEXT,
    return_train    TEXT,
    source          TEXT DEFAULT 'erail',
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_trains_name ON trains(name);
CREATE INDEX IF NOT EXISTS idx_trains_from ON trains(from_code);
CREATE INDEX IF NOT EXISTS idx_trains_to   ON trains(to_code);
CREATE INDEX IF NOT EXISTS idx_trains_type ON trains(type);

CREATE TABLE IF NOT EXISTS schedule_stops (
    train_number        TEXT NOT NULL,
    seq                 INTEGER NOT NULL,
    station_code        TEXT NOT NULL,
    station_name        TEXT,
    day                 INTEGER,
    arrival             TEXT,
    departure           TEXT,
    halt_mins           INTEGER DEFAULT 0,
    distance_km         REAL,
    platform            TEXT,
    speed_kmph          REAL,
    is_commercial_halt  INTEGER DEFAULT 1,
    source              TEXT DEFAULT 'erail',
    updated_at          TEXT,
    PRIMARY KEY (train_number, seq)
);
CREATE INDEX IF NOT EXISTS idx_sched_station ON schedule_stops(station_code);
CREATE INDEX IF NOT EXISTS idx_sched_train   ON schedule_stops(train_number);

CREATE TABLE IF NOT EXISTS coach_compositions (
    train_number    TEXT NOT NULL,
    position        INTEGER NOT NULL,
    coach_code      TEXT,       -- e.g. S1, B3, A1, GS
    coach_type      TEXT,       -- Sleeper, 3-Tier AC, Executive, etc.
    class_type      TEXT,       -- SL, 3A, 2A, 1A, CC, EC, 2S, GS
    rake_type       TEXT,       -- LHB / ICF
    updated_at      TEXT,
    PRIMARY KEY (train_number, position)
);
CREATE INDEX IF NOT EXISTS idx_coach_train ON coach_compositions(train_number);

CREATE TABLE IF NOT EXISTS historical_station_delays (
    train_number        TEXT NOT NULL,
    station_code        TEXT NOT NULL,
    avg_delay_mins      REAL,
    pct_on_time         REAL,
    pct_slight_delay    REAL,
    pct_moderate_delay  REAL,
    pct_severe_delay    REAL,
    sample_days         INTEGER,
    source              TEXT DEFAULT 'erail',
    scraped_at          TEXT,
    PRIMARY KEY (train_number, station_code)
);
CREATE INDEX IF NOT EXISTS idx_hist_delay_stn ON historical_station_delays(station_code);

CREATE TABLE IF NOT EXISTS train_exceptions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number            TEXT NOT NULL,
    journey_date            TEXT NOT NULL,
    exception_type          TEXT NOT NULL, -- RESCHEDULED, CANCELLED, DIVERTED
    original_departure      TEXT,
    rescheduled_departure   TEXT,
    delay_at_origin_mins    INTEGER DEFAULT 0,
    diverted_via            TEXT,
    reason                  TEXT,
    source                  TEXT DEFAULT 'ntes',
    recorded_at             TEXT
);
CREATE INDEX IF NOT EXISTS idx_ex_train_date ON train_exceptions(train_number, journey_date);
CREATE INDEX IF NOT EXISTS idx_ex_type ON train_exceptions(exception_type);

CREATE TABLE IF NOT EXISTS live_observations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    train_number        TEXT NOT NULL,
    journey_date        TEXT NOT NULL,
    station_code        TEXT NOT NULL,
    observed_at         TEXT NOT NULL,
    sched_arrival       TEXT,
    actual_arrival      TEXT,
    arrival_delay_mins  INTEGER,
    sched_departure     TEXT,
    actual_departure    TEXT,
    departure_delay_mins INTEGER,
    platform            TEXT,
    status              TEXT,
    current_location    TEXT,
    source              TEXT DEFAULT 'ntes',
    UNIQUE (train_number, journey_date, station_code, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_obs_train ON live_observations(train_number, journey_date);
CREATE INDEX IF NOT EXISTS idx_obs_station ON live_observations(station_code);

CREATE TABLE IF NOT EXISTS segments (
    from_code               TEXT NOT NULL,
    to_code                 TEXT NOT NULL,
    sched_minutes_p50       REAL,
    sched_minutes_min       REAL,
    distance_km             REAL,
    n_timetables            INTEGER DEFAULT 0,
    hist_delay_added_p50    REAL,
    hist_delay_added_p90    REAL,
    n_obs                   INTEGER DEFAULT 0,
    source                  TEXT DEFAULT 'schedule',
    PRIMARY KEY (from_code, to_code)
);
CREATE INDEX IF NOT EXISTS idx_seg_from ON segments(from_code);
