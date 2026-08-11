
CREATE TABLE sensory_reading (
    location_id      INTEGER NOT NULL,       -- which sensor
    window_end       DATETIME NOT NULL,      -- which hour, UTC
    pedestrian_count INTEGER,

    sensory_status   varchar(20) NOT NULL
        CHECK (sensory_status IN ('Low', 'High', 'No Data')),

    -- Nullable alone would still allow the two nonsense rows: a 'No Data' row
    -- carrying a count, and a 'Low'/'High' row carrying none. Tie them
    -- together so the database refuses both.
    --
    -- Safe against MySQL's UNKNOWN-is-satisfied rule for CHECK constraints:
    -- IS NULL / IS NOT NULL always return TRUE or FALSE, and sensory_status
    -- is NOT NULL, so this expression can never evaluate to UNKNOWN and let a
    -- bad row through.
    CONSTRAINT chk_count_matches_status CHECK (
        (sensory_status = 'No Data' AND pedestrian_count IS NULL)
        OR (sensory_status IN ('Low', 'High') AND pedestrian_count IS NOT NULL)
    ),

    -- Re-running a scoring job over a window already covered overwrites
    -- rather than duplicates, the same way pedestrian_count_minute is keyed.
    PRIMARY KEY (location_id, window_end)
);
