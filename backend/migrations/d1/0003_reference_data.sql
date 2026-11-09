-- Reference data. Both statements are idempotent so re-applying the migration
-- (or seeding staging) never duplicates rows.

INSERT INTO shift_statuses (code, label, color, text_color, is_working, sort_order)
VALUES
    ('G', 'General shift', '#E5E7EB', '#111827', 1, 1),
    ('M', 'Morning shift', '#BBF7D0', '#14532D', 1, 2),
    ('A', 'Afternoon shift', '#BFDBFE', '#1E3A8A', 1, 3),
    ('N', 'Night shift', '#FDE68A', '#78350F', 1, 4),
    ('L', 'Leave', '#FECACA', '#7F1D1D', 0, 5),
    ('CO', 'Compensatory off', '#FDBA74', '#7C2D12', 0, 6),
    ('O', 'Week-off / day-off', '#F3F4F6', '#374151', 0, 7),
    ('H', 'Holiday', '#DDD6FE', '#4C1D95', 0, 8)
ON CONFLICT (code) DO NOTHING;

-- Weekdays run 0 (Sunday) to 6 (Saturday). Weekends need one fewer person
-- per shift. A recursive CTE avoids the compound-SELECT term limit D1 enforces.
WITH RECURSIVE weekdays(weekday) AS (
    SELECT 0
    UNION ALL
    SELECT weekday + 1 FROM weekdays WHERE weekday < 6
)
INSERT INTO staffing_requirements (weekday, status_id, required_count)
SELECT
    w.weekday,
    s.id,
    CASE s.code
        WHEN 'G' THEN CASE WHEN w.weekday < 5 THEN 4 ELSE 3 END
        WHEN 'M' THEN CASE WHEN w.weekday < 5 THEN 3 ELSE 2 END
        WHEN 'A' THEN CASE WHEN w.weekday < 5 THEN 3 ELSE 2 END
        WHEN 'N' THEN CASE WHEN w.weekday < 5 THEN 3 ELSE 2 END
    END
FROM weekdays w
JOIN shift_statuses s ON s.code IN ('G', 'M', 'A', 'N')
WHERE NOT EXISTS (
    SELECT 1 FROM staffing_requirements r
    WHERE r.weekday = w.weekday AND r.status_id = s.id
);
