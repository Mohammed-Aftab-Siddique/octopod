-- Week-offs are a per-employee choice again: two consecutive days selected on
-- the employee form (for example Saturday–Sunday or Monday–Tuesday).
--
-- The organisation-wide consecutive-off-days setting no longer exists, so drop
-- the key/value policy table introduced in 0006. Existing employees already
-- have a valid week_off_start_day value from 0005.
DROP TABLE IF EXISTS app_settings;
