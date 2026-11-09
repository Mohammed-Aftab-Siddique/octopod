-- Normalise identifiers and enforce case-insensitive uniqueness. SQLite and D1
-- both support expression indexes on lower(). Employee codes are displayed and
-- stored uppercase by the application; emails are stored lowercase.
UPDATE employees SET employee_code = upper(employee_code);
UPDATE employees SET email = lower(email);
UPDATE users SET email = lower(email);

CREATE UNIQUE INDEX uq_employees_employee_code_lower
    ON employees (lower(employee_code));
CREATE UNIQUE INDEX uq_employees_email_lower
    ON employees (lower(email));
CREATE UNIQUE INDEX uq_users_email_lower
    ON users (lower(email));
