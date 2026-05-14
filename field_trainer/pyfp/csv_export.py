"""PYFP CSV export — wide (per-battery) and long (per-event) formats."""
import csv
import io

_BATTERY_COLS = [
    'battery_id', 'athlete_name', 'team_name', 'school_year', 'test_window',
    'rubric', 'age_at_test', 'gender', 'started_at', 'completed_at',
    'pyfp_pacer_laps',
    'pyfp_mile_run_seconds', 'pyfp_mile_walk_seconds',
    'pyfp_curl_up_reps', 'pyfp_push_up_reps',
    'pyfp_pull_up_reps', 'pyfp_modified_pull_up_reps',
    'pyfp_flexed_arm_hang_seconds', 'pyfp_plank_seconds',
    'pyfp_trunk_lift_inches', 'pyfp_sit_and_reach_inches',
    'pyfp_v_sit_reach_inches', 'pyfp_shoulder_stretch_score',
    'pyfp_shuttle_run_seconds', 'pyfp_bmi_value', 'pyfp_skinfold_pct',
    'hr_resting_bpm', 'hr_peak_bpm', 'hr_recovery_1min_bpm', 'hr_recovery_3min_bpm',
    'award_hfz_all_zones', 'award_pft_3_of_6', 'award_pft_full_6',
]

_CT_TO_COL = {
    'pyfp_pacer':            'pyfp_pacer_laps',
    'pyfp_mile_run':         'pyfp_mile_run_seconds',
    'pyfp_mile_walk':        'pyfp_mile_walk_seconds',
    'pyfp_curl_up':          'pyfp_curl_up_reps',
    'pyfp_push_up':          'pyfp_push_up_reps',
    'pyfp_pull_up':          'pyfp_pull_up_reps',
    'pyfp_modified_pull_up': 'pyfp_modified_pull_up_reps',
    'pyfp_flexed_arm_hang':  'pyfp_flexed_arm_hang_seconds',
    'pyfp_plank':            'pyfp_plank_seconds',
    'pyfp_trunk_lift':       'pyfp_trunk_lift_inches',
    'pyfp_sit_and_reach':    'pyfp_sit_and_reach_inches',
    'pyfp_v_sit_reach':      'pyfp_v_sit_reach_inches',
    'pyfp_shoulder_stretch': 'pyfp_shoulder_stretch_score',
    'pyfp_shuttle_run':      'pyfp_shuttle_run_seconds',
    'pyfp_bmi':              'pyfp_bmi_value',
    'pyfp_skinfold':         'pyfp_skinfold_pct',
}

_EVENT_COLS = [
    'event_result_id', 'battery_id', 'athlete_name', 'team_name',
    'school_year', 'test_window', 'rubric', 'age_at_test', 'gender',
    'course_type', 'raw_value', 'raw_unit',
    'attempt_number', 'is_best', 'recorded_at', 'notes',
    'hr_resting_bpm', 'hr_peak_bpm',
]


def batteries_csv(batteries: list, db) -> str:
    """Wide format — one row per battery."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_BATTERY_COLS, extrasaction='ignore')
    writer.writeheader()

    for bat in batteries:
        athlete = db.get_athlete(bat['athlete_id']) or {}
        team    = db.get_team(athlete.get('team_id', '')) or {}
        results = db.get_pyfp_event_results_for_battery(bat['battery_id'])
        awards  = db.get_pyfp_awards(bat['battery_id'])
        award_types = {a['award_type'] for a in awards}

        best: dict = {}
        for r in results:
            ct = r['course_type']
            if ct not in best or r['is_best']:
                best[ct] = r['raw_value']

        row: dict = {
            'battery_id':   bat['battery_id'],
            'athlete_name': athlete.get('name', ''),
            'team_name':    team.get('name', ''),
            'school_year':  bat['school_year'],
            'test_window':  bat['test_window'],
            'rubric':       bat['rubric'],
            'age_at_test':  bat['age_at_test'],
            'gender':       bat['gender'],
            'started_at':   bat.get('started_at', ''),
            'completed_at': bat.get('completed_at') or '',
            'hr_resting_bpm':       '',
            'hr_peak_bpm':          '',
            'hr_recovery_1min_bpm': '',
            'hr_recovery_3min_bpm': '',
            'award_hfz_all_zones': 1 if 'hfz_all_zones' in award_types else 0,
            'award_pft_3_of_6':    1 if 'pft_3_of_6'    in award_types else 0,
            'award_pft_full_6':    1 if 'pft_full_6'     in award_types else 0,
        }
        for ct, col in _CT_TO_COL.items():
            row[col] = best.get(ct, '')

        writer.writerow(row)

    return buf.getvalue()


def events_csv(batteries: list, db) -> str:
    """Long format — one row per event_result."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_EVENT_COLS, extrasaction='ignore')
    writer.writeheader()

    for bat in batteries:
        athlete = db.get_athlete(bat['athlete_id']) or {}
        team    = db.get_team(athlete.get('team_id', '')) or {}
        results = db.get_pyfp_event_results_for_battery(bat['battery_id'])

        for r in results:
            writer.writerow({
                'event_result_id': r['event_result_id'],
                'battery_id':      r['battery_id'],
                'athlete_name':    athlete.get('name', ''),
                'team_name':       team.get('name', ''),
                'school_year':     bat['school_year'],
                'test_window':     bat['test_window'],
                'rubric':          bat['rubric'],
                'age_at_test':     bat['age_at_test'],
                'gender':          bat['gender'],
                'course_type':     r['course_type'],
                'raw_value':       r['raw_value'],
                'raw_unit':        r['raw_unit'],
                'attempt_number':  r['attempt_number'],
                'is_best':         r['is_best'],
                'recorded_at':     r['recorded_at'],
                'notes':           r.get('notes', '') or '',
                'hr_resting_bpm':  '',
                'hr_peak_bpm':     '',
            })

    return buf.getvalue()
