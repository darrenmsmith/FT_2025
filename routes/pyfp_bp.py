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
                })

    return render_template(
        'pyfp_dashboard.html',
        teams=teams,
        selected_team=selected_team,
        athlete_rows=athlete_rows,
        school_year=school_year,
        test_window=test_window,
        school_year_options=_school_year_options(),
        rubric_labels=RUBRIC_LABELS,
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
        return jsonify({'ok': True, 'already_complete': True})
    db.complete_pyfp_battery(battery_id)
    return jsonify({'ok': True, 'already_complete': False})
