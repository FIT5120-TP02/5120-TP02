CREATE TABLE sensory_reading (
    location_id INTEGER NOT NULL,
    window_end DATETIME NOT NULL,
    pedestrian_count INTEGER,
    sensory_status VARCHAR(20) NOT NULL
        CHECK (sensory_status IN ('Low', 'High', 'No Data')),
    PRIMARY KEY (location_id, window_end)
);
