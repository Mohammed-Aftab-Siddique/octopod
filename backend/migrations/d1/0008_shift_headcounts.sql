-- Staffing requirements are shift headcounts for the whole month, not
-- per-weekday coverage. Collapse the old weekday rows into one row per shift,
-- keeping the largest configured count.
CREATE TABLE staffing_requirements_new (
    id INTEGER PRIMARY KEY,
    status_id INTEGER NOT NULL,
    required_count INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_staffing_status UNIQUE (status_id),
    FOREIGN KEY (status_id) REFERENCES shift_statuses (id) ON DELETE CASCADE
);

INSERT INTO staffing_requirements_new (id, status_id, required_count)
SELECT MIN(id), status_id, MAX(required_count)
FROM staffing_requirements
GROUP BY status_id;

DROP TABLE staffing_requirements;
ALTER TABLE staffing_requirements_new RENAME TO staffing_requirements;
