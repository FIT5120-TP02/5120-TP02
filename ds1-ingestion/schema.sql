-- database schema for onboarding module

CREATE TABLE location (
    location_id INTEGER PRIMARY KEY,
    location_name   varchar(255) NOT NULL,    -- such as "Parliament Railway Station"
    latitude FLOAT not null,
    longitude FLOAT not null,
    address  varchar(255),       -- street address
    location_type varchar(50) not null,  -- 'sensor', 'refuge', or 'place'
    category varchar(100),  -- refuge category, such as 'park' 'library'. other not refuge is NULL
    placement varchar(50)  -- 'indoor' or 'outdoor', only for location_type='sensor', other is NULL
);


CREATE TABLE pedestrian_count_minute (
    location_id INTEGER NOT NULL,
    sensing_datetime DATETIME NOT NULL, -- "2026-08-03T14:18:00+00:00"
    sensing_date DATE NOT NULL, -- "2026-08-03"
    sensing_time TIME NOT NULL, -- "14:18"
    direction_1 INTEGER,
    direction_2 INTEGER,
    total_of_directions INTEGER,
    PRIMARY KEY (location_id, sensing_datetime)
);





CREATE TABLE pedestrian_count_hour (
    id BIGINT NOT NULL,   -- source id: location+hour+date concatenated, 12 digits
    location_id INTEGER NOT NULL,
    sensing_date DATE NOT NULL, -- "2026-08-03"
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    hourday INTEGER NOT NULL CHECK (hourday BETWEEN 0 AND 23),
    direction_1 INTEGER,
    direction_2 INTEGER,
    pedestrian_count INTEGER,
    PRIMARY KEY (location_id, sensing_date, hourday)
);
CREATE INDEX idx_pedestrian_count_hour
ON pedestrian_count_hour (location_id, day_of_week, hourday);


-- table of baseline values for each location, day of week, and hour of day.
CREATE TABLE baseline (
    location_id  INTEGER NOT NULL,
    day_of_week  INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    hourday INTEGER NOT NULL CHECK (hourday BETWEEN 0 AND 23),
    average_count DOUBLE NOT NULL,
    median_count DOUBLE NOT NULL,
    observation_count INTEGER NOT NULL,
    recomputed_at  datetime NOT NULL,
    PRIMARY KEY (location_id, day_of_week, hourday)
);


CREATE TABLE config (
    config_key  varchar(255) PRIMARY KEY, -- which config value, such as "threshold_multiplier"
    value varchar(255) NOT NULL,  -- the value of the config, such as "1.5"
    updated_at datetime NOT NULL, -- when the value was last updated
    note varchar(255)  -- how to compute the value, or other notes about it
);
