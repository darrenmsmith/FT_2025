# Field Trainer API Reference

Base URL: `http://192.168.7.116:5001` (D0)

---

## PYFP — Presidential Youth Fitness Program

All PYFP routes are served by the `pyfp_bp` Flask blueprint registered in `coach_interface.py`.

### Dashboard + navigation

| Method | Route | Description |
|---|---|---|
| GET | `/pyfp/healthz` | Health check — returns `{"ok": true}` |
| GET | `/pyfp/` | PYFP dashboard — class picker, completion grid |
| GET | `/pyfp/team/<team_id>` | Redirects to dashboard with team selected |
| GET | `/pyfp/athlete/<athlete_id>` | Per-athlete battery view and event grid |
| GET | `/pyfp/reports` | Class completion grid + CSV download page |
| GET | `/pyfp/battery/<battery_id>/report` | Printable per-athlete report card |

Query parameters for UI routes: `?school_year=2025-2026&test_window=spring` (auto-defaulted to current window).

---

### Battery lifecycle

#### `POST /api/pyfp/battery/start`

Create a new battery for an athlete.

**Request body:**
```json
{
  "athlete_id": "<uuid>",
  "school_year": "2025-2026",
  "test_window": "spring",
  "rubric": "fitnessgram_hfz",
  "age_at_test": 12,
  "gender": "male"
}
```

**Rubric values:** `fitnessgram_hfz` | `pft_2026` | `both`

**Response 201:** `{"battery_id": "<uuid>", "created": true}`
**Response 200:** `{"battery_id": "<uuid>", "created": false}` (battery already exists for this window)

---

#### `GET /api/pyfp/battery/<battery_id>/status`

Returns battery + event completion status.

```json
{
  "battery": { "battery_id": "...", "rubric": "...", "completed_at": null, ... },
  "events_total": 15,
  "events_done": 8,
  "done_types": ["pyfp_curl_up", "pyfp_push_up", "..."],
  "is_complete": false
}
```

---

#### `POST /api/pyfp/battery/<battery_id>/complete`

Finalize a battery: sets `completed_at`, computes HFZ/PFT scores, writes earned awards.

**Response:**
```json
{ "ok": true, "already_complete": false, "awards": ["pft_3_of_6"] }
```

---

### Event recording

#### `POST /api/pyfp/battery/<battery_id>/event/<course_type>/record`

Submit an event result. Body varies by engine:

**manual_count** (pull_up, modified_pull_up):
```json
{ "count": 8 }
```

**manual_passfail** (shoulder_stretch):
```json
{ "right_pass": true, "left_pass": false }
```

**manual_measure** — trunk_lift:
```json
{ "inches": 10.5 }
```

**manual_measure** — sit_and_reach:
```json
{ "right_inches": 11.0, "left_inches": 10.5 }
```

**manual_measure** — v_sit_reach (up to 3 attempts):
```json
{ "attempts": [6.0, 8.5, 7.0] }
```

**manual_measure** — bmi:
```json
{ "height_ft": 4, "height_in": 10, "weight_lbs": 95 }
```

**manual_measure** — skinfold:
```json
{ "triceps_mm": 14, "calf_mm": 12 }
```

**cadence** (curl_up, push_up):
```json
{ "count": 22 }
```

**timer** (flexed_arm_hang, plank):
```json
{ "duration_seconds": 18.5 }
```

**Response 200:** `{ "ok": true, "event_result_id": "<uuid>" }`

---

### PACER bridge

#### `POST /api/pyfp/battery/<battery_id>/pacer/start`

Creates a beep-test session for the PACER event. Returns `redirect_url` for the beep-test monitor.

#### `POST /api/pyfp/battery/<battery_id>/pacer/import`

Reads completed beep-test result back and updates `pyfp_event_result`.

---

### Cone-based events (mile run, mile walk, shuttle run)

#### `GET /pyfp/battery/<battery_id>/event/<course_type>/cones`

Cone assignment UI — shows online cones and role dropdowns.

#### `POST /api/pyfp/battery/<battery_id>/event/<course_type>/cones`

Save cone assignment.

**Mile run / walk body:**
```json
{ "start_finish": "192.168.99.101", "lap_marker": "192.168.99.102", "target_laps": 4 }
```

**Shuttle run body:**
```json
{ "endpoint_a": "192.168.99.101", "endpoint_b": "192.168.99.102" }
```

#### `POST /api/pyfp/battery/<battery_id>/event/<course_type>/run/start`

Start a cone-based run. The service is immediately active and listening for touch events.

**Response 201:** `{ "ok": true, "session_id": "...", "run_id": "...", "event_result_id": "..." }`

#### `GET /api/pyfp/battery/<battery_id>/event/<course_type>/run/status`

Poll for run progress.

```json
{ "status": "active", "state": { "lap_count": 2, "target_laps": 4, "lap_times": [...] } }
```

Status values: `active` | `done` | `idle`

#### `POST /api/pyfp/battery/<battery_id>/event/<course_type>/run/abort`

Cancel an in-progress run. Result not saved.

#### `GET /pyfp/battery/<battery_id>/event/<course_type>/monitor`

Live run monitor UI (elapsed timer, progress, split times).

---

### Reporting + CSV export

#### `GET /api/pyfp/reports/csv/batteries`

Wide-format CSV — one row per battery.

Query params: `team_id` (optional), `school_year`, `test_window`

Columns: battery metadata, one column per event's best raw value, reserved HR columns, award flags.

#### `GET /api/pyfp/reports/csv/events`

Long-format CSV — one row per event result.

Query params: `team_id` (optional), `school_year`, `test_window`

Columns: event metadata, raw_value, raw_unit, attempt_number, is_best, reserved HR columns.

---

### Audio

#### `POST /api/pyfp/audio/play`

Fire a single audio clip on the D0 speaker.

```json
{ "clip": "default_beep" }
```

Clips available in `/opt/field_trainer/audio/`.

---

### Debug

#### `POST /api/pyfp/debug/touch`

Simulate a hardware touch event (for testing without field cones).

```json
{ "device_id": "192.168.99.101" }
```

---

## Scoring tables

Active scoring tables are registered in the `pyfp_scoring_table_version` DB table.
The scorer loads the JSON file at `json_path` and caches it in memory.

| Table | Rubric | Default |
|---|---|---|
| FitnessGram HFZ 2024 | fitnessgram_hfz | Yes |
| PFT 85th Percentile 2010 | pft_2026 | Yes |
| PFT 2026 Official (placeholder) | pft_2026 | No |

See `/opt/field_trainer/pyfp/README.md` for the scoring-table swap procedure.
