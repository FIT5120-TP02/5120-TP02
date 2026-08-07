-- 002 store coordinates as DOUBLE, not FLOAT
--
-- FLOAT keeps about 7 significant digits, and a Melbourne coordinate needs 10:
-- 144.96515323 was being stored as 144.965, which is roughly 13 metres of error
-- in longitude. DS 3 matches sensors to a route inside a 120 metre buffer, so
-- that error is noise it should not have to carry.
--
-- This widens the column. It does NOT restore the digits already lost - those
-- were thrown away at insert time. Re-run the sync afterwards:
--     python ingesting.py sensors landmarks

ALTER TABLE location MODIFY latitude DOUBLE NOT NULL;
ALTER TABLE location MODIFY longitude DOUBLE NOT NULL;
