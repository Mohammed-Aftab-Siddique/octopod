-- Employees choose the first of two consecutive week-off days.
--
-- ISO weekdays are used (0 = Monday … 6 = Sunday), matching Python's
-- ``date.weekday()``. Existing employees keep their staggered pattern by
-- deriving the start day from their rotation offset. The old weekly_off_days
-- column is no longer used by the application.
ALTER TABLE employees
    ADD COLUMN week_off_start_day INTEGER NOT NULL DEFAULT 0
    CHECK (week_off_start_day >= 0 AND week_off_start_day <= 6);

UPDATE employees SET week_off_start_day = rotation_offset % 7;

-- Week-offs now come from the employee configuration, not availability.
-- Preserve historic entries as an unavailable day rather than dropping them.
UPDATE availability SET kind = 'unavailable' WHERE kind = 'week_off';
