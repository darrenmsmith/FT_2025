# PYFP Module — Field Trainer

Presidential Youth Fitness Program assessment module for Field Trainer.
Supports FitnessGram HFZ, PFT 2026, and combined rubrics.

---

## Quick-start install

The PYFP module is already wired into `coach_interface.py`. On a fresh
deploy the only one-time setup steps are:

```bash
# 1. Apply schema + courses (idempotent — safe to re-run)
python3 -c "
import sys; sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
db = DatabaseManager('/opt/data/field_trainer.db')
with open('/opt/data/create_pyfp_schema.sql') as f:
    with db.get_connection() as conn:
        conn.executescript(f.read())
with open('/opt/data/create_pyfp_courses.sql') as f:
    with db.get_connection() as conn:
        conn.executescript(f.read())
"

# 2. Seed scoring-table version rows (run once; idempotent via INSERT OR IGNORE)
python3 /opt/data/seed_pyfp_scoring_tables.py   # created by Phase 1

# 3. (Optional) Load demo data
python3 /opt/data/seed_pyfp_demo.py
```

The blueprint is registered in `coach_interface.py` automatically; no
additional Flask wiring is needed.

---

## Daily workflow

```
/pyfp/                                # PYFP dashboard — pick class + window
/pyfp/athlete/<athlete_id>            # per-athlete event grid + battery start
/pyfp/battery/<battery_id>/event/<course_type>/record   # record an event
/pyfp/battery/<battery_id>/report     # printable report card
/pyfp/reports                         # class completion grid + CSV export
```

---

## Scoring table swap

Scoring tables live in `/opt/data/pyfp_scoring/`. Each JSON file is
registered in the `pyfp_scoring_table_version` DB table.

**To swap to a new table:**

1. Drop the new JSON into `/opt/data/pyfp_scoring/my_new_table.json`.
   Follow the schema in `hfz_standards_2024.json` exactly.

2. Register it:

```python
import sys; sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
db = DatabaseManager('/opt/data/field_trainer.db')
with db.get_connection() as conn:
    conn.execute(
        """INSERT INTO pyfp_scoring_table_version
               (name, rubric, source_url, effective_from, json_path, is_default)
           VALUES (?, ?, ?, ?, ?, 1)""",
        ('My Table Name', 'fitnessgram_hfz', None, '2025-01-01',
         '/opt/data/pyfp_scoring/my_new_table.json')
    )
    # Clear old default for this rubric
    conn.execute(
        "UPDATE pyfp_scoring_table_version SET is_default=0 WHERE name != 'My Table Name' AND rubric='fitnessgram_hfz'"
    )
```

3. Clear the in-memory JSON cache (requires service restart):

```bash
sudo systemctl restart field-trainer-server.service
```

---

## Event engines

| Engine | Events | Notes |
|---|---|---|
| `manual_count` | pull_up, modified_pull_up | Integer count |
| `manual_measure` | trunk_lift, sit_and_reach, v_sit_reach, bmi, skinfold | BMI auto-computed; skinfold uses Slaughter equation |
| `manual_passfail` | shoulder_stretch | Right + left, each pass/fail |
| `cadence` | curl_up, push_up | Server fires start beep; browser metronome at selectable BPM |
| `timer` | flexed_arm_hang, plank | Client-side stopwatch; submits elapsed seconds |
| `beep_test_bridge` | pacer | Redirects to existing beep-test module; imports result back |
| `mile_service` | mile_run, mile_walk | Cone-based; coach assigns start/finish cone |
| `shuttle_service` | shuttle_run | Cone-based; B→A→B→A touch sequence |

---

## Awards

Awards are computed automatically when the coach presses **Complete Battery**
(`POST /api/pyfp/battery/<id>/complete`).

| Award | Criterion |
|---|---|
| `hfz_all_zones` | All HFZ events scored ≥ HFZ minimum (no below-HFZ results) |
| `pft_3_of_6` | At least 3 of the 6 PFT events meet the 85th-percentile standard |
| `pft_full_6` | All 6 PFT events meet the 85th-percentile standard |

Awards are stored in `pyfp_award` and shown on the battery report card.

---

## CSV export

```
GET /api/pyfp/reports/csv/batteries?team_id=&school_year=&test_window=
    → Wide format: one row per battery, one column per event (best attempt)

GET /api/pyfp/reports/csv/events?team_id=&school_year=&test_window=
    → Long format: one row per event_result (all attempts)
```

HR columns are present but empty until Phase 9 (HR overlay).

---

## Rollback

```bash
# Full PYFP rollback (git)
git checkout pre-pyfp-main -- .
sudo systemctl restart field-trainer-server.service

# DB-level: drop PYFP tables
python3 -c "
import sys; sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
db = DatabaseManager('/opt/data/field_trainer.db')
with db.get_connection() as conn:
    for t in ['pyfp_award','pyfp_cone_assignment','pyfp_event_result',
              'pyfp_assessment_battery','pyfp_scoring_table_version']:
        conn.execute(f'DROP TABLE IF EXISTS {t}')
    conn.execute(\"DELETE FROM courses WHERE course_type LIKE 'pyfp_%'\")
    conn.execute(\"DELETE FROM settings WHERE setting_key='default_landing'\")
"
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/pyfp/` returns 404 | Blueprint not registered | Check `coach_interface.py` imports `pyfp_bp` |
| Scoring returns `'unscored'` | No default scoring table | Run `UPDATE pyfp_scoring_table_version SET is_default=1 WHERE name='FitnessGram HFZ 2024'` |
| Mile run start fails 500 | Circular import in pyfp_mile_service | Ensure service uses `DatabaseManager(DB_PATH)`, not `from routes.pyfp_bp import db` |
| Cone touch not routing to mile/shuttle | PYFP dispatch not at top of `handle_touch_event` | Check `session_service.py` — PYFP block must precede the `session_id` check |
| PACER bridge 404 | No beep-test course in DB | Run `create_pyfp_courses.sql` to seed the `pyfp_pacer` course row |
