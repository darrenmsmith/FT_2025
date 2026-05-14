# Field Trainer — Technical Overview

## Architecture

Field Trainer runs as a single Flask process (`coach_interface.py`) on the Raspberry Pi D0
at port 5001. SQLite is the primary datastore. Field devices (D1–D5) communicate via BLE
beacons; their touch events are dispatched through `session_service.handle_touch_event`.

```
┌─────────────────────────────────────────────────────────┐
│  coach_interface.py  (Flask app, port 5001)             │
│                                                          │
│  Blueprints registered:                                  │
│    pyfp_bp        — /pyfp/, /api/pyfp/                  │
│    beep_test_bp   — /beep-test/, /api/beep-test/        │
│    sprint_bp      — /sprint/, /api/sprint/              │
│    sessions_bp    — /api/sessions/                      │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┴──────────────────┐
        │  field_trainer/                  │
        │    db_manager.py   (SQLite ORM)  │
        │    ft_registry.py  (REGISTRY)    │
        │    ft_heartbeat.py               │
        │    ft_models.py                  │
        │    pyfp/           (PYFP module) │
        │      scoring.py                  │
        │      awards.py                   │
        │      csv_export.py               │
        │      events_registry.py          │
        │      pacer_bridge.py             │
        │      default_landing.py          │
        └──────────────────────────────────┘
                        │
        ┌───────────────┴──────────────────┐
        │  services/                       │
        │    session_service.py            │
        │    beep_test_service.py          │
        │    sprint_service.py             │
        │    pyfp_mile_service.py          │
        │    pyfp_shuttle_service.py       │
        └──────────────────────────────────┘
```

---

## Database

`/opt/data/field_trainer.db` — SQLite, foreign keys OFF (legacy behavior preserved).

### Core tables

| Table | Purpose |
|---|---|
| `teams` | Athlete groups (PE classes, sports teams) |
| `athletes` | Individual athletes; FK to `teams` |
| `courses` | Course definitions; `category='PYFP'` for PYFP events |
| `sessions` | One assessment session per athlete-course pair |
| `runs` | One run per athlete within a session |
| `segments` | Timed legs within a run |
| `performance_history` | PR-tracking metric store (cross-module) |
| `personal_records` | Current PR per athlete/metric |
| `settings` | Key-value config (e.g., `default_landing`) |

### PYFP tables (added Phase 1)

| Table | Purpose |
|---|---|
| `pyfp_assessment_battery` | One row per athlete per (school_year, test_window). Holds rubric, age_at_test, gender. UNIQUE on (athlete_id, school_year, test_window). |
| `pyfp_event_result` | One row per attempt per event per battery. `is_best=1` on the canonical score. |
| `pyfp_cone_assignment` | Cone role → device_id mapping for mile/shuttle events. |
| `pyfp_award` | Awards earned on battery completion. |
| `pyfp_scoring_table_version` | Registry of JSON scoring tables with default flags. |

---

## PYFP module

### Event registry (`events_registry.py`)

Single source of truth for which events belong to which rubric and what engine handles recording.

```python
EVENTS = {
    "pyfp_pacer": {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "engine": "beep_test_bridge"},
    ...
}
events_for_rubric('fitnessgram_hfz')  # → list of 15 course_type strings
events_for_rubric('pft_2026')         # → list of 6 course_type strings
events_for_rubric('both')             # → all 16
```

### Scoring (`scoring.py`)

Loads the default JSON table for a rubric from DB, caches in-memory per path.

```python
classify_hfz(course_type, raw_value, age, gender, db)
# → 'hfz' | 'below_hfz' | 'above_hfz' | 'unscored'

classify_pft(course_type, raw_value, age, gender, db)
# → 'meets' | 'below' | 'unscored'

score_battery(battery, results, db)
# → {course_type: {'hfz': ..., 'pft': ...}}
```

Classification logic:
- **Higher-is-better events** (reps, laps, inches): `< hfz_min` → below; `hfz_min..hfz_max` → hfz; `> hfz_max` → above
- **Lower-is-better events** (seconds): `> hfz_max` → below; `≤ hfz_max` → hfz
- **Range events** (BMI, skinfold): `< hfz_min` → above_hfz (underweight); `hfz_min..hfz_max` → hfz; `> hfz_max` → below_hfz (overweight)

### Awards (`awards.py`)

Called from `POST /api/pyfp/battery/<id>/complete`. Writes to `pyfp_award` via
`INSERT OR REPLACE` (idempotent).

```
hfz_all_zones  — all HFZ-rubric events scored hfz or above_hfz
pft_3_of_6     — ≥3 of 6 PFT events score 'meets'
pft_full_6     — all 6 PFT events score 'meets'
```

### Touch dispatch (`session_service.py`)

PYFP cone services intercept touch events at the top of `handle_touch_event`,
before the standard session routing:

```python
def handle_touch_event(device_id, timestamp):
    # PYFP mile/walk
    mile_svc = get_pyfp_mile_service()
    if mile_svc.is_active():
        mile_svc.handle_touch(device_id, timestamp)
        return
    # PYFP shuttle
    shuttle_svc = get_pyfp_shuttle_service()
    if shuttle_svc.is_active():
        shuttle_svc.handle_touch(device_id, timestamp)
        return
    # ... existing session routing
```

### Service singletons

`pyfp_mile_service.py` and `pyfp_shuttle_service.py` follow the singleton pattern
(one active run at a time, held in module-level `_svc`). They use their own
`DatabaseManager` instances to avoid circular imports.

---

## Cone-based events — data flow

```
Coach assigns cones → POST /api/pyfp/battery/.../cones
    → writes pyfp_cone_assignment rows

Coach clicks Start → POST /api/pyfp/battery/.../run/start
    → PyfpMileService.start() / PyfpShuttleService.start()
    → creates session + run + segments in DB
    → sets service state to 'active'
    → lights cones green via REGISTRY.set_led()

Athlete runs → hardware BLE touch → REGISTRY._touch_handler()
    → session_service.handle_touch_event()
    → PyfpMileService.handle_touch() / PyfpShuttleService.handle_touch()
    → db.record_touch() → records segment timing

Final touch → service._finish()
    → db.complete_run() + db.complete_session()
    → UPDATE pyfp_event_result SET raw_value = total_seconds
    → db.write_pyfp_performance_history()
    → sets service state to 'done'
    → cones return to amber
```

---

## CSV export

Two formats served from `pyfp/csv_export.py`:

- **Wide** (`batteries_csv`): 32 columns — battery metadata + one column per event's best
  raw value + reserved HR columns + award flags
- **Long** (`events_csv`): 18 columns — one row per `pyfp_event_result` row

Both functions accept a list of battery dicts and a `db` instance; they are
pure Python with no Flask dependency, making them testable in isolation.

---

## Scoring table JSON format

```json
{
  "name": "FitnessGram HFZ 2024",
  "rubric": "fitnessgram_hfz",
  "events": {
    "pyfp_pacer": {
      "unit": "laps",
      "is_better_higher": true,
      "by_age_gender": {
        "male":   { "10": { "hfz_min": 23, "hfz_max": 999 } },
        "female": { "10": { "hfz_min": 15, "hfz_max": 999 } }
      }
    }
  }
}
```

PFT tables use `"p85"` instead of `"hfz_min"/"hfz_max"`.
Age lookup clamps to the nearest available age key (no KeyError on out-of-range ages).

---

## Adding a new PYFP event

1. Add an entry to `events_registry.py` (`EVENTS` dict).
2. Add a `course_type` row in `create_pyfp_courses.sql` (and apply it).
3. Add the engine handler in `pyfp_bp.py` (`event_record_submit`).
4. Add HFZ/PFT thresholds to the relevant scoring JSON files.
5. Add a column mapping to `csv_export.py` (`_CT_TO_COL`).
6. Add a test case to `pyfp_test_plan.md`.
