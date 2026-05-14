# PYFP Manual Test Plan — v1.0

Field Trainer PYFP module — 45 test cases.
Run after each deploy that touches PYFP code. HR cases (Phase 9) appended when that phase ships.

---

## How to use this plan

- Mark each case **PASS**, **FAIL**, or **SKIP** (skip = not applicable on this hardware).
- A failed case blocks release unless explicitly waived.
- Cases marked `[HW]` require at least one field cone online (192.168.99.10x).
- Cases marked `[BT]` require the beep-test hardware (speaker + D0).

---

## §1 — Schema (5 cases)

| # | Description | Expected |
|---|---|---|
| 1.1 | `create_pyfp_schema.sql` applied to fresh DB | All 5 PYFP tables and 5 indexes exist |
| 1.2 | Re-run `create_pyfp_schema.sql` on existing DB | No error; existing data untouched (CREATE IF NOT EXISTS) |
| 1.3 | `create_pyfp_courses.sql` applied | 16 `pyfp_*` rows in `courses`; each has `category='PYFP'` |
| 1.4 | `INSERT OR IGNORE` for `default_landing` setting | Row present; re-run does not duplicate |
| 1.5 | `pyfp_event_result` UNIQUE constraint | Second insert with same (battery_id, course_type, attempt_number) raises IntegrityError |

---

## §2 — Dashboard + battery lifecycle (6 cases)

| # | Description | Expected |
|---|---|---|
| 2.1 | `GET /pyfp/` with no team selected | Dashboard renders; "select a class" prompt visible |
| 2.2 | `GET /pyfp/?team_id=<id>&school_year=&test_window=` | Athlete completion grid shown; progress bars render |
| 2.3 | Start battery via UI (HFZ rubric) | `pyfp_assessment_battery` row created; athlete view shows HFZ event grid (15 events) |
| 2.4 | Start battery via UI (PFT rubric) | Event grid shows 6 PFT events only |
| 2.5 | Start battery via UI (Both rubric) | Event grid shows all 16 events |
| 2.6 | `POST /api/pyfp/battery/<id>/complete` | `completed_at` set; row highlighted green in dashboard; awards computed |

---

## §3 — Manual-entry events (14 cases — one per event)

For each: record a value → verify `pyfp_event_result` row present with `is_best=1`
and a `performance_history` row present.

| # | Event | Engine | Test value |
|---|---|---|---|
| 3.1  | pyfp_pull_up          | manual_count   | 5 reps |
| 3.2  | pyfp_modified_pull_up | manual_count   | 10 reps |
| 3.3  | pyfp_trunk_lift       | manual_measure | 10 inches |
| 3.4  | pyfp_sit_and_reach    | manual_measure | right=11, left=10 |
| 3.5  | pyfp_v_sit_reach      | manual_measure | 3 attempts: 6, 8, 7 → best=8 |
| 3.6  | pyfp_shoulder_stretch | manual_passfail| right=pass, left=pass → score=2 |
| 3.7  | pyfp_bmi              | manual_measure | height 5'2", weight 110 lbs → BMI≈20.1 |
| 3.8  | pyfp_skinfold         | manual_measure | triceps=15mm, calf=12mm, male → ~19.7% |
| 3.9  | pyfp_curl_up          | cadence        | 22 reps |
| 3.10 | pyfp_push_up          | cadence        | 14 reps |
| 3.11 | pyfp_flexed_arm_hang  | timer          | 18.5 seconds |
| 3.12 | pyfp_plank            | timer          | 63.0 seconds |
| 3.13 | pyfp_mile_run         | mile_service   | [HW] 4-lap run via cone, result > 0s |
| 3.14 | pyfp_shuttle_run      | shuttle_service| [HW] B→A→B→A, result > 0s |

Additional: re-record (second attempt) for pyfp_v_sit_reach → `is_best` updates correctly.

---

## §4 — Scoring boundaries (4 cases)

| # | Description | Expected |
|---|---|---|
| 4.1 | HFZ pass edge: 10yo male PACER = 23 laps (hfz_min) | `classify_hfz` → `'hfz'` |
| 4.2 | HFZ fail edge: 10yo male PACER = 22 laps (below min) | `classify_hfz` → `'below_hfz'` |
| 4.3 | PFT meets edge: 10yo male PACER = 32 laps (= p85) | `classify_pft` → `'meets'` |
| 4.4 | Age clamp: age=20 passed to scorer | Returns value for age=17 (max clamped); no KeyError |

---

## §5 — Awards (3 cases)

| # | Description | Expected |
|---|---|---|
| 5.1 | Battery with all HFZ events ≥ hfz_min → complete | `pyfp_award` row with `award_type='hfz_all_zones'`; appears on report card |
| 5.2 | Battery with exactly 3 of 6 PFT events meeting p85 → complete | `award_type='pft_3_of_6'` present; `pft_full_6` absent |
| 5.3 | Battery with all 6 PFT events meeting p85 → complete | Both `pft_3_of_6` and `pft_full_6` present |

---

## §6 — PACER bridge (3 cases)

| # | Description | Expected |
|---|---|---|
| 6.1 `[BT]` | `POST /api/pyfp/battery/<id>/pacer/start` | Beep-test session created; response contains `redirect_url`; navigating to URL shows beep-test monitor |
| 6.2 `[BT]` | After completing PACER, `POST /api/pyfp/battery/<id>/pacer/import` | `pyfp_event_result.raw_value` = computed total laps; `performance_history` row present |
| 6.3 | Import with no completed PACER session | Returns `{'ok': False, 'error': '...'}` or appropriate message |

---

## §7 — Cone assignment (4 cases)

| # | Description | Expected |
|---|---|---|
| 7.1 `[HW]` | Mile run: assign single start/finish cone → Save | `pyfp_cone_assignment` row with role=`start_finish`; redirected to monitor |
| 7.2 `[HW]` | Mile run: assign start/finish + lap marker cone | Two rows in `pyfp_cone_assignment` |
| 7.3 `[HW]` | Shuttle: assign two different endpoint cones | Two rows (endpoint_a, endpoint_b) |
| 7.4 | Shuttle: submit same cone for both endpoints | API returns 400 "endpoints must be different" |

---

## §8 — Reporting (6 cases)

| # | Description | Expected |
|---|---|---|
| 8.1 | `GET /pyfp/battery/<id>/report` | Report card renders; events table has HFZ/PFT classification badges |
| 8.2 | Report card for incomplete battery | Warning banner shown; scoring still renders for completed events |
| 8.3 | `GET /api/pyfp/reports/csv/batteries?school_year=&test_window=` | CSV downloads; header row has all 32 columns; data rows populated |
| 8.4 | `GET /api/pyfp/reports/csv/events?school_year=&test_window=` | CSV downloads; header row has 18 columns; one row per event_result |
| 8.5 | `GET /pyfp/reports?team_id=&school_year=&test_window=` | Reports page renders; complete rows highlighted green |
| 8.6 | CSV with no matching batteries | CSV downloads with header row only (no data rows) |

---

## §9 — Default-landing + nav (3 cases)

| # | Description | Expected |
|---|---|---|
| 9.1 | `default_landing` setting = `'pyfp'` → `GET /` | Redirects to `/pyfp/` |
| 9.2 | `default_landing` setting = `'coach_dashboard'` → `GET /` | Serves standard FT dashboard |
| 9.3 | Main FT dashboard course list | PYFP courses absent (`pyfp_*` rows not shown) |

---

## §10 — Smoke tests (5 cases)

| # | Description | Expected |
|---|---|---|
| 10.1 | `GET /pyfp/healthz` | `{"ok": true}`, HTTP 200 |
| 10.2 | Service restart → navigate to `/pyfp/` | No import errors in log; page renders |
| 10.3 | Run seed script twice | Second run skips existing records; no duplicates in DB |
| 10.4 | Battery with rubric=both → CSV export | Event columns for both HFZ-only and PFT-only events populated |
| 10.5 | Abort in-progress mile run | `run_status` → idle; cone LED returns to amber; battery remains in-progress |

---

*Phase 9 (HR) appends 3 additional cases when that phase ships.*
