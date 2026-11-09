# Octopod Roster — Standard Operating Procedure (SOP)

## 1. Purpose

This SOP explains how to use the Octopod Roster application: signing in,
viewing a published roster, and — for administrators — maintaining employees,
availability, holidays, staffing requirements, and the monthly roster cycle.

It reflects the behaviour of the current application. Where the UI shows a
specific label (for example **New draft**, **Publish**, or **My row**), that
label is used here.

## 2. Roles and access

| Role | What they can do |
|------|------------------|
| **Employee** | Sign in, view the published roster for any month, switch between their own row and the full team, export the roster as a PNG. |
| **Administrator** | Everything an employee can do, plus manage employees, availability, staffing requirements, holidays, roster drafts, generation, publishing, and exports of any version. |

Navigation differs by role:

- **Employee:** `My roster`
- **Administrator:** `My roster`, `Employees`, `Rosters`, `Settings`

Administrators see the **Full team** view of *My roster* by default; employees
see **My row** by default.

Access is enforced on the server. Hiding a menu item is not the only control.

---

## 3. Signing in

1. Open the application URL.
2. On **Sign in**, enter your **Email or employee ID**.
   - Either form works: `you@example.com` or `EMP001`.
3. Enter your password and select **Sign in**.
4. If your account is active, you are taken to **My roster**.

### If you do not know your employee ID

1. On the sign-in screen, select **Look up your ID**.
2. Enter your employee ID and select **Look up employee**.
3. The page shows the matching **name** and **employee code**.
4. Select **Continue to sign in** to return to the sign-in form with the ID
   filled in.

The lookup only returns the code and name of an **active** employee. It does
**not** sign you in or reveal a password. Repeated lookups may be rate limited.

### If sign-in fails

| Message / situation | Meaning | Action |
|---|---|---|
| Invalid credentials | Wrong identifier or password | Re-check both. IDs are not case-sensitive; passwords are. |
| Account is inactive / cannot sign in | The account was deactivated | Ask an administrator to reactivate or recreate access. |
| Session expires or you are returned to sign-in | The session ended or was revoked | Sign in again. A password reset or deactivation revokes existing sessions. |
| Too many attempts | Rate limiting is active | Wait and try again. |

### Demo accounts (development / demo data only)

| Role | Identifier | Password |
|---|---|---|
| Administrator | `admin@example.com` | `Admin123!` |
| Employee | `EMP001` | `Employee123!` |

These accounts exist only when demo data has been seeded. Do not rely on them in
production.

### Signing out

Use the sign-out control in the header. Always sign out on shared devices.

---

## 4. Employee procedure — view and export your roster

1. Sign in. **My roster** opens for the current month.
2. Use the month selector (`<` / `>` beside the month name) to move between
   months.
3. Choose a view:
   - **My row** — shows only your row. Your row is highlighted.
   - **Full team** — shows every employee in the published version.
4. Read the cell for each date:

   | Code | Meaning |
   |---|---|
   | `G` | General shift |
   | `M` | Morning shift |
   | `A` | Afternoon shift |
   | `N` | Night shift |
   | `L` | Leave |
   | `CO` | Compensatory off |
   | `O` | Week-off / day-off |
   | `H` | Holiday |

   The **Legend** below the grid shows the same codes with their colours.
5. Select **Export PNG** to download an image of the roster. The export contains
   the month, dates, names, statuses, and legend.

Notes:

- You only ever see the **currently published** version. Drafts are invisible to
  employees.
- If the month has no published roster, the page shows
  *“No published roster for <month>”* with an explanation. Contact your
  administrator.
- Published rosters are read-only. If something is wrong, contact an
  administrator; you cannot edit cells.
- If your account is not linked to an employee record, **My row** shows
  *“No employee profile linked”*. Use **Full team** or ask an administrator to
  link your account.
- The grid shows today's column with a highlighted border, and weekends and
  holidays with distinct header colours. Hovering a cell shows a tooltip with
  the full status name.

---

## 5. Administrator monthly cycle (recommended order)

Run the steps in this order each month. Later steps depend on earlier data.

1. **Employees** — confirm active staff and rotation offsets.
2. **Employees → Availability** — record approved leave, comp-off, week-offs,
   and unavailable dates.
3. **Settings → Holidays** — add public/company holidays for the month.
4. **Settings → Staffing requirements** — set required headcount per weekday and
   working shift.
5. **Rosters** — select the month and select **New draft**.
6. Open the draft and select **Generate**.
7. **Review** the generated grid and correct individual cells.
8. **Publish** the draft after review.
9. **Export PNG** if a printable/shareable copy is needed.

Generation never publishes automatically. Publishing is always an explicit,
confirmed action.

---

## 6. Administrator procedure — manage employees

Open **Employees**.

### View the list

- The table shows employee name and ID, email, **Rotation** offset, and
  **Active/Inactive** status.
- Select **Show inactive** / **Hide inactive** to change the filter. The table
  shows inactive employees by default.

### Add an employee

1. Select **Add employee**.
2. Complete:
   - **Employee ID** — required; letters, numbers, hyphens, and underscores
     only. It is stored in upper case and must be unique.
   - **Full name** — required.
   - **Email** — required and unique.
   - **Initial password (optional)** — at least 8 characters. If left blank, the
     default password is `Employee123!`.
3. Select **Add employee**.

Adding an employee also creates their login account with the **employee** role.
Share the initial password securely and ask them to change it.

**Rotation** is assigned automatically as the next offset unless set explicitly.
It controls where the employee starts in the shift cycle (see §10).

### Edit an employee

1. Select **Edit** on the row.
2. Change the ID, name, or email as needed. Leave the password blank to keep the
   current one.
3. Select **Save changes**.

If you change the email, the linked login account email changes too.

### Reset a password

1. Select **Reset** on the row.
2. Enter a new password (at least 8 characters).
3. Select **Reset password**.

This signs the employee out of all existing sessions. Tell them the new
password.

### Deactivate an employee

1. Select **Deactivate** on the row.
2. Confirm in the **Deactivate employee** dialog.

Deactivation:

- prevents the employee from signing in,
- revokes their existing sessions,
- removes them from **new** drafts and generation (only active employees are
  included),
- does **not** remove them from already published or archived versions, and
- does **not** delete their record or history.

There is no “delete employee” action. Deactivation is the supported offboarding
path. The employee list has no **Reactivate** button in the UI; reactivation is
done through the API (`PATCH /api/v1/employees/{id}` with `is_active: true`).
After reactivating, re-check availability and rotation, and note that the
employee still does not appear in drafts created while they were inactive.

> **Destructive / irreversible:** deactivation and password reset take effect
> immediately and revoke sessions. Confirm the correct employee before
> proceeding.

### Open an employee's availability

Select **Availability** on the employee row. See the next section.

---

## 7. Administrator procedure — record availability

Open **Employees → Availability** for the employee. The page lists entries from
one month before the current month through six months ahead.

### Add availability

1. Set **From** and **To** dates. A single-day entry uses the same date twice.
   The **To** date auto-adjusts if it would precede **From**.
2. Choose **Type**:
   - **Leave**
   - **Compensatory off**
   - **Week-off**
   - **Unavailable**
3. Optionally add a **Note** (for example “Approved leave”).
4. Select **Add availability**.

Rules and behaviour:

- Leave is treated as pre-approved. There is no separate approval step.
- You can record dates in the past as well as the future.
- A range is expanded to one entry per calendar day.
- **Adding over an existing date overwrites that date's type and note** rather
  than creating a duplicate.
- Availability affects **generation**, not an already published roster. To apply
  changes to a published month, create a new draft and regenerate.
- During generation:
  - **Leave** → `L`
  - **Compensatory off** → `CO`
  - **Week-off** and **Unavailable** → `O`
  - A configured **holiday** overrides availability and gives everyone `H`.

### Remove availability

Select the trash icon on an entry. This deletes that single day. To clear a
range, remove each day or overwrite the range with the desired type.

---

## 8. Administrator procedure — configure settings

Open **Settings**. Settings apply globally, except holidays, which are per
month.

### 8.1 Staffing requirements

The table sets required headcount for each **working** shift (`G`, `M`, `A`,
`N`) per weekday. Non-working codes (`L`, `CO`, `O`, `H`) are not configurable
here.

1. Enter a number (0–10000) for each weekday/status cell. Blank or zero means no
   requirement.
2. Select **Save**.

Important:

- Saving replaces the **entire** requirement table with what is currently on
  screen.
- Generation reports a **shortage** for any weekday/status where assigned staff
  are below the requirement.
- Requirements are used only when at least one requirement exists. If none are
  configured, generation derives a default coverage from team size and adds a
  warning to the result.
- Requirements are applied by **weekday**, not by specific calendar date.

### 8.2 Holidays

1. Use the month selector in the **Holidays** card to choose the month.
2. Enter a **Date** within that month and a **Label**.
3. Select **Add**.
4. To remove one, select the trash icon on its row.

Rules:

- Only one holiday can exist per date. Adding a duplicate returns
  *“A holiday already exists on that date”*.
- Holidays are highlighted in the grid header (`HOL`) and every employee is
  assigned `H` during generation.
- Holiday changes affect **generation**. Regenerate a draft to apply them.
- Holidays are stored per date; the month selector only filters the list.

### 8.3 Status legend

The **Status legend** card lists the configured status codes, labels, and
colours. Use it to confirm what each code means before reviewing a roster.

---

## 9. Administrator procedure — create, generate, edit, and publish

Open **Rosters**.

### 9.1 Select the month and create a draft

1. Use the month selector to choose the target month.
2. Select **New draft**.
3. The app creates the draft (or opens the existing draft) and navigates to the
   roster editor.

Rules:

- Only **one draft per month** can exist. Selecting **New draft** again returns
  the existing draft instead of creating a duplicate.
- A new draft includes all **currently active** employees. Employees already
  assigned in the draft remain visible even if they are deactivated later.
- A new draft after a publish gets the next **version** number (v1, v2, …).
- The list shows every version for the month with its version, status, created
  date, and published date. Select **Open** to view one.

### 9.2 Generate the roster

1. Open the draft.
2. Select **Generate**.
3. If the draft already has assignments, confirm in the **Regenerate roster**
   dialog.

Generation:

- is **deterministic** for the same inputs,
- **replaces all existing assignments** in the draft,
- includes every active employee for every day of the month,
- assigns `H` to everyone on configured holidays,
- applies `L`, `CO`, and `O` from availability,
- respects configured staffing requirements where possible,
- never publishes automatically.

After generation, a result card shows:

- **Shortages** — date and shift code with `assigned/required` counts. Up to 20
  are listed, with a count of any additional shortages.
- **Warnings** — for example, no staffing requirements configured (default
  coverage used), or the reminder to review before publishing.
- If no shortages exist, it reports that all configured requirements were met.

Shortages are informational. They do not block publishing, but review them
before you publish.

### 9.3 Review and edit cells

The draft grid is editable.

1. Select any cell. The **Set status** dialog opens showing the employee and
   date.
2. Choose a status code from the list.
3. The change saves automatically; the header shows **Saving…** while it is in
   progress and reverts if the save fails.
4. Cells without an assignment show `+`.

Notes:

- The grid shows status badges, employee/day counts, and the last-updated time.
- Sticky employee and date headers stay visible while scrolling.
- Tooltips show the full status name and any assignment note.
- The draft banner reminds you that employees cannot see the roster until it is
  published.

### 9.4 Publish the draft

1. Select **Publish**.
2. Confirm in the **Publish roster** dialog.

Publishing:

- makes the roster immediately visible to employees,
- marks the draft **published** and records the publish time,
- **archives the previously published version** for that month,
- makes the published version **read-only**.

A draft with no assignments cannot be published; the API returns
*“Cannot publish an empty roster”*. Generate or add assignments first.

> **Destructive / irreversible:** publishing archives the prior published
> version. You cannot un-publish or edit a published roster. To correct it,
> create a new draft for the month, regenerate or edit it, and publish the new
> version. Employees then see the new version.

### 9.5 Export

Select **Export PNG** on any roster you can open. Administrators can export
drafts, published versions, and archived versions. Employees can export only
the currently published version.

### 9.6 Version and status reference

| Status | Meaning | Editable? | Visible to employees? |
|---|---|---|---|
| `draft` | Working copy for the month | Yes | No |
| `published` | Current official roster | No | Yes |
| `archived` | A previously published version | No | No |

---

## 10. How generation decides assignments (reference)

You do not need this to use the app, but it explains the output.

- The rotation cycle is **`G → M → A → N → O`**.
- Each employee has a **rotation offset**. The preferred status for a day is
  `cycle[(day_ordinal + rotation_offset) % 5]`. Different offsets stagger
  week-offs across the team.
- Holidays override everything: all employees receive `H`.
- Availability overrides rotation:
  - leave → `L`
  - comp-off → `CO`
  - week-off / unavailable → `O`
- Staffing requirements then pull employees into the needed working shifts.
  Ties are broken by preference match, per-shift counts, total work counts,
  rotation position, and employee ID, in that order.
- If too many employees are available, the generator adds rotating days off. If
  too few are available, it recalls employees from their rotating day off.
- Any remaining available employees work their preferred shift (or the first
  working shift if their preference was `O`).
- Remaining gaps are reported as shortages rather than hidden.

Because generation uses a shared cycle, week-offs rotate along with shifts. It
is a heuristic, not an optimiser; always review the draft.

---

## 11. Common messages and how to resolve them

| Message / symptom | Cause | Resolution |
|---|---|---|
| *Employee code already exists* | Duplicate employee ID | Use a unique ID. Compare case-insensitively. |
| *Employee email already exists* | Duplicate email | Use a unique email. |
| *A holiday already exists on that date* | Duplicate holiday | Edit or delete the existing holiday first. |
| *Cannot publish an empty roster* | Draft has no assignments | Generate the roster or add assignments manually. |
| *Only draft rosters can be edited* | Attempting to edit a published/archived version | Create a new draft for that month. |
| *Only draft rosters can be published* | Attempting to publish a non-draft | Open the draft version instead. |
| *Only draft rosters can be generated* | Attempting to generate a published/archived version | Create or open the month's draft. |
| *Date … is outside the roster month* | Manual assignment outside the month | Use a cell inside the month. |
| *Unknown status code* | Invalid status in a request | Choose a status from the picker. |
| *No active employees. Add employees before generating a roster.* | No active staff | Add or reactivate employees. |
| *No staffing requirements configured. Default coverage was derived from team size.* (warning) | Requirements table is empty | Configure requirements in **Settings** for precise coverage. |
| *No published roster for <month>* | Administrator has not published that month | Ask the administrator, or publish it. |
| *No employee profile linked* | Admin account has no employee record | Use **Full team**, or link the account. |
| *No active employee found with that ID* | Lookup for an unknown or inactive ID | Check the ID; ask an administrator. |
| Cell change reverts | Save failed (for example, session expired) | Sign in again and retry. |
| Old screen after an update | PWA/service-worker cache | Reload; the app updates on the next load. |

---

## 12. Destructive and irreversible actions

| Action | Effect | Reversible? |
|---|---|---|
| **Publish** | Archives the previous published version; published roster becomes read-only and visible to employees | No direct undo; publish a new version |
| **Generate / Regenerate** | Replaces **all** assignments in the draft | No undo; regenerate or edit manually |
| **Deactivate employee** | Blocks sign-in and revokes sessions; excludes them from new drafts | Yes, by reactivating, but history is not restored to drafts |
| **Reset password** | Changes the password and revokes sessions | Yes, by resetting again |
| **Delete holiday** | Removes it and its label | Only by re-adding it |
| **Delete availability** | Removes that day's availability entry | Only by re-adding it |
| **Save staffing requirements** | Replaces the whole requirements table | By re-entering and saving the correct table |

---

## 13. Monthly checklist (administrator)

- [ ] Confirm the employee list is current; deactivate leavers and add new staff.
- [ ] Set or verify rotation offsets for new employees.
- [ ] Enter all approved leave, comp-off, week-offs, and unavailable dates.
- [ ] Add this month's holidays in **Settings**.
- [ ] Review **Staffing requirements** for each weekday.
- [ ] Create or open the month's draft.
- [ ] Select **Generate** and review the result.
- [ ] Read every **shortage** and **warning**; adjust staffing, availability, or
      cells as needed.
- [ ] Spot-check holidays, weekends, leave, and night shifts.
- [ ] Publish and confirm.
- [ ] Export a PNG if a copy is needed.
- [ ] Tell employees the roster is published.

---

## 14. Quick reference

| Task | Where |
|---|---|
| Sign in | `/login` |
| Look up an employee ID | `/lookup` |
| View published roster | `My roster` |
| Manage employees | `Employees` |
| Record availability | `Employees → Availability` |
| Staffing requirements and holidays | `Settings` |
| Create/generate/publish rosters | `Rosters` |
| Employee default password | `Employee123!` |
| Minimum password length | 8 characters |
| Working statuses | `G`, `M`, `A`, `N` |
| Non-working statuses | `L`, `CO`, `O`, `H` |
| Rotation cycle | `G → M → A → N → O` |
| Drafts per month | One |
| Roster export format | PNG |
