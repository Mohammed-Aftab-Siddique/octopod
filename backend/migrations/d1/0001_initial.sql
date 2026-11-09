-- Initial D1 schema. SQLite/D1 stores enums as text with CHECK constraints and
-- booleans as 0/1.
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    employee_code VARCHAR(50) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    rotation_offset INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX ix_employees_email ON employees (email);
CREATE UNIQUE INDEX ix_employees_employee_code ON employees (employee_code);

CREATE TABLE holidays (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    label VARCHAR(120) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX ix_holidays_date ON holidays (date);

CREATE TABLE shift_statuses (
    id INTEGER PRIMARY KEY,
    code VARCHAR(8) NOT NULL,
    label VARCHAR(60) NOT NULL,
    color VARCHAR(20) NOT NULL,
    text_color VARCHAR(20) NOT NULL DEFAULT '#111827',
    is_working BOOLEAN NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX ix_shift_statuses_code ON shift_statuses (code);

CREATE TABLE staffing_requirements (
    id INTEGER PRIMARY KEY,
    weekday INTEGER NOT NULL,
    status_id INTEGER NOT NULL,
    required_count INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_staffing_weekday_status UNIQUE (weekday, status_id),
    FOREIGN KEY (status_id) REFERENCES shift_statuses (id) ON DELETE CASCADE
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'employee'
        CHECK (role IN ('admin', 'employee')),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    employee_id INTEGER UNIQUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE availability (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    date DATE NOT NULL,
    kind VARCHAR(20) NOT NULL
        CHECK (kind IN ('leave', 'comp_off', 'week_off', 'unavailable')),
    note VARCHAR(255),
    created_by INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_availability_employee_date UNIQUE (employee_id, date),
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users (id)
);
CREATE INDEX ix_availability_date ON availability (date);
CREATE INDEX ix_availability_employee_id ON availability (employee_id);

CREATE TABLE roster_periods (
    id INTEGER PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'archived')),
    created_by INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_by INTEGER,
    published_at DATETIME,
    CONSTRAINT uq_roster_period_version UNIQUE (year, month, version),
    FOREIGN KEY (created_by) REFERENCES users (id),
    FOREIGN KEY (published_by) REFERENCES users (id)
);
CREATE INDEX ix_roster_periods_year ON roster_periods (year);
CREATE INDEX ix_roster_periods_month ON roster_periods (month);
CREATE UNIQUE INDEX uq_roster_period_published
    ON roster_periods (year, month) WHERE status = 'published';
CREATE UNIQUE INDEX uq_roster_period_draft
    ON roster_periods (year, month) WHERE status = 'draft';

CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY,
    token_hash VARCHAR(64) NOT NULL,
    csrf_token VARCHAR(64) NOT NULL,
    user_id INTEGER NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_user_sessions_token_hash ON user_sessions (token_hash);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);

CREATE TABLE generation_runs (
    id INTEGER PRIMARY KEY,
    roster_period_id INTEGER NOT NULL,
    created_by INTEGER,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'succeeded',
    shortages JSON NOT NULL DEFAULT '[]',
    warnings JSON NOT NULL DEFAULT '[]',
    FOREIGN KEY (roster_period_id) REFERENCES roster_periods (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users (id)
);
CREATE INDEX ix_generation_runs_roster_period_id
    ON generation_runs (roster_period_id);

CREATE TABLE roster_assignments (
    id INTEGER PRIMARY KEY,
    roster_period_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status_id INTEGER NOT NULL,
    note VARCHAR(255),
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_assignment_period_employee_date
        UNIQUE (roster_period_id, employee_id, date),
    FOREIGN KEY (roster_period_id) REFERENCES roster_periods (id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees (id) ON DELETE CASCADE,
    FOREIGN KEY (status_id) REFERENCES shift_statuses (id)
);
CREATE INDEX ix_roster_assignments_date ON roster_assignments (date);
CREATE INDEX ix_roster_assignments_employee_id ON roster_assignments (employee_id);
CREATE INDEX ix_roster_assignments_roster_period_id ON roster_assignments (roster_period_id);
