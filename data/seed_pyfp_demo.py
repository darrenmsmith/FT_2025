#!/usr/bin/env python3
"""
PYFP demo seed — creates "PYFP Demo Class" with 25 athletes and synthetic
batteries covering all three rubrics (fitnessgram_hfz, pft_2026, both).

Idempotent: skips team/athlete/battery creation when records already exist.

Usage:
    python3 /opt/data/seed_pyfp_demo.py [--wipe]

--wipe: delete the PYFP Demo Class and all related data first (hard reset).
"""
import sys
import random
import argparse

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.pyfp.scoring import score_battery, _CACHE as SCORE_CACHE
from field_trainer.pyfp.awards import compute_and_write_awards

DB_PATH     = '/opt/data/field_trainer.db'
TEAM_NAME   = 'PYFP Demo Class'
SCHOOL_YEAR = '2025-2026'
WINDOW      = 'spring'
RNG         = random.Random(42)          # fixed seed for reproducibility

# 25 athletes: (name, age, gender, rubric, jersey)
ATHLETES = [
    # ---- fitnessgram_hfz (8) ----
    ('Aiden Brooks',      12, 'male',   'fitnessgram_hfz',  1),
    ('Bella Carter',      11, 'female', 'fitnessgram_hfz',  2),
    ('Carlos Diaz',       13, 'male',   'fitnessgram_hfz',  3),
    ('Diana Evans',       10, 'female', 'fitnessgram_hfz',  4),
    ('Ethan Foster',      14, 'male',   'fitnessgram_hfz',  5),
    ('Fiona Grant',       12, 'female', 'fitnessgram_hfz',  6),
    ('Gabriel Harris',    11, 'male',   'fitnessgram_hfz',  7),
    ('Hana Imai',         13, 'female', 'fitnessgram_hfz',  8),
    # ---- pft_2026 (9) ----
    ('Ivan Jones',        12, 'male',   'pft_2026',         9),
    ('Julia Kim',         11, 'female', 'pft_2026',        10),
    ('Kevin Lee',         13, 'male',   'pft_2026',        11),
    ('Laura Martinez',    10, 'female', 'pft_2026',        12),
    ('Mason Nelson',      14, 'male',   'pft_2026',        13),
    ('Nora Okafor',       12, 'female', 'pft_2026',        14),
    ('Oscar Patel',       11, 'male',   'pft_2026',        15),
    ('Priya Quinn',       13, 'female', 'pft_2026',        16),
    ('Rafael Rivera',     10, 'male',   'pft_2026',        17),
    # ---- both (8) ----
    ('Sophia Santos',     12, 'female', 'both',            18),
    ('Theo Turner',       11, 'male',   'both',            19),
    ('Uma Vargas',        13, 'female', 'both',            20),
    ('Victor Wang',       14, 'male',   'both',            21),
    ('Wendy Xavier',      10, 'female', 'both',            22),
    ('Xavier Young',      12, 'male',   'both',            23),
    ('Yara Zimmermann',   11, 'female', 'both',            24),
    ('Zack Anderson',     13, 'male',   'both',            25),
]

# Athletes (jersey numbers) whose battery stays incomplete (no data yet)
NOT_STARTED = {3, 14, 25}

# Athletes whose battery is partially complete (only some events recorded)
PARTIAL = {6, 10, 17, 22, 16}


def _hfz_value(course_type, age, gender) -> float | None:
    """Return a plausible in-HFZ raw value for the given event/age/gender."""
    m = gender == 'male'
    match course_type:
        case 'pyfp_pacer':
            base = {10: 28, 11: 30, 12: 38, 13: 48, 14: 55}[min(age, 14)]
            return float(RNG.randint(base - 5, base + 12) if m else RNG.randint(base - 8, base + 5))
        case 'pyfp_mile_run':
            base = {10: 560, 11: 530, 12: 500, 13: 470, 14: 440}[min(age, 14)]
            adj = -20 if m else 20
            return float(RNG.randint(base + adj - 40, base + adj + 40))
        case 'pyfp_mile_walk':
            base = {10: 750, 11: 720, 12: 690, 13: 660, 14: 630}[min(age, 14)]
            return float(RNG.randint(base - 30, base + 60))
        case 'pyfp_curl_up':
            base = {10: 18, 11: 21, 12: 25, 13: 28, 14: 30}[min(age, 14)]
            return float(RNG.randint(base - 3, base + 8))
        case 'pyfp_push_up':
            base = {10: 10, 11: 12, 12: 14, 13: 16, 14: 20}[min(age, 14)]
            adj = 4 if m else 0
            return float(RNG.randint(base + adj - 2, base + adj + 6))
        case 'pyfp_pull_up':
            base = {10: 3, 11: 3, 12: 5, 13: 7, 14: 8}[min(age, 14)]
            adj = 2 if m else -1
            return float(max(1, RNG.randint(base + adj - 1, base + adj + 3)))
        case 'pyfp_modified_pull_up':
            base = {10: 10, 11: 12, 12: 13, 13: 14, 14: 15}[min(age, 14)]
            return float(RNG.randint(base - 2, base + 4))
        case 'pyfp_flexed_arm_hang':
            base = {10: 12, 11: 14, 12: 16, 13: 20, 14: 22}[min(age, 14)]
            return float(RNG.randint(base - 3, base + 10))
        case 'pyfp_plank':
            base = {10: 55, 11: 60, 12: 65, 13: 70, 14: 75}[min(age, 14)]
            return float(RNG.randint(base - 10, base + 20))
        case 'pyfp_trunk_lift':
            return float(RNG.randint(9, 12))
        case 'pyfp_sit_and_reach':
            base = 10 if not m else 8
            return float(RNG.randint(base, base + 6))
        case 'pyfp_v_sit_reach':
            return float(RNG.randint(2, 8))
        case 'pyfp_shoulder_stretch':
            return 2.0    # both sides pass (in HFZ)
        case 'pyfp_shuttle_run':
            base = {10: 10.8, 11: 10.6, 12: 10.4, 13: 10.2, 14: 10.0}[min(age, 14)]
            adj = -0.3 if m else 0.2
            return round(RNG.uniform(base + adj - 0.5, base + adj + 0.5), 1)
        case 'pyfp_bmi':
            base = {10: 17.5, 11: 18.0, 12: 18.5, 13: 19.0, 14: 19.5}[min(age, 14)]
            return round(RNG.uniform(base - 1.5, base + 2.5), 1)
        case 'pyfp_skinfold':
            base = 18.0 if m else 24.0
            return round(RNG.uniform(base - 3, base + 5), 1)
    return None


def _raw_unit(course_type) -> str:
    units = {
        'pyfp_pacer': 'laps', 'pyfp_mile_run': 'seconds', 'pyfp_mile_walk': 'seconds',
        'pyfp_curl_up': 'reps', 'pyfp_push_up': 'reps', 'pyfp_pull_up': 'reps',
        'pyfp_modified_pull_up': 'reps', 'pyfp_flexed_arm_hang': 'seconds',
        'pyfp_plank': 'seconds', 'pyfp_trunk_lift': 'inches',
        'pyfp_sit_and_reach': 'inches', 'pyfp_v_sit_reach': 'inches',
        'pyfp_shoulder_stretch': 'pass_fail', 'pyfp_shuttle_run': 'seconds',
        'pyfp_bmi': 'bmi', 'pyfp_skinfold': 'percent',
    }
    return units.get(course_type, 'units')


def _metric_name(course_type) -> str:
    names = {
        'pyfp_pacer': 'pyfp_pacer_laps', 'pyfp_mile_run': 'pyfp_mile_run_seconds',
        'pyfp_mile_walk': 'pyfp_mile_walk_seconds', 'pyfp_curl_up': 'pyfp_curl_up_reps',
        'pyfp_push_up': 'pyfp_push_up_reps', 'pyfp_pull_up': 'pyfp_pull_up_reps',
        'pyfp_modified_pull_up': 'pyfp_modified_pull_up_reps',
        'pyfp_flexed_arm_hang': 'pyfp_flexed_arm_hang_seconds',
        'pyfp_plank': 'pyfp_plank_seconds', 'pyfp_trunk_lift': 'pyfp_trunk_lift_inches',
        'pyfp_sit_and_reach': 'pyfp_sit_and_reach_inches',
        'pyfp_v_sit_reach': 'pyfp_v_sit_reach_inches',
        'pyfp_shoulder_stretch': 'pyfp_shoulder_stretch_score',
        'pyfp_shuttle_run': 'pyfp_shuttle_run_seconds',
        'pyfp_bmi': 'pyfp_bmi_index', 'pyfp_skinfold': 'pyfp_skinfold_pct',
    }
    return names.get(course_type, course_type)


def _is_better_higher(course_type) -> bool:
    return course_type not in ('pyfp_mile_run', 'pyfp_mile_walk', 'pyfp_shuttle_run',
                                'pyfp_bmi', 'pyfp_skinfold')


def _get_course_id(db, course_type) -> int | None:
    courses = db.get_pyfp_courses()
    for c in courses:
        if c['course_type'] == course_type:
            return c['course_id']
    return None


def _events_for_rubric(rubric) -> list[str]:
    from field_trainer.pyfp.events_registry import events_for_rubric
    return events_for_rubric(rubric)


def wipe_demo(db):
    teams = db.get_all_teams()
    demo = next((t for t in teams if t['name'] == TEAM_NAME), None)
    if not demo:
        print("No demo team found — nothing to wipe.")
        return
    team_id = demo['team_id']
    athletes = db.get_athletes_by_team(team_id)
    with db.get_connection() as conn:
        for a in athletes:
            conn.execute("DELETE FROM athletes WHERE athlete_id=?", (a['athlete_id'],))
        conn.execute("DELETE FROM teams WHERE team_id=?", (team_id,))
    print(f"Wiped team {TEAM_NAME} and {len(athletes)} athletes.")


def seed(db):
    # 1 — find or create team
    teams = db.get_all_teams()
    demo_team = next((t for t in teams if t['name'] == TEAM_NAME), None)
    if demo_team:
        team_id = demo_team['team_id']
        print(f"Reusing existing team: {team_id}")
    else:
        team_id = db.create_team(TEAM_NAME, age_group='Middle School')
        print(f"Created team: {team_id}")

    existing_athletes = {a['name']: a for a in db.get_athletes_by_team(team_id)}

    for name, age, gender, rubric, jersey in ATHLETES:
        if name in existing_athletes:
            athlete_id = existing_athletes[name]['athlete_id']
            print(f"  skip athlete (exists): {name}")
        else:
            athlete_id = db.create_athlete(team_id, name, jersey_number=jersey, age=age)
            print(f"  created athlete: {name} (#{jersey}, age {age}, {gender})")

        if jersey in NOT_STARTED:
            print(f"    → no battery (not started)")
            continue

        # Find or create battery
        existing_bat = db.get_pyfp_battery_for_athlete_window(athlete_id, SCHOOL_YEAR, WINDOW)
        if existing_bat:
            battery_id = existing_bat['battery_id']
            print(f"    → battery exists: {battery_id}")
        else:
            battery_id = db.create_pyfp_battery(
                athlete_id=athlete_id,
                school_year=SCHOOL_YEAR,
                test_window=WINDOW,
                rubric=rubric,
                age_at_test=age,
                gender=gender,
            )
            print(f"    → created battery ({rubric})")

        # Decide which events to fill in
        all_events = _events_for_rubric(rubric)
        if jersey in PARTIAL:
            events_to_fill = RNG.sample(all_events, k=max(1, len(all_events) // 2))
            complete = False
        else:
            events_to_fill = all_events
            complete = True

        # Record event results (skip if already recorded for this battery)
        existing_results = {r['course_type'] for r in db.get_pyfp_event_results_for_battery(battery_id)}
        course_id_cache = {}

        for ct in events_to_fill:
            if ct in existing_results:
                continue
            val = _hfz_value(ct, age, gender)
            if val is None:
                continue
            unit = _raw_unit(ct)
            cid  = course_id_cache.setdefault(ct, _get_course_id(db, ct))

            db.create_pyfp_event_result(
                battery_id, ct, val, unit, attempt_number=1, is_best=1,
            )
            db.write_pyfp_performance_history(
                athlete_id=athlete_id,
                metric_name=_metric_name(ct),
                metric_value=val,
                metric_unit=unit,
                course_id=cid,
                notes=f"PYFP demo seed; battery {battery_id}",
                is_better_higher=_is_better_higher(ct),
            )

        # Complete battery and trigger scoring/awards
        if complete:
            bat = db.get_pyfp_battery(battery_id)
            if not bat['completed_at']:
                db.complete_pyfp_battery(battery_id)
                bat = db.get_pyfp_battery(battery_id)
                SCORE_CACHE.clear()
                results = db.get_pyfp_event_results_for_battery(battery_id)
                scores  = score_battery(bat, results, db)
                awarded = compute_and_write_awards(bat, scores, db)
                if awarded:
                    print(f"      awards: {awarded}")
                else:
                    print(f"      complete (no awards)")
            else:
                print(f"      already complete")

    print("\nSeed complete.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wipe', action='store_true', help='Delete demo team and re-seed')
    args = parser.parse_args()

    db = DatabaseManager(DB_PATH)
    if args.wipe:
        wipe_demo(db)
    seed(db)
