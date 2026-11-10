# Product decisions

These decisions resolve the open product questions in [`GOAL.md`](../GOAL.md)
and are reflected in the implementation.

## 1. Leave is pre-approved and can be recorded for any date

Administrators record availability directly; there is no approval workflow.
The availability form accepts a date range, including past dates within the
current month, so leave can be entered whenever it becomes known. Overlapping
ranges update existing entries rather than creating duplicates.

## 2. Fixed shifts with rotating week-offs

Employees hold a **primary shift** for the roster period rather than rotating
through every shift each day. The shift is `default_shift` when set; otherwise
it is derived from `rotation_offset` (`working_shifts[offset % count]`) so a
new team is balanced automatically.

Week-offs rotate independently. Each employee gets `weekly_off_days`
consecutive days off per week (default `2`), starting on the weekday given by
`rotation_offset % 7`. Different offsets therefore stagger the team's days off.

Staffing requirements are the correction layer: when coverage is short they
can recall an employee from a planned day off, and when a shift is over-staffed
they can add a day off or move an employee to another shift. Fairness counters
keep those corrections deterministic and balanced. This matches the business
roster: a person stays in their shift for the month and moves only for
coverage.

## 3. Holidays are per-month and use the `H` code

Holidays are stored with a date and label and configured through the settings
page for a selected month. Holiday dates are highlighted in violet in the grid
header and cells, use the `H` status code, and generation assigns `H` to every
employee on that date.

## 4. Employees see their own row by default

The employee home page defaults to "My row" and highlights the signed-in
employee. A "Full team" toggle reveals the complete published roster. Both
views are read-only and only expose the currently published version.

## 5. No employee cap

The roster grid uses sticky employee/date headers and horizontal scrolling, so
teams of any size remain usable. The PNG export grows vertically with the
employee count instead of truncating rows.

## 6. Accounts and login identifiers

There is no email delivery. Administrators create employee accounts and set an
initial password (default `Employee123!`) or reset it later. Employees can sign
in with either their email address or their employee code after optionally
looking up their name by ID.

Identifiers are case-insensitive. The database enforces this with functional
unique indexes on `lower(employee_code)` and `lower(email)` for employees, and
`lower(email)` for users. Service-level checks still provide friendly `409`
responses, but the indexes are the final guarantee under concurrency.

## 7. One draft per month

At most one draft roster may exist for a given month. A partial unique index on
`(year, month)` where `status = 'draft'` enforces this, and `POST /rosters` is
idempotent: it returns `201` when it creates the draft and `200` when it returns
the existing one. A new version can only be created after the previous draft is
published.

## 8. Sessions are revoked when access changes

Resetting an employee's password or deactivating their account deletes all of
that user's active sessions. Unrelated profile edits do not. Expired sessions
for a user are pruned opportunistically during login.

The CSRF token is compared in constant time, and CORS only allows the HTTP
methods and headers the application actually uses.

## 9. Date-only values are parsed locally

Roster dates are date-only strings (`YYYY-MM-DD`). The frontend parses them with
a shared helper that constructs local midnight instead of relying on
`new Date("YYYY-MM-DD")`, which is interpreted as UTC and can display the
previous day in negative-offset timezones. Timestamp fields (created/updated)
remain full ISO timestamps and are formatted separately.

## 10. Roster employee membership is not snapshotted per version

Published versions display the employees that have assignments in that version,
not a separate period-specific membership table. This is sufficient for the MVP:
it prevents later hires from appearing in older published rosters and keeps
deactivated employees visible if they were assigned. A full membership snapshot
is a documented post-MVP improvement rather than a current defect.
