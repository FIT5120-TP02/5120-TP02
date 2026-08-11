CREATE TABLE sensory_reading (
    location_id      INTEGER NOT NULL,  
    window_end       DATETIME NOT NULL,
    pedestrian_count INTEGER NOT NULL,    
    sensory_status   varchar(20) NOT NULL   
        CHECK (sensory_status IN ('Low','High','No Data')),
    PRIMARY KEY (location_id, window_end)
);