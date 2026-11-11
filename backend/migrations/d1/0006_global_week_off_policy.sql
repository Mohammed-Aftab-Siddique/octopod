-- Week-off block length is now an organisation-wide policy.
--
-- Employees keep their automatically staggered start day in
-- employees.week_off_start_day, but administrators no longer edit it per
-- employee. The generator reads this setting to decide how many consecutive
-- days make up the weekly block.
CREATE TABLE app_settings (
    key VARCHAR(64) PRIMARY KEY,
    value VARCHAR(255) NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO app_settings (key, value)
VALUES ('consecutive_off_days', '2');
