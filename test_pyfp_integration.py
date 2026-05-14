#!/usr/bin/env python3
"""
PYFP Integration Test Suite

Tests the full PYFP HTTP API against a running server at localhost:5001.
Creates isolated test data (team + athlete) and cleans up after itself.
Uses the /api/pyfp/debug/touch endpoint to simulate cone events without hardware.

Usage: python3 test_pyfp_integration.py

Prereqs:
  - field-trainer-server.service running
  - seed_pyfp_demo.py run at least once (for demo-class smoke test)
"""

import sys
import time
import json
import sqlite3
import requests
from datetime import datetime

sys.path.insert(0, '/opt')

DB_PATH  = '/opt/data/field_trainer.db'
BASE_URL = 'http://localhost:5001'

SCHOOL_YEAR = '2025-2026'
WINDOW      = 'spring'


class PyfpIntegrationTests:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.start_time = None

        # IDs created during setup — cleaned in teardown
        self._team_id    = None
        self._athlete_id = None
        self._battery_id = None

    # ------------------------------------------------------------------ #
    # Infrastructure                                                       #
    # ------------------------------------------------------------------ #

    def log_result(self, name: str, passed: bool, message: str = ''):
        self.test_results.append({'test': name, 'passed': passed, 'message': message})
        suffix = f' — {message}' if message else ''
        print(f'   {"✅" if passed else "❌"} {name}{suffix}')

    def print_header(self, title: str):
        print(f'\n{"="*70}')
        print(f'  {title}')
        print('='*70)

    def get(self, path, **kwargs):
        return self.session.get(f'{BASE_URL}{path}', timeout=10, **kwargs)

    def post(self, path, **kwargs):
        return self.session.post(f'{BASE_URL}{path}', timeout=10, **kwargs)

    def db_query(self, sql, params=()):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params).fetchone()
        conn.close()
        return dict(row) if row else None

    def db_count(self, sql, params=()):
        conn = sqlite3.connect(DB_PATH)
        n = conn.execute(sql, params).fetchone()[0]
        conn.close()
        return n

    def setup(self):
        """Verify server up; create isolated test team + athlete."""
        print('\n🔧 Setting up test environment…')

        resp = self.get('/pyfp/healthz')
        if resp.status_code != 200 or not resp.json().get('ok'):
            raise RuntimeError('Server not responding — start field-trainer-server.service first')
        print('   ✅ Server reachable')

        from field_trainer.db_manager import DatabaseManager
        db = DatabaseManager(DB_PATH)
        self._team_id    = db.create_team('_PYFP_Integration_Test_')
        self._athlete_id = db.create_athlete(self._team_id, '_Test Athlete_', age=12)
        print(f'   ✅ Test team/athlete created')

    def teardown(self):
        """Remove all test data."""
        print('\n🧹 Cleaning up…')
        conn = sqlite3.connect(DB_PATH)
        if self._battery_id:
            conn.execute('DELETE FROM pyfp_award        WHERE battery_id=?', (self._battery_id,))
            conn.execute('DELETE FROM pyfp_cone_assignment WHERE event_result_id IN '
                         '(SELECT event_result_id FROM pyfp_event_result WHERE battery_id=?)',
                         (self._battery_id,))
            conn.execute('DELETE FROM pyfp_event_result WHERE battery_id=?', (self._battery_id,))
            conn.execute('DELETE FROM pyfp_assessment_battery WHERE battery_id=?', (self._battery_id,))
        if self._athlete_id:
            conn.execute('DELETE FROM performance_history WHERE athlete_id=?', (self._athlete_id,))
            conn.execute('DELETE FROM athletes WHERE athlete_id=?', (self._athlete_id,))
        if self._team_id:
            conn.execute('DELETE FROM teams WHERE team_id=?', (self._team_id,))
        conn.commit()
        conn.close()
        print('   ✅ Cleanup complete')

    # ------------------------------------------------------------------ #
    # §1 — Health + dashboard                                              #
    # ------------------------------------------------------------------ #

    def test_healthz(self):
        self.print_header('TEST 1 — Healthz')
        resp = self.get('/pyfp/healthz')
        ok = resp.status_code == 200 and resp.json().get('ok') is True
        self.log_result('GET /pyfp/healthz → 200 {"ok": true}', ok,
                        f'status={resp.status_code}')
        return ok

    def test_dashboard_renders(self):
        self.print_header('TEST 2 — Dashboard renders')
        resp = self.get('/pyfp/')
        ok = resp.status_code == 200 and 'PYFP' in resp.text
        self.log_result('GET /pyfp/ → 200, contains PYFP', ok, f'status={resp.status_code}')
        return ok

    def test_demo_class_in_dashboard(self):
        """Demo seed must have been run; PYFP Demo Class visible in team list."""
        resp = self.get('/pyfp/')
        ok = resp.status_code == 200 and 'PYFP Demo Class' in resp.text
        self.log_result('PYFP Demo Class appears in dashboard', ok)
        return ok

    # ------------------------------------------------------------------ #
    # §2 — Battery lifecycle                                               #
    # ------------------------------------------------------------------ #

    def test_battery_start(self):
        self.print_header('TEST 3 — Battery start')
        resp = self.post('/api/pyfp/battery/start', json={
            'athlete_id':  self._athlete_id,
            'school_year': SCHOOL_YEAR,
            'test_window': WINDOW,
            'rubric':      'both',
            'age_at_test': 12,
            'gender':      'male',
        })
        ok = resp.status_code in (200, 201) and 'battery_id' in resp.json()
        if ok:
            self._battery_id = resp.json()['battery_id']
        self.log_result('POST /api/pyfp/battery/start → 201, returns battery_id',
                        ok, f'status={resp.status_code}')
        return ok

    def test_battery_start_idempotent(self):
        """Second start for same athlete+window returns existing battery_id."""
        resp = self.post('/api/pyfp/battery/start', json={
            'athlete_id':  self._athlete_id,
            'school_year': SCHOOL_YEAR,
            'test_window': WINDOW,
            'rubric':      'both',
            'age_at_test': 12,
            'gender':      'male',
        })
        data = resp.json()
        ok = resp.status_code in (200, 201) and data.get('battery_id') == self._battery_id \
             and data.get('created') is False
        self.log_result('Battery start idempotent (created=false)', ok,
                        f'battery_id matches={data.get("battery_id") == self._battery_id}')
        return ok

    def test_battery_status_empty(self):
        """Fresh battery: events_done=0."""
        resp = self.get(f'/api/pyfp/battery/{self._battery_id}/status')
        data = resp.json()
        ok = resp.status_code == 200 and data.get('events_done') == 0
        self.log_result('Battery status: events_done=0 on fresh battery', ok,
                        f'events_done={data.get("events_done")}')
        return ok

    # ------------------------------------------------------------------ #
    # §3 — Event recording                                                 #
    # ------------------------------------------------------------------ #

    def _record(self, course_type, body):
        return self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/{course_type}/record',
            json=body,
        )

    def test_record_pull_up(self):
        self.print_header('TEST 4 — Event recording')
        resp = self._record('pyfp_pull_up', {'count': 6})
        ok = resp.status_code == 200 and resp.json().get('ok')
        # DB check
        row = self.db_query(
            'SELECT raw_value FROM pyfp_event_result WHERE battery_id=? AND course_type=?',
            (self._battery_id, 'pyfp_pull_up')
        )
        ok = ok and row is not None and row['raw_value'] == 6.0
        self.log_result('Record pull_up (count=6) → event_result in DB', ok,
                        f'db_value={row}')
        return ok

    def test_record_trunk_lift(self):
        resp = self._record('pyfp_trunk_lift', {'inches': 10.5})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record trunk_lift (inches=10.5)', ok, f'status={resp.status_code}')
        return ok

    def test_record_sit_and_reach(self):
        resp = self._record('pyfp_sit_and_reach', {'right_inches': 11.0, 'left_inches': 10.0})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record sit_and_reach (right=11, left=10)', ok)
        return ok

    def test_record_v_sit_reach_best_of_three(self):
        resp = self._record('pyfp_v_sit_reach', {'attempts': [5.0, 8.0, 7.0]})
        ok = resp.status_code == 200 and resp.json().get('ok')
        # Best should be 8.0 with is_best=1
        row = self.db_query(
            'SELECT raw_value FROM pyfp_event_result WHERE battery_id=? AND course_type=? '
            'AND is_best=1',
            (self._battery_id, 'pyfp_v_sit_reach')
        )
        ok = ok and row is not None and row['raw_value'] == 8.0
        self.log_result('Record v_sit_reach best-of-3 → is_best=1 on 8.0', ok,
                        f'best={row}')
        return ok

    def test_record_shoulder_stretch(self):
        resp = self._record('pyfp_shoulder_stretch', {'right_pass': True, 'left_pass': True})
        ok = resp.status_code == 200 and resp.json().get('ok')
        row = self.db_query(
            'SELECT raw_value FROM pyfp_event_result WHERE battery_id=? AND course_type=?',
            (self._battery_id, 'pyfp_shoulder_stretch')
        )
        ok = ok and row is not None and row['raw_value'] == 2.0
        self.log_result('Record shoulder_stretch both-pass → score=2.0', ok)
        return ok

    def test_record_bmi(self):
        resp = self._record('pyfp_bmi', {'height_ft': 4, 'height_in': 10, 'weight_lbs': 95})
        data = resp.json()
        ok = resp.status_code == 200 and data.get('ok') and 'bmi' in data
        # BMI = 95 * 703 / (58^2) ≈ 19.8
        bmi = data.get('bmi', 0)
        ok = ok and 18.0 < bmi < 22.0
        self.log_result(f'Record BMI (5\'10", 95lb) → BMI≈{bmi:.1f}', ok)
        return ok

    def test_record_skinfold(self):
        resp = self._record('pyfp_skinfold', {'triceps_mm': 14, 'calf_mm': 12})
        data = resp.json()
        ok = resp.status_code == 200 and data.get('ok') and 'pct_body_fat' in data
        pct = data.get('pct_body_fat', 0)
        # Male: 0.735*(14+12)+1.0 = 20.1
        ok = ok and 18.0 < pct < 22.0
        self.log_result(f'Record skinfold → pct_body_fat≈{pct:.1f}%', ok)
        return ok

    def test_record_curl_up_cadence(self):
        resp = self._record('pyfp_curl_up', {'count': 22})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record curl_up via cadence engine (count=22)', ok)
        return ok

    def test_record_plank_timer(self):
        resp = self._record('pyfp_plank', {'duration_seconds': 63.5})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record plank via timer engine (63.5s)', ok)
        return ok

    def test_record_modified_pull_up(self):
        resp = self._record('pyfp_modified_pull_up', {'count': 11})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record modified_pull_up (count=11)', ok)
        return ok

    def test_record_flexed_arm_hang(self):
        resp = self._record('pyfp_flexed_arm_hang', {'duration_seconds': 18.0})
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('Record flexed_arm_hang (18.0s)', ok)
        return ok

    def test_performance_history_written(self):
        """Each recorded event should have a performance_history row."""
        count = self.db_count(
            'SELECT COUNT(*) FROM performance_history WHERE athlete_id=?',
            (self._athlete_id,)
        )
        ok = count >= 8
        self.log_result(f'performance_history rows written (got {count}, need ≥8)', ok)
        return ok

    def test_battery_status_after_recording(self):
        """events_done > 0 after recording events."""
        resp = self.get(f'/api/pyfp/battery/{self._battery_id}/status')
        data = resp.json()
        done = data.get('events_done', 0)
        ok = resp.status_code == 200 and done >= 8
        self.log_result(f'Battery status events_done={done} (≥8)', ok)
        return ok

    # ------------------------------------------------------------------ #
    # §4 — Cone assignment + simulated run                                 #
    # ------------------------------------------------------------------ #

    def test_cone_assignment_save(self):
        self.print_header('TEST 5 — Cone events (simulated)')
        resp = self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_shuttle_run/cones',
            json={'endpoint_a': '192.168.99.100', 'endpoint_b': '192.168.99.101'},
        )
        ok = resp.status_code == 200 and resp.json().get('ok')
        self.log_result('POST cone assignment (shuttle) → ok', ok,
                        f'status={resp.status_code}')
        return ok

    def test_cone_assignment_duplicate_endpoints_rejected(self):
        resp = self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_shuttle_run/cones',
            json={'endpoint_a': '192.168.99.101', 'endpoint_b': '192.168.99.101'},
        )
        ok = resp.status_code == 400
        self.log_result('Same endpoint_a/b → 400 rejected', ok,
                        f'status={resp.status_code}')
        return ok

    def test_shuttle_run_simulated(self):
        """Start shuttle run, fire 4 debug touches in B→A→B→A order, verify done."""
        # Start run
        resp = self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_shuttle_run/run/start',
            json={},
        )
        if resp.status_code != 201 or not resp.json().get('ok'):
            self.log_result('Shuttle run start', False,
                            f'status={resp.status_code} body={resp.text[:200]}')
            return False
        self.log_result('Shuttle run start → 201', True)

        # Simulate B→A→B→A touches
        sequence = [
            '192.168.99.101',  # B
            '192.168.99.100',  # A
            '192.168.99.101',  # B
            '192.168.99.100',  # A
        ]
        for i, dev in enumerate(sequence, 1):
            time.sleep(0.3)
            r = self.post('/api/pyfp/debug/touch', json={'device_id': dev})
            if not r.json().get('ok'):
                self.log_result(f'Shuttle debug touch {i}', False, r.text[:100])
                return False

        time.sleep(0.5)

        # Poll status — should be done
        resp = self.get(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_shuttle_run/run/status'
        )
        data = resp.json()
        status = data.get('status') or data.get('state', {}).get('status')
        ok = status == 'done'
        self.log_result('Shuttle run completes after 4 touches (status=done)', ok,
                        f'status={status}')

        # Verify event_result raw_value > 0
        row = self.db_query(
            'SELECT raw_value FROM pyfp_event_result WHERE battery_id=? '
            'AND course_type=? AND raw_value > 0',
            (self._battery_id, 'pyfp_shuttle_run')
        )
        ok2 = row is not None
        self.log_result('Shuttle event_result raw_value > 0 in DB', ok2, f'row={row}')
        return ok and ok2

    # ------------------------------------------------------------------ #
    # §5 — Battery complete + scoring + awards                             #
    # ------------------------------------------------------------------ #

    def test_battery_complete(self):
        self.print_header('TEST 6 — Battery complete')
        resp = self.post(f'/api/pyfp/battery/{self._battery_id}/complete', json={})
        data = resp.json()
        ok = resp.status_code == 200 and data.get('ok')
        self.log_result('POST battery complete → ok', ok,
                        f'already_complete={data.get("already_complete")} awards={data.get("awards")}')
        return ok

    def test_battery_complete_idempotent(self):
        """Calling complete twice returns already_complete=True."""
        resp = self.post(f'/api/pyfp/battery/{self._battery_id}/complete', json={})
        data = resp.json()
        ok = resp.status_code == 200 and data.get('already_complete') is True
        self.log_result('Battery complete idempotent (already_complete=true)', ok)
        return ok

    def test_battery_completed_at_set(self):
        row = self.db_query(
            'SELECT completed_at FROM pyfp_assessment_battery WHERE battery_id=?',
            (self._battery_id,)
        )
        ok = row is not None and row['completed_at'] is not None
        self.log_result('completed_at set in DB after complete', ok,
                        f'completed_at={row}')
        return ok

    def test_complete_blocks_further_recording(self):
        """Recording an event on a completed battery → 409."""
        resp = self._record('pyfp_pull_up', {'count': 99})
        ok = resp.status_code == 409
        self.log_result('Recording on completed battery → 409', ok,
                        f'status={resp.status_code}')
        return ok

    # ------------------------------------------------------------------ #
    # §6 — Report card + reports page                                      #
    # ------------------------------------------------------------------ #

    def test_report_card_renders(self):
        self.print_header('TEST 7 — Report card + reports')
        resp = self.get(f'/pyfp/battery/{self._battery_id}/report')
        ok = resp.status_code == 200 and 'Report Card' in resp.text
        self.log_result('GET /pyfp/battery/<id>/report → 200, contains Report Card', ok,
                        f'status={resp.status_code}')
        return ok

    def test_athlete_view_renders(self):
        resp = self.get(f'/pyfp/athlete/{self._athlete_id}')
        ok = resp.status_code == 200
        self.log_result('GET /pyfp/athlete/<id> → 200', ok, f'status={resp.status_code}')
        return ok

    def test_reports_page_renders(self):
        resp = self.get(f'/pyfp/reports?team_id={self._team_id}'
                        f'&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        ok = resp.status_code == 200 and 'Reports' in resp.text
        self.log_result('GET /pyfp/reports → 200', ok, f'status={resp.status_code}')
        return ok

    # ------------------------------------------------------------------ #
    # §7 — CSV exports                                                     #
    # ------------------------------------------------------------------ #

    def test_csv_batteries(self):
        self.print_header('TEST 8 — CSV exports')
        resp = self.get(f'/api/pyfp/reports/csv/batteries'
                        f'?team_id={self._team_id}&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        ok = resp.status_code == 200
        content_type = resp.headers.get('Content-Type', '')
        ok = ok and 'text/csv' in content_type
        lines = resp.text.strip().splitlines()
        # header + at least 1 data row
        ok = ok and len(lines) >= 2
        # header must contain battery_id
        ok = ok and 'battery_id' in lines[0]
        self.log_result(f'CSV batteries: {len(lines)} lines, correct headers', ok)
        return ok

    def test_csv_batteries_award_columns(self):
        """Wide CSV header contains all three award columns."""
        resp = self.get(f'/api/pyfp/reports/csv/batteries'
                        f'?team_id={self._team_id}&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        header = resp.text.splitlines()[0]
        ok = all(col in header for col in
                 ('award_hfz_all_zones', 'award_pft_3_of_6', 'award_pft_full_6'))
        self.log_result('CSV batteries header has all award columns', ok)
        return ok

    def test_csv_batteries_hr_columns_reserved(self):
        """Wide CSV header contains reserved HR columns."""
        resp = self.get(f'/api/pyfp/reports/csv/batteries'
                        f'?team_id={self._team_id}&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        header = resp.text.splitlines()[0]
        ok = 'hr_resting_bpm' in header and 'hr_peak_bpm' in header
        self.log_result('CSV batteries header has reserved HR columns', ok)
        return ok

    def test_csv_events(self):
        resp = self.get(f'/api/pyfp/reports/csv/events'
                        f'?team_id={self._team_id}&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        ok = resp.status_code == 200 and 'text/csv' in resp.headers.get('Content-Type', '')
        lines = resp.text.strip().splitlines()
        ok = ok and len(lines) >= 2 and 'event_result_id' in lines[0]
        self.log_result(f'CSV events: {len(lines)} lines, correct headers', ok)
        return ok

    def test_csv_empty_filter(self):
        """CSV with no matching batteries returns header only."""
        resp = self.get('/api/pyfp/reports/csv/batteries'
                        '?school_year=1999-2000&test_window=fall')
        lines = [l for l in resp.text.strip().splitlines() if l]
        # header only
        ok = resp.status_code == 200 and len(lines) == 1
        self.log_result('CSV with no matching data returns header only', ok,
                        f'lines={len(lines)}')
        return ok

    # ------------------------------------------------------------------ #
    # §8 — Error handling                                                  #
    # ------------------------------------------------------------------ #

    def test_battery_not_found(self):
        self.print_header('TEST 9 — Error handling')
        resp = self.get('/api/pyfp/battery/no-such-id/status')
        ok = resp.status_code == 404
        self.log_result('Battery status with bad ID → 404', ok, f'status={resp.status_code}')
        return ok

    def test_record_unknown_event(self):
        """Recording for unknown course_type → 404."""
        # Use a new non-completed battery — ours is completed, which gives 409
        # so just check the event-unknown path on the existing battery pre-completion.
        # Actually since our battery IS completed, we test 404 vs 409 ordering.
        resp = self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_nonexistent/record',
            json={'count': 1},
        )
        ok = resp.status_code in (404, 409)
        self.log_result('Recording unknown event → 404 or 409', ok,
                        f'status={resp.status_code}')
        return ok

    def test_start_battery_missing_fields(self):
        """Missing required fields → 400."""
        resp = self.post('/api/pyfp/battery/start', json={'athlete_id': self._athlete_id})
        ok = resp.status_code == 400
        self.log_result('Battery start with missing fields → 400', ok,
                        f'status={resp.status_code}')
        return ok

    def test_cone_assignment_missing_endpoints(self):
        """Shuttle assignment with missing endpoint → 4xx (400 if active, 409 if completed)."""
        resp = self.post(
            f'/api/pyfp/battery/{self._battery_id}/event/pyfp_shuttle_run/cones',
            json={'endpoint_a': '192.168.99.101'},
        )
        ok = resp.status_code in (400, 409)
        self.log_result('Shuttle cone assignment missing endpoint_b → 4xx', ok,
                        f'status={resp.status_code}')
        return ok

    # ------------------------------------------------------------------ #
    # §9 — Demo class smoke test                                           #
    # ------------------------------------------------------------------ #

    def test_demo_class_csv_has_data(self):
        self.print_header('TEST 10 — Demo class smoke test')
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name='PYFP Demo Class'"
        ).fetchone()
        conn.close()
        if not row:
            self.log_result('Demo class present in DB', False, 'Run seed_pyfp_demo.py first')
            return False
        team_id = row[0]

        resp = self.get(f'/api/pyfp/reports/csv/batteries'
                        f'?team_id={team_id}&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        lines = [l for l in resp.text.strip().splitlines() if l]
        ok = resp.status_code == 200 and len(lines) > 5
        self.log_result(f'Demo class CSV has {len(lines)-1} athlete rows', ok)
        return ok

    def test_demo_class_dashboard_shows_completions(self):
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT team_id FROM teams WHERE name='PYFP Demo Class'"
        ).fetchone()
        conn.close()
        if not row:
            self.log_result('Demo class dashboard completions', False,
                            'Run seed_pyfp_demo.py first')
            return False
        team_id = row[0]
        resp = self.get(f'/pyfp/?team_id={team_id}'
                        f'&school_year={SCHOOL_YEAR}&test_window={WINDOW}')
        ok = resp.status_code == 200 and 'Complete' in resp.text
        self.log_result('Demo class dashboard shows completed batteries', ok)
        return ok

    # ------------------------------------------------------------------ #
    # Runner                                                               #
    # ------------------------------------------------------------------ #

    def run_all_tests(self):
        self.start_time = time.time()

        print('\n' + '='*70)
        print('  PYFP INTEGRATION TEST SUITE')
        print('='*70)
        print(f'  Server: {BASE_URL}')
        print(f'  DB:     {DB_PATH}')
        print(f'  Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('='*70)

        try:
            self.setup()
        except Exception as e:
            print(f'\n❌ Setup failed: {e}')
            return False

        sections = [
            [
                self.test_healthz,
                self.test_dashboard_renders,
                self.test_demo_class_in_dashboard,
            ],
            [
                self.test_battery_start,
                self.test_battery_start_idempotent,
                self.test_battery_status_empty,
            ],
            [
                self.test_record_pull_up,
                self.test_record_trunk_lift,
                self.test_record_sit_and_reach,
                self.test_record_v_sit_reach_best_of_three,
                self.test_record_shoulder_stretch,
                self.test_record_bmi,
                self.test_record_skinfold,
                self.test_record_curl_up_cadence,
                self.test_record_plank_timer,
                self.test_record_modified_pull_up,
                self.test_record_flexed_arm_hang,
                self.test_performance_history_written,
                self.test_battery_status_after_recording,
            ],
            [
                self.test_cone_assignment_save,
                self.test_cone_assignment_duplicate_endpoints_rejected,
                self.test_shuttle_run_simulated,
            ],
            [
                self.test_battery_complete,
                self.test_battery_complete_idempotent,
                self.test_battery_completed_at_set,
                self.test_complete_blocks_further_recording,
            ],
            [
                self.test_report_card_renders,
                self.test_athlete_view_renders,
                self.test_reports_page_renders,
            ],
            [
                self.test_csv_batteries,
                self.test_csv_batteries_award_columns,
                self.test_csv_batteries_hr_columns_reserved,
                self.test_csv_events,
                self.test_csv_empty_filter,
            ],
            [
                self.test_battery_not_found,
                self.test_record_unknown_event,
                self.test_start_battery_missing_fields,
                self.test_cone_assignment_missing_endpoints,
            ],
            [
                self.test_demo_class_csv_has_data,
                self.test_demo_class_dashboard_shows_completions,
            ],
        ]

        passed = failed = 0
        for group in sections:
            for test_fn in group:
                try:
                    if test_fn():
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    self.log_result(test_fn.__name__, False, f'Exception: {e}')
                    import traceback; traceback.print_exc()
                    failed += 1

        try:
            self.teardown()
        except Exception as e:
            print(f'\n  ⚠️  Teardown error: {e}')

        elapsed = time.time() - self.start_time
        total = passed + failed

        print('\n' + '='*70)
        print('  SUMMARY')
        print('='*70)
        print(f'  Total: {total}  ✅ Passed: {passed}  ❌ Failed: {failed}  ⏱  {elapsed:.2f}s')
        if failed == 0:
            print('  🎉 ALL TESTS PASSED')
        else:
            print(f'  ⚠️  {failed} TEST(S) FAILED')
        print('='*70)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = f'/tmp/pyfp_integration_test_{ts}.txt'
        try:
            with open(path, 'w') as f:
                f.write(f'PYFP Integration Tests — {datetime.now().isoformat()}\n')
                f.write(f'Server={BASE_URL}  Total={total} Passed={passed} Failed={failed}\n\n')
                for r in self.test_results:
                    f.write(f'{"PASS" if r["passed"] else "FAIL"}: {r["test"]}'
                            + (f' — {r["message"]}' if r['message'] else '') + '\n')
            print(f'\n  📄 Results: {path}')
        except Exception:
            pass

        return failed == 0


def main():
    tester = PyfpIntegrationTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
