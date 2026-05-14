import json
import math
import sys
from datetime import date, datetime
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

sys.path.insert(0, '/opt')
from field_trainer.db_manager import DatabaseManager
from field_trainer.pyfp.events_registry import EVENTS, events_for_rubric

pyfp_bp = Blueprint("pyfp", __name__)
db = DatabaseManager('/opt/data/field_trainer.db')

RUBRIC_LABELS = {
    'fitnessgram_hfz': 'FitnessGram HFZ',
    'pft_2026':        'PFT 2026',
    'both':            'Both (HFZ + PFT)',
}

CATEGORY_ORDER = ['aerobic', 'core', 'upper', 'trunk', 'flexibility', 'agility', 'body_comp']
CATEGORY_LABELS = {
    'aerobic':     'Aerobic Capacity',
    'core':        'Core Strength',
    'upper':       'Upper Body',
    'trunk':       'Trunk Strength',
    'flexibility': 'Flexibility',
    'agility':     'Agility',
    'body_comp':   'Body Composition',
}


def _current_school_year() -> str:
    today = date.today()
    y = today.year if today.month >= 8 else today.year - 1
    return f"{y}-{y + 1}"


def _current_test_window() -> str:
    return 'fall' if date.today().month >= 8 else 'spring'


def _school_year_options() -> list[str]:
    today = date.today()
    y = today.year if today.month >= 8 else today.year - 1
    return [f"{y - 1}-{y}", f"{y}-{y + 1}"]


def _profile_ok(athlete: dict) -> bool:
    """Return True if the athlete record has the data needed for PYFP battery creation."""
    age = athlete.get('age')
    gender = (athlete.get('gender') or '').strip().lower()
    return bool(age) and gender in ('male', 'female')


def _build_event_grid(battery: dict, results: list[dict], pyfp_courses: dict) -> list[dict]:
    """Return categories list with event cards for the template."""
    done_types = {r['course_type'] for r in results}
    event_keys = events_for_rubric(battery['rubric'])

    cats: dict[str, list] = {}
    for key in event_keys:
        cat = EVENTS[key]['category']
        cats.setdefault(cat, [])
        course = pyfp_courses.get(key, {})
        raw_name = course.get('course_name', key)
        display_name = raw_name.replace('PYFP - ', '')
        cats[cat].append({
            'course_type': key,
            'name': display_name,
            'engine': EVENTS[key]['engine'],
            'done': key in done_types,
        })

    grid = []
    for cat in CATEGORY_ORDER:
        if cat in cats:
            grid.append({
                'category': cat,
                'label': CATEGORY_LABELS[cat],
                'events': cats[cat],
            })
    return grid


# ==================== UI ROUTES ====================

@pyfp_bp.route('/pyfp/healthz')
def healthz():
    return jsonify({"ok": True})


@pyfp_bp.route('/pyfp/')
def dashboard():
    teams = db.get_all_teams()
    team_id = request.args.get('team_id')
    school_year = request.args.get('school_year', _current_school_year())
    test_window = request.args.get('test_window', _current_test_window())

    selected_team = None
    athlete_rows = []

    if team_id:
        selected_team = db.get_team(team_id)
        if selected_team:
            athletes = db.get_athletes_by_team(team_id)
            batteries_by_athlete = {
                b['athlete_id']: b
                for b in db.get_pyfp_team_batteries(team_id, school_year, test_window)
            }
            pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}

            for athlete in athletes:
                battery = batteries_by_athlete.get(athlete['athlete_id'])
                events_done = 0
                events_total = 0
                pct = 0
                if battery:
                    results = db.get_pyfp_event_results_for_battery(battery['battery_id'])
                    event_keys = events_for_rubric(battery['rubric'])
                    done_types = {r['course_type'] for r in results}
                    events_done = len(done_types)
                    events_total = len(event_keys)
                    pct = round(100 * events_done / events_total) if events_total else 0
                athlete_rows.append({
                    'athlete': athlete,
                    'battery': battery,
                    'events_done': events_done,
                    'events_total': events_total,
                    'pct': pct,
                    'profile_ok': _profile_ok(athlete),
                })

    complete_count = sum(1 for r in athlete_rows if r.get('battery') and r['battery']['completed_at'])

    # Event name lists per rubric for the battery-picker UI
    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    event_lists = {
        rubric: [
            pyfp_courses.get(k, {}).get('course_name', k).replace('PYFP - ', '')
            for k in events_for_rubric(rubric)
        ]
        for rubric in ('pft_2026', 'fitnessgram_hfz', 'both')
    }

    return render_template(
        'pyfp_dashboard.html',
        teams=teams,
        selected_team=selected_team,
        athlete_rows=athlete_rows,
        school_year=school_year,
        test_window=test_window,
        school_year_options=_school_year_options(),
        rubric_labels=RUBRIC_LABELS,
        complete_count=complete_count,
        event_lists=event_lists,
    )


@pyfp_bp.route('/pyfp/team/<team_id>')
def team_view(team_id):
    return redirect(url_for('pyfp.dashboard', team_id=team_id))


@pyfp_bp.route('/pyfp/athlete/<athlete_id>')
def athlete_view(athlete_id):
    athlete = db.get_athlete(athlete_id)
    if not athlete:
        return "Athlete not found", 404

    school_year = request.args.get('school_year', _current_school_year())
    test_window = request.args.get('test_window', _current_test_window())

    battery = db.get_pyfp_battery_for_athlete_window(athlete_id, school_year, test_window)
    all_batteries = db.get_pyfp_batteries_for_athlete(athlete_id)
    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}

    event_grid = []
    results = []
    if battery:
        results = db.get_pyfp_event_results_for_battery(battery['battery_id'])
        event_grid = _build_event_grid(battery, results, pyfp_courses)

    # Compute age from birthdate if age field is null
    age_hint = athlete.get('age')
    if not age_hint and athlete.get('birthdate'):
        try:
            bd = date.fromisoformat(athlete['birthdate'])
            today = date.today()
            age_hint = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        except ValueError:
            pass

    return render_template(
        'pyfp_athlete.html',
        athlete=athlete,
        battery=battery,
        all_batteries=all_batteries,
        event_grid=event_grid,
        results=results,
        school_year=school_year,
        test_window=test_window,
        school_year_options=_school_year_options(),
        rubric_labels=RUBRIC_LABELS,
        age_hint=age_hint,
        category_labels=CATEGORY_LABELS,
    )


# ==================== API ROUTES ====================

@pyfp_bp.route('/api/pyfp/battery/start', methods=['POST'])
def battery_start():
    data = request.get_json(force=True)
    athlete_id  = data.get('athlete_id', '').strip()
    school_year = data.get('school_year', '').strip()
    test_window = data.get('test_window', '').strip()
    rubric      = data.get('rubric', '').strip()
    age_at_test = data.get('age_at_test')
    gender      = data.get('gender', '').strip().lower()

    if not all([athlete_id, school_year, test_window, rubric, age_at_test, gender]):
        return jsonify({'error': 'Missing required fields'}), 400
    if test_window not in ('fall', 'spring'):
        return jsonify({'error': 'test_window must be fall or spring'}), 400
    if rubric not in ('fitnessgram_hfz', 'pft_2026', 'both'):
        return jsonify({'error': 'Invalid rubric'}), 400
    if gender not in ('male', 'female'):
        return jsonify({'error': 'gender must be male or female'}), 400

    existing = db.get_pyfp_battery_for_athlete_window(athlete_id, school_year, test_window)
    if existing:
        return jsonify({'battery_id': existing['battery_id'], 'created': False})

    battery_id = db.create_pyfp_battery(
        athlete_id=athlete_id,
        school_year=school_year,
        test_window=test_window,
        rubric=rubric,
        age_at_test=int(age_at_test),
        gender=gender,
    )
    return jsonify({'battery_id': battery_id, 'created': True}), 201


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/status')
def battery_status(battery_id):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404

    results = db.get_pyfp_event_results_for_battery(battery_id)
    event_keys = events_for_rubric(battery['rubric'])
    done_types = {r['course_type'] for r in results}

    return jsonify({
        'battery': battery,
        'events_total': len(event_keys),
        'events_done': len(done_types),
        'done_types': list(done_types),
        'is_complete': battery['completed_at'] is not None,
    })


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/complete', methods=['POST'])
def battery_complete(battery_id):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    if battery['completed_at']:
        return jsonify({'ok': True, 'already_complete': True,
                        'awards': [a['award_type'] for a in db.get_pyfp_awards(battery_id)]})
    db.complete_pyfp_battery(battery_id)
    battery = db.get_pyfp_battery(battery_id)

    try:
        from field_trainer.pyfp.scoring import score_battery
        from field_trainer.pyfp.awards import compute_and_write_awards
        results = db.get_pyfp_event_results_for_battery(battery_id)
        scores  = score_battery(battery, results, db)
        awarded = compute_and_write_awards(battery, scores, db)
    except Exception as e:
        print(f"[PYFP] scoring/awards error: {e}")
        awarded = []

    return jsonify({'ok': True, 'already_complete': False, 'awards': awarded})


@pyfp_bp.route('/api/pyfp/team/<team_id>/battery/start-all', methods=['POST'])
def team_battery_start_all(team_id):
    """Batch-create batteries for every athlete in the team who has age + gender set."""
    data        = request.get_json(force=True) or {}
    school_year = data.get('school_year', _current_school_year())
    test_window = data.get('test_window', _current_test_window())
    rubric      = data.get('rubric', 'fitnessgram_hfz')

    if rubric not in ('fitnessgram_hfz', 'pft_2026', 'both'):
        return jsonify({'error': 'Invalid rubric'}), 400

    athletes = db.get_athletes_by_team(team_id)
    created = existing = skipped = 0
    skipped_names: list[str] = []

    for athlete in athletes:
        if not _profile_ok(athlete):
            skipped += 1
            skipped_names.append(athlete['name'])
            continue

        if db.get_pyfp_battery_for_athlete_window(
                athlete['athlete_id'], school_year, test_window):
            existing += 1
            continue

        gender = athlete['gender'].strip().lower()
        db.create_pyfp_battery(
            athlete_id=athlete['athlete_id'],
            school_year=school_year,
            test_window=test_window,
            rubric=rubric,
            age_at_test=int(athlete['age']),
            gender=gender,
        )
        created += 1

    return jsonify({
        'ok': True,
        'created': created,
        'existing': existing,
        'skipped': skipped,
        'skipped_names': skipped_names,
    })


# ==================== PHASE 3 — MANUAL EVENT RECORDING ====================

# Engines available for recording (expanded each phase)
_RECORDABLE_ENGINES = {'manual_count', 'manual_measure', 'manual_passfail',  # Phase 3
                       'cadence', 'timer'}                                    # Phase 5

# metric_name suffix and unit per course_type for performance_history
_METRIC = {
    # Phase 3 — manual engines
    'pyfp_pull_up':          ('pyfp_pull_up_reps',             'reps',      True),
    'pyfp_modified_pull_up': ('pyfp_modified_pull_up_reps',    'reps',      True),
    'pyfp_trunk_lift':       ('pyfp_trunk_lift_inches',         'inches',    True),
    'pyfp_sit_and_reach':    ('pyfp_sit_and_reach_inches',      'inches',    True),
    'pyfp_v_sit_reach':      ('pyfp_v_sit_reach_inches',        'inches',    True),
    'pyfp_shoulder_stretch': ('pyfp_shoulder_stretch_score',    'pass_fail', True),
    'pyfp_bmi':              ('pyfp_bmi_index',                 'bmi',       False),
    'pyfp_skinfold':         ('pyfp_skinfold_pct',              'percent',   False),
    # Phase 5 — cadence + timer engines
    'pyfp_curl_up':          ('pyfp_curl_up_reps',              'reps',      True),
    'pyfp_push_up':          ('pyfp_push_up_reps',              'reps',      True),
    'pyfp_flexed_arm_hang':  ('pyfp_flexed_arm_hang_seconds',   'seconds',   True),
    'pyfp_plank':            ('pyfp_plank_seconds',             'seconds',   True),
}


def _get_course_id(course_type: str) -> int | None:
    courses = db.get_pyfp_courses()
    for c in courses:
        if c['course_type'] == course_type:
            return c['course_id']
    return None


def _slaughter_pct_body_fat(triceps_mm: float, calf_mm: float, gender: str) -> float:
    total = triceps_mm + calf_mm
    if gender == 'male':
        return round(0.735 * total + 1.0, 1)
    return round(0.610 * total + 5.1, 1)


@pyfp_bp.route('/pyfp/battery/<battery_id>/event/<course_type>/record')
def event_record_form(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return "Battery not found", 404
    athlete = db.get_athlete(battery['athlete_id'])
    if not athlete:
        return "Athlete not found", 404

    if course_type not in EVENTS:
        return "Unknown event", 404

    engine = EVENTS[course_type]['engine']

    # Cone-based events redirect to the cone picker flow
    if engine in ('mile_service', 'shuttle_service'):
        return redirect(url_for('pyfp.cone_picker',
                                battery_id=battery_id, course_type=course_type))

    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    course = pyfp_courses.get(course_type, {})
    display_name = course.get('course_name', course_type).replace('PYFP - ', '')

    existing_results = db.get_pyfp_event_results_for_battery(battery['battery_id'])
    event_results = [r for r in existing_results if r['course_type'] == course_type]

    return render_template(
        'pyfp_event_record.html',
        battery=battery,
        athlete=athlete,
        course_type=course_type,
        engine=engine,
        display_name=display_name,
        event_results=event_results,
        phase3_available=(engine in _RECORDABLE_ENGINES),
    )


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/event/<course_type>/record', methods=['POST'])
def event_record_submit(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    if battery['completed_at']:
        return jsonify({'error': 'Battery is already completed'}), 409
    if course_type not in EVENTS:
        return jsonify({'error': 'Unknown event'}), 404

    engine = EVENTS[course_type]['engine']
    if engine not in _RECORDABLE_ENGINES:
        return jsonify({'error': f'Engine {engine!r} not yet available'}), 422

    data = request.get_json(force=True)
    metric_name, metric_unit, is_better_higher = _METRIC.get(
        course_type, (course_type, 'units', True)
    )
    course_id = _get_course_id(course_type)
    athlete_id = battery['athlete_id']
    perf_notes = f"PYFP battery {battery_id}"

    # ---- manual_count: pull_up, modified_pull_up ----
    if engine == 'manual_count':
        count = data.get('count')
        if count is None:
            return jsonify({'error': 'count required'}), 400
        count = int(count)
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, float(count), 'reps',
            attempt_number=1, is_best=1,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, float(count), metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=True,
        )
        return jsonify({'ok': True, 'event_result_id': result_id})

    # ---- manual_passfail: shoulder_stretch ----
    if engine == 'manual_passfail':
        right = 1 if data.get('right_pass') else 0
        left  = 1 if data.get('left_pass')  else 0
        score = float(right + left)  # 0, 1, or 2
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, score, 'pass_fail',
            attempt_number=1, is_best=1, secondary_value=float(left),
            notes=json.dumps({'right': right, 'left': left}),
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, score, metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=True,
        )
        return jsonify({'ok': True, 'event_result_id': result_id})

    # ---- manual_measure: trunk_lift ----
    if course_type == 'pyfp_trunk_lift':
        inches = data.get('inches')
        if inches is None:
            return jsonify({'error': 'inches required'}), 400
        inches = min(float(inches), 12.0)
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, inches, 'inches',
            attempt_number=1, is_best=1,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, inches, metric_unit,
            course_id=course_id, notes=perf_notes,
        )
        return jsonify({'ok': True, 'event_result_id': result_id})

    # ---- manual_measure: sit_and_reach (best per side — right + left) ----
    if course_type == 'pyfp_sit_and_reach':
        right = data.get('right_inches')
        left  = data.get('left_inches')
        if right is None:
            return jsonify({'error': 'right_inches required'}), 400
        right = float(right)
        left  = float(left) if left is not None else None
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, right, 'inches',
            attempt_number=1, is_best=1,
            secondary_value=left,
            notes=json.dumps({'right_inches': right, 'left_inches': left}),
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, right, metric_unit,
            course_id=course_id, notes=perf_notes,
        )
        return jsonify({'ok': True, 'event_result_id': result_id})

    # ---- manual_measure: v_sit_reach (up to 3 attempts, best marked) ----
    if course_type == 'pyfp_v_sit_reach':
        raw_attempts = data.get('attempts', [])
        if not raw_attempts:
            return jsonify({'error': 'attempts list required'}), 400
        attempts = [float(v) for v in raw_attempts if v != '' and v is not None]
        if not attempts:
            return jsonify({'error': 'At least one attempt value required'}), 400
        result_ids = []
        for i, val in enumerate(attempts[:3], start=1):
            result_ids.append(db.create_pyfp_event_result(
                battery_id, course_type, val, 'inches',
                attempt_number=i, is_best=0,
            ))
        db.recompute_pyfp_best(battery_id, course_type, is_better_higher=True)
        best_val = max(attempts)
        db.write_pyfp_performance_history(
            athlete_id, metric_name, best_val, metric_unit,
            course_id=course_id, notes=perf_notes,
        )
        return jsonify({'ok': True, 'event_result_ids': result_ids})

    # ---- manual_measure: bmi ----
    if course_type == 'pyfp_bmi':
        height_ft  = data.get('height_ft', 0)
        height_in  = data.get('height_in', 0)
        weight_lbs = data.get('weight_lbs')
        if weight_lbs is None:
            return jsonify({'error': 'weight_lbs required'}), 400
        total_in = float(height_ft) * 12 + float(height_in)
        if total_in <= 0:
            return jsonify({'error': 'height must be > 0'}), 400
        bmi = round((float(weight_lbs) * 703) / (total_in ** 2), 1)
        bmi_notes = json.dumps({
            'height_ft': height_ft, 'height_in': height_in,
            'weight_lbs': weight_lbs, 'total_height_in': total_in,
        })
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, bmi, 'bmi',
            attempt_number=1, is_best=1,
            secondary_value=float(weight_lbs), notes=bmi_notes,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, bmi, metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=False,
        )
        return jsonify({'ok': True, 'event_result_id': result_id, 'bmi': bmi})

    # ---- manual_measure: skinfold ----
    if course_type == 'pyfp_skinfold':
        triceps = data.get('triceps_mm')
        calf    = data.get('calf_mm')
        if triceps is None or calf is None:
            return jsonify({'error': 'triceps_mm and calf_mm required'}), 400
        gender = battery['gender']
        pct_bf = _slaughter_pct_body_fat(float(triceps), float(calf), gender)
        skinfold_notes = json.dumps({'triceps_mm': triceps, 'calf_mm': calf, 'gender': gender})
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, pct_bf, 'percent',
            attempt_number=1, is_best=1,
            secondary_value=float(triceps) + float(calf), notes=skinfold_notes,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, pct_bf, metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=False,
        )
        return jsonify({'ok': True, 'event_result_id': result_id, 'pct_body_fat': pct_bf})

    # ---- cadence engine: curl_up, push_up ----
    if engine == 'cadence':
        count = data.get('count')
        if count is None:
            return jsonify({'error': 'count required'}), 400
        count = int(count)
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, float(count), 'reps',
            attempt_number=1, is_best=1,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, float(count), metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=True,
        )
        return jsonify({'ok': True, 'event_result_id': result_id})

    # ---- timer engine: flexed_arm_hang, plank ----
    if engine == 'timer':
        duration = data.get('duration_seconds')
        if duration is None:
            return jsonify({'error': 'duration_seconds required'}), 400
        duration = round(float(duration), 1)
        result_id = db.create_pyfp_event_result(
            battery_id, course_type, duration, 'seconds',
            attempt_number=1, is_best=1,
        )
        db.write_pyfp_performance_history(
            athlete_id, metric_name, duration, metric_unit,
            course_id=course_id, notes=perf_notes, is_better_higher=True,
        )
        return jsonify({'ok': True, 'event_result_id': result_id, 'duration_seconds': duration})

    return jsonify({'error': 'Unhandled engine'}), 500


# ==================== PHASE 5 — SERVER AUDIO ====================

@pyfp_bp.route('/api/pyfp/audio/play', methods=['POST'])
def audio_play():
    """Fire a single audio clip on D0 via REGISTRY._audio (non-blocking)."""
    try:
        from field_trainer.ft_registry import REGISTRY
        data = request.get_json(force=True) or {}
        clip = data.get('clip', 'default_beep')
        if REGISTRY._audio:
            ok = REGISTRY._audio.play(clip)
            return jsonify({'ok': ok, 'clip': clip})
        return jsonify({'ok': False, 'reason': 'AudioManager not available'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ==================== PHASE 6 — CONE-BASED MILE + SHUTTLE ====================

_CONE_EVENTS = {'pyfp_mile_run', 'pyfp_mile_walk', 'pyfp_shuttle_run'}

_IP_TO_LABEL = {
    '192.168.99.100': 'Cone 0 — 192.168.99.100',
    '192.168.99.101': 'Cone 1',
    '192.168.99.102': 'Cone 2',
    '192.168.99.103': 'Cone 3',
    '192.168.99.104': 'Cone 4',
    '192.168.99.105': 'Cone 5',
}


def _online_cones(include_d0: bool = False) -> list[dict]:
    """Return online field cones with human-readable labels.

    D0 (192.168.99.100) does not self-register in the REGISTRY snapshot, so
    when include_d0=True it is prepended explicitly as a static entry.
    """
    try:
        from field_trainer.ft_registry import REGISTRY
        snap = REGISTRY.snapshot()
        results = []
        for n in snap.get('nodes', []):
            ip = n.get('ip', '')
            if not ip.startswith('192.168.99.1') or ip == '192.168.99.100':
                continue
            results.append({**n, 'label': _IP_TO_LABEL.get(ip, ip)})
        results.sort(key=lambda x: x.get('ip', ''))
    except Exception:
        results = []

    if include_d0:
        d0 = {'ip': '192.168.99.100', 'node_id': '192.168.99.100',
               'status': 'online', 'label': _IP_TO_LABEL['192.168.99.100']}
        results = [d0] + results

    return results


@pyfp_bp.route('/pyfp/battery/<battery_id>/event/<course_type>/cones')
def cone_picker(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return "Battery not found", 404
    athlete = db.get_athlete(battery['athlete_id'])
    if course_type not in _CONE_EVENTS:
        return "Not a cone-based event", 400

    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    course = pyfp_courses.get(course_type, {})
    display_name = course.get('course_name', course_type).replace('PYFP - ', '')

    # Existing cone assignment for this battery + course_type (if any)
    existing_results = [r for r in db.get_pyfp_event_results_for_battery(battery_id)
                        if r['course_type'] == course_type]
    existing_cones = []
    if existing_results:
        with db.get_connection() as conn:
            existing_cones = [dict(r) for r in conn.execute(
                "SELECT * FROM pyfp_cone_assignment WHERE event_result_id=?",
                (existing_results[0]['event_result_id'],)
            ).fetchall()]

    return render_template(
        'pyfp_cone_picker.html',
        battery=battery,
        athlete=athlete,
        course_type=course_type,
        display_name=display_name,
        online_cones=_online_cones(include_d0=course_type in ('pyfp_mile_run', 'pyfp_mile_walk')),
        existing_cones={c['role']: c for c in existing_cones},
    )


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/event/<course_type>/cones', methods=['POST'])
def cone_assignment_save(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    if battery['completed_at']:
        return jsonify({'error': 'Battery already completed'}), 409
    if course_type not in _CONE_EVENTS:
        return jsonify({'error': 'Not a cone-based event'}), 400

    data = request.get_json(force=True)

    if course_type in ('pyfp_mile_run', 'pyfp_mile_walk'):
        start_finish = data.get('start_finish', '').strip()
        if not start_finish:
            return jsonify({'error': 'start_finish cone is required'}), 400
        roles = {'start_finish': start_finish}
        lm = data.get('lap_marker', '').strip()
        if lm:
            roles['lap_marker'] = lm
    elif course_type == 'pyfp_shuttle_run':
        ep_a = data.get('endpoint_a', '').strip()
        ep_b = data.get('endpoint_b', '').strip()
        if not ep_a or not ep_b:
            return jsonify({'error': 'Both endpoint_a and endpoint_b are required'}), 400
        if ep_a == ep_b:
            return jsonify({'error': 'endpoint_a and endpoint_b must be different'}), 400
        roles = {'endpoint_a': ep_a, 'endpoint_b': ep_b}
    else:
        return jsonify({'error': 'Unsupported event'}), 400

    # Persist to pyfp_cone_assignment (linked to a placeholder event_result)
    existing = [r for r in db.get_pyfp_event_results_for_battery(battery_id)
                if r['course_type'] == course_type]
    if not existing:
        event_result_id = db.create_pyfp_event_result(
            battery_id=battery_id, course_type=course_type,
            raw_value=0.0, raw_unit='seconds',
            attempt_number=1, is_best=0, notes='cone_assignment_pending',
        )
    else:
        event_result_id = existing[0]['event_result_id']

    with db.get_connection() as conn:
        conn.execute("DELETE FROM pyfp_cone_assignment WHERE event_result_id=?", (event_result_id,))
        for role, device_id in roles.items():
            conn.execute(
                "INSERT INTO pyfp_cone_assignment (event_result_id, role, device_id) VALUES (?,?,?)",
                (event_result_id, role, device_id),
            )

    return jsonify({'ok': True, 'event_result_id': event_result_id, 'roles': roles})


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/event/<course_type>/run/start', methods=['POST'])
def run_start(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    if battery['completed_at']:
        return jsonify({'error': 'Battery already completed'}), 409

    # Load cone assignment
    existing = [r for r in db.get_pyfp_event_results_for_battery(battery_id)
                if r['course_type'] == course_type]
    if not existing:
        return jsonify({'error': 'No cone assignment found — pick cones first'}), 400

    event_result_id = existing[0]['event_result_id']
    with db.get_connection() as conn:
        cones = {r['role']: r['device_id'] for r in conn.execute(
            "SELECT role, device_id FROM pyfp_cone_assignment WHERE event_result_id=?",
            (event_result_id,)
        ).fetchall()}

    data = request.get_json(force=True) or {}

    if course_type in ('pyfp_mile_run', 'pyfp_mile_walk'):
        sf = cones.get('start_finish')
        if not sf:
            return jsonify({'error': 'start_finish cone not assigned'}), 400
        lm = cones.get('lap_marker')
        target_laps = int(data.get('target_laps', 4))
        from services.pyfp_mile_service import get_pyfp_mile_service
        result = get_pyfp_mile_service().start(
            battery_id=battery_id, course_type=course_type,
            start_finish_cone_id=sf, target_laps=target_laps,
            lap_marker_cone_id=lm,
        )
    elif course_type == 'pyfp_shuttle_run':
        ep_a = cones.get('endpoint_a')
        ep_b = cones.get('endpoint_b')
        if not ep_a or not ep_b:
            return jsonify({'error': 'Both endpoint cones must be assigned'}), 400
        from services.pyfp_shuttle_service import get_pyfp_shuttle_service
        result = get_pyfp_shuttle_service().start(
            battery_id=battery_id, endpoint_a=ep_a, endpoint_b=ep_b,
        )
    else:
        return jsonify({'error': 'Not a cone-based event'}), 400

    if not result.get('ok'):
        return jsonify(result), 409
    return jsonify(result), 201


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/event/<course_type>/run/status')
def run_status(battery_id, course_type):
    if course_type in ('pyfp_mile_run', 'pyfp_mile_walk'):
        from services.pyfp_mile_service import get_pyfp_mile_service
        status = get_pyfp_mile_service().get_status()
        active_for = status.get('battery_id') == battery_id
    elif course_type == 'pyfp_shuttle_run':
        from services.pyfp_shuttle_service import get_pyfp_shuttle_service
        status = get_pyfp_shuttle_service().get_status()
        active_for = status.get('battery_id') == battery_id
    else:
        return jsonify({'error': 'Not a cone-based event'}), 400

    if not active_for:
        # Check completed event result
        results = [r for r in db.get_pyfp_event_results_for_battery(battery_id)
                   if r['course_type'] == course_type]
        if results and results[0]['raw_value'] > 0:
            return jsonify({'status': 'done', 'result': results[0]})
        return jsonify({'status': 'idle'})

    return jsonify({'status': status.get('status', 'unknown'), 'state': status})


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/event/<course_type>/run/abort', methods=['POST'])
def run_abort(battery_id, course_type):
    if course_type in ('pyfp_mile_run', 'pyfp_mile_walk'):
        from services.pyfp_mile_service import get_pyfp_mile_service
        get_pyfp_mile_service().abort()
    elif course_type == 'pyfp_shuttle_run':
        from services.pyfp_shuttle_service import get_pyfp_shuttle_service
        get_pyfp_shuttle_service().abort()
    return jsonify({'ok': True})


@pyfp_bp.route('/pyfp/battery/<battery_id>/event/<course_type>/monitor')
def run_monitor(battery_id, course_type):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return "Battery not found", 404
    athlete = db.get_athlete(battery['athlete_id'])
    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    course = pyfp_courses.get(course_type, {})
    display_name = course.get('course_name', course_type).replace('PYFP - ', '')
    return render_template(
        'pyfp_run_monitor.html',
        battery=battery, athlete=athlete,
        course_type=course_type, display_name=display_name,
    )


# Debug: simulate a touch event via REGISTRY (for testing without hardware)
@pyfp_bp.route('/api/pyfp/debug/touch', methods=['POST'])
def debug_touch():
    data = request.get_json(force=True) or {}
    device_id = data.get('device_id', '192.168.99.101')
    from datetime import datetime as dt
    from field_trainer.ft_registry import REGISTRY
    # REGISTRY._touch_handler is session_service.handle_touch_event (set at startup)
    if REGISTRY._touch_handler:
        REGISTRY._touch_handler(device_id, dt.utcnow())
        return jsonify({'ok': True, 'device_id': device_id})
    return jsonify({'ok': False, 'error': 'No touch handler registered'}), 503


# ==================== PHASE 4 — PACER BRIDGE ====================

@pyfp_bp.route('/api/pyfp/battery/<battery_id>/pacer/start', methods=['POST'])
def pacer_start(battery_id):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    if battery['completed_at']:
        return jsonify({'error': 'Battery already completed'}), 409
    data = request.get_json(force=True) or {}
    start_level = max(1, min(21, int(data.get('start_level', 1))))
    try:
        from field_trainer.pyfp.pacer_bridge import start_pacer
        result = start_pacer(battery_id, start_level=start_level)
        return jsonify(result), 200 if not result['created'] else 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@pyfp_bp.route('/api/pyfp/battery/<battery_id>/pacer/import', methods=['POST'])
def pacer_import(battery_id):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return jsonify({'error': 'Battery not found'}), 404
    try:
        from field_trainer.pyfp.pacer_bridge import import_pacer_result
        result = import_pacer_result(battery_id)
        return jsonify({'ok': True, **result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== PHASE 7 — SCORING, AWARDS, REPORTS ====================

def _get_filtered_batteries(team_id: str | None, school_year: str, test_window: str) -> list[dict]:
    """Return batteries matching the filter across all teams or one team."""
    if team_id:
        return db.get_pyfp_team_batteries(team_id, school_year, test_window)
    teams = db.get_all_teams()
    batteries = []
    for team in teams:
        batteries.extend(db.get_pyfp_team_batteries(team['team_id'], school_year, test_window))
    return batteries


@pyfp_bp.route('/pyfp/battery/<battery_id>/report')
def battery_report(battery_id):
    battery = db.get_pyfp_battery(battery_id)
    if not battery:
        return "Battery not found", 404
    athlete = db.get_athlete(battery['athlete_id'])
    if not athlete:
        return "Athlete not found", 404

    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}
    results      = db.get_pyfp_event_results_for_battery(battery_id)
    awards       = db.get_pyfp_awards(battery_id)
    event_grid   = _build_event_grid(battery, results, pyfp_courses)

    # Best result per course_type for display
    results_by_type: dict = {}
    for r in results:
        ct = r['course_type']
        if ct not in results_by_type or r['is_best']:
            results_by_type[ct] = r

    from field_trainer.pyfp.scoring import score_battery
    scores = score_battery(battery, results, db)

    return render_template(
        'pyfp_battery_summary.html',
        battery=battery,
        athlete=athlete,
        event_grid=event_grid,
        results_by_type=results_by_type,
        awards=awards,
        scores=scores,
        rubric_labels=RUBRIC_LABELS,
    )


@pyfp_bp.route('/pyfp/reports')
def reports_page():
    teams       = db.get_all_teams()
    team_id     = request.args.get('team_id', '').strip() or None
    school_year = request.args.get('school_year', _current_school_year())
    test_window = request.args.get('test_window', _current_test_window())

    selected_team = db.get_team(team_id) if team_id else None
    batteries     = _get_filtered_batteries(team_id, school_year, test_window)
    batteries_by_athlete = {b['athlete_id']: b for b in batteries}

    athlete_rows = []
    complete_count = 0
    pyfp_courses = {c['course_type']: c for c in db.get_pyfp_courses()}

    athletes_to_show = (
        db.get_athletes_by_team(team_id)
        if team_id else
        [a for t in db.get_all_teams() for a in db.get_athletes_by_team(t['team_id'])]
    )

    for athlete in athletes_to_show:
        battery = batteries_by_athlete.get(athlete['athlete_id'])
        events_done = events_total = pct = 0
        row_awards = []
        if battery:
            results     = db.get_pyfp_event_results_for_battery(battery['battery_id'])
            event_keys  = events_for_rubric(battery['rubric'])
            done_types  = {r['course_type'] for r in results}
            events_done = len(done_types)
            events_total = len(event_keys)
            pct         = round(100 * events_done / events_total) if events_total else 0
            row_awards  = db.get_pyfp_awards(battery['battery_id'])
            if battery['completed_at']:
                complete_count += 1
        athlete_rows.append({
            'athlete': athlete,
            'battery': battery,
            'events_done': events_done,
            'events_total': events_total,
            'pct': pct,
            'awards': row_awards,
        })

    qs_parts = []
    if team_id:     qs_parts.append(f'team_id={team_id}')
    qs_parts += [f'school_year={school_year}', f'test_window={test_window}']
    csv_qs = '&'.join(qs_parts)

    return render_template(
        'pyfp_reports.html',
        teams=teams,
        selected_team=selected_team,
        athlete_rows=athlete_rows,
        complete_count=complete_count,
        school_year=school_year,
        test_window=test_window,
        school_year_options=_school_year_options(),
        rubric_labels=RUBRIC_LABELS,
        csv_qs=csv_qs,
    )


@pyfp_bp.route('/api/pyfp/reports/csv/batteries')
def csv_batteries():
    team_id     = request.args.get('team_id', '').strip() or None
    school_year = request.args.get('school_year', _current_school_year())
    test_window = request.args.get('test_window', _current_test_window())
    batteries   = _get_filtered_batteries(team_id, school_year, test_window)

    from field_trainer.pyfp.csv_export import batteries_csv
    content  = batteries_csv(batteries, db)
    filename = f"pyfp_batteries_{school_year}_{test_window}.csv"
    from flask import Response
    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@pyfp_bp.route('/api/pyfp/reports/csv/events')
def csv_events():
    team_id     = request.args.get('team_id', '').strip() or None
    school_year = request.args.get('school_year', _current_school_year())
    test_window = request.args.get('test_window', _current_test_window())
    batteries   = _get_filtered_batteries(team_id, school_year, test_window)

    from field_trainer.pyfp.csv_export import events_csv
    content  = events_csv(batteries, db)
    filename = f"pyfp_events_{school_year}_{test_window}.csv"
    from flask import Response
    return Response(
        content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
