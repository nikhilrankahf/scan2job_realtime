## Functional Requirements: Scan2Job Live Floor Tracking Dashboard (Widgets)

This document specifies the functional requirements for every user-facing widget in the Streamlit dashboard so engineers can precisely implement behavior and data logic.

### Scope
- Focuses on interactive Streamlit widgets (inputs, toggles, buttons, expanders, tables).
- Summarizes the data definitions that these widgets rely on.

## Data definitions used by widgets
- Data source: `Scan2Job Realtime Sample Data.csv`.
- Records are normalized into a people-centric dataframe with columns: `associate_id`, `associate_name`, `supervisor_name`, `job_department`, `work_department`, `work_position`, `shift_type`, `line` (optional), `last_activity_ts`, boolean flags `on_floor`, `scanned_in`, `unscanned`, `clocked_in`.
- Derived flags:
  - **scanned_in**: True if any record for associate has `SOURCE ∈ {"Badgr","HighJump","Pick to Light"}`.
  - **unscanned**: True if any record has `SOURCE = "Compliance"` OR `WORK_DEPARTMENT = "Compliance"` OR `WORK_POSITION = "Time Off Task"`.
  - **on_floor**: True if associate appears in the CSV (i.e., any event in the file).
  - **clocked_in**: From Workday events: latest `Punch in` exists and is later than latest `Punch out` (or no `Punch out`).
- General grouping rules:
  - Hiring/Job department displays use `job_department` (blank → "—").
  - Work department groupings map multiple sub-departments to a Job-level group:
    - `Assembly`,`Kitting`,`Site Support` → `Production`
    - `Admin`,`HR/Admin` → `Other`
    - See code map for all mappings (engineers must keep this mapping configurable).
  - Ignore work departments that equal "Compliance" and timecard-related values where noted.

## Authentication widgets

### Password form
- Location: Top of app when not authenticated.
- Widgets:
  - `Password` text input (masked).
  - `Login` button (form submit).
- Behavior:
  - Accepts a single shared password from secret `APP_PASSWORD`.
  - On valid password:
    - Sets session `__authed = True` and timestamp `__auth_ts = now`.
    - Persists a short token in URL query params `auth` and `asu` to survive full reloads within timeout.
    - Timeout minutes from secret `APP_PASSWORD_TIMEOUT_MIN` (default 30); sliding window refreshes on activity.
    - Reruns app after success.
  - On invalid password: displays error and remains on login screen.
  - While authenticated: access is allowed until idle timeout is exceeded, after which the form is shown again.
- Acceptance criteria:
  - Correct password grants access without re-prompting within the timeout window (even after full reload).
  - Wrong password never grants access.
  - After idle timeout passes, user must log in again.

## Sidebar widgets

### Toggle: Hide names on wallboard
- Label: “Hide names on wallboard”
- Default: Off
- Behavior:
  - When On: mask names in the people table (`Name = "—"`).
  - When Off: show true names.
  - Does not affect counts, breakdowns, or ordering beyond the name field display.
- Acceptance criteria:
  - Toggling immediately updates the table’s `Name` column masking.
  - No impact on row inclusion or counts in any section.

## Mid page breakdown widgets

### Expanders: Scanned-in Breakdown
- Header: `Scanned-in Breakdown (X)` where X is the count of unique `associate_id` with `scanned_in = True` after ignoring Compliance/timecard rows.
- Body structure (interactive):
  - Level 1 (rows): Job Group (mapped from `work_department`) shown in On Floor ordering; each row shows `Group — count`. If the group has sub-departments, render an expander instead of a flat row.
  - Level 2 (expander): Sub-Department rows (by cleaned `work_department`, including `NA`), each shows `Sub-Department — count`. If a sub-department has valid `line` values, render an expander; otherwise show as flat text row.
  - Level 3 (expander): Line rows `Line — count`. If a line has valid `work_position` values, render an expander; otherwise show as flat text row.
  - Level 4 (expander): Table listing counts by `Work Position` for that line (columns: `Work Position`, `Associates`).
- Data rules:
  - Ignore rows where work department equals "Compliance" or contains "time card" (case-insensitive) for this section.
  - Normalization for display-level values: treat `""`, `None`, `—`, `nan`, `NaN` as `NA`.
  - Ordering of Level 1 groups matches the On Floor Headcount department ordering; ensure `Other` appears last.
- Empty state: “No scanned-in associates.”
- Acceptance criteria:
  - Counts per level equal unique `associate_id` counts for that filtered subset.
  - Expanders appear only when a level has nested detail; otherwise show flat row.
  - Normalization and ignoring rules are applied exactly as specified.

### Table: Non-Scanned Breakdown
- Header: `Non-Scanned Breakdown (Y)` where Y is the count of unique `associate_id` with `on_floor = True` and `scanned_in = False`.
- Widget: Data table with columns `Job Department`, `Associates`.
- Behavior:
  - Group by `job_department` (blanks → "—"), count unique `associate_id`, sort descending by `Associates`.
  - Apply the same ignoring rules for Compliance/timecard only where specified in code (non-scanned uses `on_floor & ~scanned_in` directly; do not drop rows beyond that logic).
- Empty state: “No non-scanned associates.”
- Acceptance criteria:
  - Totals align with header count.
  - Sorting and blank handling match spec.

## People table and filtering widgets

### Expander: 🔍 Filters
- Default: Collapsed.
- Inputs inside (case-insensitive contains filters, combined with AND across fields):
  - Text input: `Id contains`
  - Text input: `Name contains`
  - Text input: `Hiring Dept contains`
  - Text input: `Work Dept contains`
  - Text input: `Work Position contains`
  - Select box: `Scanned In` with options `(any)`, `Yes`, `No`
- Behavior:
  - Each text input filters its corresponding column using substring match (case-insensitive).
  - `Scanned In`:
    - `(any)`: do not filter by scanned state.
    - `Yes`: keep rows where `Scanned In = True`.
    - `No`: keep rows where `Scanned In = False`.
  - Filters inside this expander combine with the controls row filters (see below) via AND.
- Acceptance criteria:
  - Changing any input immediately updates the table.
  - All matches are case-insensitive and operate on string representations.

### Controls row: global search, quick toggles, department select, clear
- Inputs:
  - Text input: `Search` (placeholder “Search ID, Name, or keyword…”).
  - Toggle: `Not Scanned-In` (keeps rows where `Scanned In = False`).
  - Toggle: `Not Clocked-In` (keeps rows where `Clocked In = False`).
  - Select box: `Department` with options `[ "(any)", <sorted unique hiring departments> ]`.
  - Button: `Clear All Filters`.
- Behavior:
  - `Search`: applies a case-insensitive substring match across all visible columns in the rendered table (row retained if any column contains the query).
  - `Not Scanned-In`: when On, apply filter `Scanned In = False`.
  - `Not Clocked-In`: when On, apply filter `Clocked In = False`.
  - `Department`: when a specific department is selected (not `(any)`), apply exact match filter on `Hiring Department`.
  - `Clear All Filters`:
    - Implements a deferred clear: sets a flag and triggers a rerun.
    - On next run, resets only these controls to default values:
      - `Search` → `""`
      - `Not Scanned-In` → `False`
      - `Not Clocked-In` → `False`
      - `Department` → `(any)`
    - Other expander filters return to their defaults via normal rerun behavior (empty values).
- Acceptance criteria:
  - All filters combine with AND across the expander and controls row.
  - `Clear All Filters` resets the four controls listed above and the table reflects no filters.
  - Department options list includes `(any)` followed by unique departments sorted ascending.

### Table: Latest Associate Activity
- Header: `Latest Associate Activity (N)` where N equals the number of rows after all filters.
- Widget: Data table of the following columns (renamed and in order):
  - `Id`, `Name`, `Hiring Department`, `Shift Type`, `Supervisor Name`, `Clocked In`, `Scanned In`, `Work Department`, `Work Position`, `Last Activity Timestamp`
- Behavior:
  - Apply sidebar name masking before rendering when “Hide names on wallboard” is On.
  - Sort rows by `Hiring Department` then `Name` ascending.
  - Hide index; use full container width.
- Acceptance criteria:
  - Row count equals header N.
  - Sorting/order, masking, and column set match spec exactly.

## Information popovers (FYI)
- Titles such as `On Floor Headcount (total)` and other section headers include an inline info popover that explains how counts are computed.
- Content is non-interactive from a data perspective and does not alter counts/filters.

## Non-functional behavior tied to widgets
- State persistence:
  - Authentication state persists across reruns within the timeout window via session and query params.
  - Filter controls persist using Streamlit’s session state keys as implemented for the controls row.
- Deferred clear:
  - The clear button sets a session flag, then performs rerun to safely reset widget state on the next run without conflicting writes.

## General acceptance checks
- Counts in headers match the underlying unique `associate_id` cardinalities after applied filters for those sections.
- Case-insensitive matching for all substring filters and global search.
- Empty states render informative messages instead of empty tables where specified.


