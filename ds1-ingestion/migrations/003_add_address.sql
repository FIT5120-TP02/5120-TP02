-- 003 street addresses, so a typed address can become a coordinate
--
-- The user types "200 Collins Street". Routing needs (-37.81518, 144.96710).
-- This table is that translation, and it lives locally rather than behind an
-- external geocoding service because the search box suggests as you type: one
-- query per keystroke is fine against 63k local rows and impossible against a
-- rate-limited API.
--
-- Covers the whole City of Melbourne, not only the CBD - somebody's home
-- address is as likely to be in Carlton or Kensington as on Collins Street.

CREATE TABLE address (
    address_id  INTEGER PRIMARY KEY,        -- source gisid, unique across all 63,721
    address_pnt varchar(255) NOT NULL,      -- "200 Collins Street  Melbourne"
    street_no   varchar(20),                -- text, not a number: "61A" exists
    str_name    varchar(255),
    suburb      varchar(100),
    latitude    DOUBLE NOT NULL,
    longitude   DOUBLE NOT NULL
);

-- Serves "starts with what the user has typed so far". A word-order-independent
-- search ("collins 200") would need a FULLTEXT index instead; add it if the
-- interface ever asks for one.
CREATE INDEX idx_address_search ON address (address_pnt);
CREATE INDEX idx_address_street ON address (str_name, street_no);
