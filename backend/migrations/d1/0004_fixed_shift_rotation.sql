-- Fixed-shift rotation.
--
-- Employees now hold a primary shift for the whole roster period instead of
-- stepping through every shift each day. ``default_shift`` is nullable: when it
-- is empty the generator derives a balanced shift from ``rotation_offset``.
-- ``weekly_off_days`` controls how many consecutive days off an employee gets
-- each week; the starting weekday is staggered by ``rotation_offset``.
ALTER TABLE employees ADD COLUMN default_shift VARCHAR(8);
ALTER TABLE employees ADD COLUMN weekly_off_days INTEGER NOT NULL DEFAULT 2;
