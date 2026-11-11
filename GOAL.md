# GOAL.md

## Introduction

Build a simple, cross-platform roster management application that allows
administrators to manage employees and create monthly shift rosters,
while employees can securely view the published roster. The application
should be easy to use on mobile devices and desktop browsers, with a
clear calendar-style presentation.

## Goals

### 1. Employee Management

-   Allow administrators to add, view, edit, and deactivate employees.
-   Store each employee's unique ID, name, and email address.
-   Ensure employee IDs are unique.
-   Allow administrators to manage employee availability, including
    planned leave and compensatory off days.
-   Allow an employee to enter their employee ID to look up the
    associated name.
-   Show the employee's name after a valid ID is entered and allow them
    to proceed to authentication.
-   Ensure that knowing an employee ID alone does not grant access to
    private or restricted information.

### 2. User Roles and Access

-   Support at least two roles: administrator and employee.
-   Allow administrators to create, edit, generate, publish, and manage
    rosters.
-   Allow employees to view published rosters without being able to
    modify them.
-   Restrict employee and roster-management functions to authorized
    administrators.
-   Ensure users can only access information and actions permitted by
    their role.

### 3. Roster Management

-   Allow administrators to create and manage rosters for a selected
    month and year.
-   Display the roster in a clear calendar or grid format.
-   Show dates and corresponding days of the week.
-   Show employees as rows and roster dates as columns, or use another
    layout that is easier to read and use.
-   Allow administrators to assign or change an employee's shift or day
    status for any roster date.
-   Support the following roster statuses:
    -   General shift
    -   Morning shift
    -   Afternoon shift
    -   Night shift
    -   Leave
    -   Compensatory off (comp-off)
    -   Week-off / day-off
-   Make different statuses visually distinguishable through colors,
    labels, or both.
-   Provide a legend explaining all roster statuses.
-   Make the roster readable on both mobile and desktop screen sizes.
-   Preserve roster changes and make the currently published roster
    available to employees.

### 4. Assisted Roster Generation

-   Allow administrators to generate a roster automatically for a
    selected month.
-   Use the employee list, employee availability, approved leave, and
    other configured constraints as inputs.
-   Allow administrators to specify the required number of employees who
    belong to each shift for the month. Employees on their week-off still count
    towards that shift's headcount.
-   Avoid assigning employees to shifts on dates when they are
    unavailable or on approved leave.
-   Respect configured shift and scheduling constraints.
-   Distribute shifts and days off as fairly and consistently as
    possible across employees.
-   Avoid overlapping or conflicting assignments for an employee.
-   Identify dates or shifts where staffing requirements cannot be
    satisfied.
-   Allow administrators to review and edit an automatically generated
    roster before publishing it.
-   Never publish an automatically generated roster without
    administrator approval.

### 5. Roster Viewing

-   Allow employees to view the published roster for the selected month.
-   Make it easy to identify an employee's assigned shift or day status
    for each date.
-   Allow employees to find and view their own roster easily.
-   Allow authorized users to view the full team roster.
-   Clearly distinguish draft rosters from published rosters for
    administrators.
-   Ensure employees cannot change roster assignments.

### 6. Roster Export

-   Allow administrators to download a roster as an image.
-   Ensure the exported image includes the selected month, dates,
    employee names, shift assignments, and status legend.
-   Make the exported roster legible and suitable for sharing.
-   Ensure the exported image reflects the roster version selected for
    export.

### 7. Usability and Reliability

-   Keep the application simple and intuitive, avoiding unnecessary
    operational complexity.
-   Provide clear feedback for invalid employee IDs, unavailable
    employees, incomplete rosters, and scheduling conflicts.
-   Prevent accidental loss of roster changes.
-   Keep roster data consistent and accurate across users and devices.
-   Support use through modern mobile and desktop web browsers.
-   Protect employee details and roster information through appropriate
    access controls.
