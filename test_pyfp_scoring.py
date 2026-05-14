#!/usr/bin/env python3
"""
PYFP Scoring & Awards Unit Test Suite

Tests scoring classification logic and award computation without requiring
a running server. Hits the real SQLite DB for scoring-table lookups.

Usage: python3 test_pyfp_scoring.py
"""

import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, '/opt')

from field_trainer.db_manager import DatabaseManager
from field_trainer.pyfp.scoring import classify_hfz, classify_pft, score_battery, _CACHE
from field_trainer.pyfp.awards import compute_and_write_awards

DB_PATH = '/opt/data/field_trainer.db'


class PyfpScoringTests:
    def __init__(self):
        self.db = DatabaseManager(DB_PATH)
        self.test_results = []
        self.start_time = None
        self._test_battery_id = None
        self._test_athlete_id = None
        self._test_team_id = None

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def log_result(self, name: str, passed: bool, message: str = ''):
        self.test_results.append({'test': name, 'passed': passed, 'message': message})
        status = '  PASS' if passed else '  FAIL'
        suffix = f' — {message}' if message else ''
        print(f'   {"✅" if passed else "❌"} {name}{suffix}')

    def print_header(self, title: str):
        print(f'\n{"="*70}')
        print(f'  {title}')
        print('='*70)

    def _fresh_cache(self):
        _CACHE.clear()

    def setup(self):
        self._fresh_cache()
        # Create a throwaway team + athlete for award tests
        self._test_team_id = self.db.create_team('_PYFP_TEST_RUNNER_')
        self._test_athlete_id = self.db.create_athlete(
            self._test_team_id, '_test_athlete_', age=12
        )

    def teardown(self):
        with self.db.get_connection() as conn:
            if self._test_battery_id:
                conn.execute('DELETE FROM pyfp_award WHERE battery_id=?', (self._test_battery_id,))
                conn.execute('DELETE FROM pyfp_event_result WHERE battery_id=?', (self._test_battery_id,))
                conn.execute('DELETE FROM pyfp_assessment_battery WHERE battery_id=?', (self._test_battery_id,))
            if self._test_athlete_id:
                conn.execute('DELETE FROM athletes WHERE athlete_id=?', (self._test_athlete_id,))
            if self._test_team_id:
                conn.execute('DELETE FROM teams WHERE team_id=?', (self._test_team_id,))

    def _make_battery(self, rubric, age=12, gender='male'):
        bid = self.db.create_pyfp_battery(
            athlete_id=self._test_athlete_id,
            school_year='2025-2026',
            test_window='spring',
            rubric=rubric,
            age_at_test=age,
            gender=gender,
        )
        self._test_battery_id = bid
        return bid

    def _result(self, battery_id, course_type, raw_value, raw_unit='reps'):
        return {
            'event_result_id': str(uuid.uuid4()),
            'battery_id': battery_id,
            'course_type': course_type,
            'raw_value': raw_value,
            'raw_unit': raw_unit,
            'is_best': 1,
        }

    # ------------------------------------------------------------------ #
    # §1 — HFZ classification: higher-is-better events                    #
    # ------------------------------------------------------------------ #

    def test_hfz_pacer_in_zone(self):
        """10yo male PACER 25 laps (hfz_min=23) → hfz"""
        r = classify_hfz('pyfp_pacer', 25, 10, 'male', self.db)
        self.log_result('HFZ PACER in-zone (25 ≥ 23)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_pacer_at_minimum(self):
        """10yo male PACER exactly at hfz_min=23 → hfz (inclusive)"""
        r = classify_hfz('pyfp_pacer', 23, 10, 'male', self.db)
        self.log_result('HFZ PACER at min edge (23)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_pacer_below_minimum(self):
        """10yo male PACER 22 laps (< hfz_min=23) → below_hfz"""
        r = classify_hfz('pyfp_pacer', 22, 10, 'male', self.db)
        self.log_result('HFZ PACER below min (22 < 23)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    def test_hfz_pushup_above_max(self):
        """10yo female push-up 20 reps (hfz_max=15) → above_hfz"""
        r = classify_hfz('pyfp_push_up', 20, 10, 'female', self.db)
        self.log_result('HFZ push-up above max (20 > 15)', r == 'above_hfz', f'got={r}')
        return r == 'above_hfz'

    def test_hfz_trunk_lift_at_max(self):
        """Trunk lift 12 inches (hfz_max=12) → hfz (inclusive)"""
        r = classify_hfz('pyfp_trunk_lift', 12, 11, 'female', self.db)
        self.log_result('HFZ trunk lift at max (12 = 12)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_shoulder_stretch_both_pass(self):
        """Shoulder stretch score=2 (both sides) → hfz"""
        r = classify_hfz('pyfp_shoulder_stretch', 2, 12, 'male', self.db)
        self.log_result('HFZ shoulder stretch both pass (2)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_shoulder_stretch_one_side(self):
        """Shoulder stretch score=1 (one side) → below_hfz (min=2)"""
        r = classify_hfz('pyfp_shoulder_stretch', 1, 12, 'male', self.db)
        self.log_result('HFZ shoulder stretch one side (1 < 2)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    # ------------------------------------------------------------------ #
    # §2 — HFZ classification: lower-is-better (time-based)               #
    # ------------------------------------------------------------------ #

    def test_hfz_mile_run_in_zone(self):
        """10yo male mile run 500s (hfz_max=630s) → hfz"""
        r = classify_hfz('pyfp_mile_run', 500, 10, 'male', self.db)
        self.log_result('HFZ mile run in-zone (500 ≤ 630)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_mile_run_too_slow(self):
        """10yo male mile run 700s (hfz_max=630s) → below_hfz"""
        r = classify_hfz('pyfp_mile_run', 700, 10, 'male', self.db)
        self.log_result('HFZ mile run too slow (700 > 630)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    def test_hfz_shuttle_run_in_zone(self):
        """10yo male shuttle 10.0s (hfz_max=11.5) → hfz"""
        r = classify_hfz('pyfp_shuttle_run', 10.0, 10, 'male', self.db)
        self.log_result('HFZ shuttle run in-zone (10.0 ≤ 11.5)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_shuttle_run_too_slow(self):
        """10yo male shuttle 12.0s (hfz_max=11.5) → below_hfz"""
        r = classify_hfz('pyfp_shuttle_run', 12.0, 10, 'male', self.db)
        self.log_result('HFZ shuttle run too slow (12.0 > 11.5)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    # ------------------------------------------------------------------ #
    # §3 — HFZ classification: range tests (BMI, skinfold)                #
    # ------------------------------------------------------------------ #

    def test_hfz_bmi_healthy(self):
        """10yo male BMI 18.0 (range 14.2–22.6) → hfz"""
        r = classify_hfz('pyfp_bmi', 18.0, 10, 'male', self.db)
        self.log_result('HFZ BMI healthy (18.0 in 14.2–22.6)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_bmi_overweight(self):
        """10yo male BMI 25.0 (> hfz_max=22.6) → below_hfz"""
        r = classify_hfz('pyfp_bmi', 25.0, 10, 'male', self.db)
        self.log_result('HFZ BMI overweight (25.0 > 22.6)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    def test_hfz_bmi_underweight(self):
        """10yo male BMI 12.0 (< hfz_min=14.2) → above_hfz (underweight)"""
        r = classify_hfz('pyfp_bmi', 12.0, 10, 'male', self.db)
        self.log_result('HFZ BMI underweight (12.0 < 14.2)', r == 'above_hfz', f'got={r}')
        return r == 'above_hfz'

    def test_hfz_skinfold_healthy_male(self):
        """Male skinfold 18% (range 10–25) → hfz"""
        r = classify_hfz('pyfp_skinfold', 18.0, 12, 'male', self.db)
        self.log_result('HFZ skinfold healthy male (18 in 10–25)', r == 'hfz', f'got={r}')
        return r == 'hfz'

    def test_hfz_skinfold_overweight_female(self):
        """Female skinfold 35% (> hfz_max=32) → below_hfz"""
        r = classify_hfz('pyfp_skinfold', 35.0, 12, 'female', self.db)
        self.log_result('HFZ skinfold overweight female (35 > 32)', r == 'below_hfz', f'got={r}')
        return r == 'below_hfz'

    # ------------------------------------------------------------------ #
    # §4 — HFZ edge cases                                                  #
    # ------------------------------------------------------------------ #

    def test_hfz_age_clamp_high(self):
        """age=20 → clamped to 17; should not raise"""
        try:
            r = classify_hfz('pyfp_pacer', 65, 20, 'male', self.db)
            ok = r in ('hfz', 'below_hfz', 'above_hfz', 'unscored')
            self.log_result('HFZ age clamp high (age=20)', ok, f'got={r}')
            return ok
        except Exception as e:
            self.log_result('HFZ age clamp high (age=20)', False, str(e))
            return False

    def test_hfz_age_clamp_low(self):
        """age=4 → clamped to 5; should not raise"""
        try:
            r = classify_hfz('pyfp_pacer', 8, 4, 'female', self.db)
            ok = r in ('hfz', 'below_hfz', 'above_hfz', 'unscored')
            self.log_result('HFZ age clamp low (age=4)', ok, f'got={r}')
            return ok
        except Exception as e:
            self.log_result('HFZ age clamp low (age=4)', False, str(e))
            return False

    def test_hfz_unknown_event(self):
        """Unknown event → 'unscored' (no crash)"""
        r = classify_hfz('pyfp_nonexistent', 10, 12, 'male', self.db)
        self.log_result('HFZ unknown event → unscored', r == 'unscored', f'got={r}')
        return r == 'unscored'

    # ------------------------------------------------------------------ #
    # §5 — PFT classification                                              #
    # ------------------------------------------------------------------ #

    def test_pft_pacer_meets(self):
        """10yo male PACER 35 laps (p85=32) → meets"""
        r = classify_pft('pyfp_pacer', 35, 10, 'male', self.db)
        self.log_result('PFT PACER meets (35 ≥ p85=32)', r == 'meets', f'got={r}')
        return r == 'meets'

    def test_pft_pacer_at_threshold(self):
        """10yo male PACER exactly at p85=32 → meets (inclusive)"""
        r = classify_pft('pyfp_pacer', 32, 10, 'male', self.db)
        self.log_result('PFT PACER at threshold (32 = p85=32)', r == 'meets', f'got={r}')
        return r == 'meets'

    def test_pft_pacer_below(self):
        """10yo male PACER 20 laps (p85=32) → below"""
        r = classify_pft('pyfp_pacer', 20, 10, 'male', self.db)
        self.log_result('PFT PACER below (20 < p85=32)', r == 'below', f'got={r}')
        return r == 'below'

    def test_pft_mile_run_meets(self):
        """10yo male mile run 480s (p85=510s, lower is better) → meets"""
        r = classify_pft('pyfp_mile_run', 480, 10, 'male', self.db)
        self.log_result('PFT mile run meets (480 ≤ p85=510)', r == 'meets', f'got={r}')
        return r == 'meets'

    def test_pft_mile_run_below(self):
        """10yo male mile run 600s (p85=510s) → below"""
        r = classify_pft('pyfp_mile_run', 600, 10, 'male', self.db)
        self.log_result('PFT mile run below (600 > p85=510)', r == 'below', f'got={r}')
        return r == 'below'

    def test_pft_plank_meets(self):
        """Male plank 65s (p85=60) → meets"""
        r = classify_pft('pyfp_plank', 65, 12, 'male', self.db)
        self.log_result('PFT plank meets (65 ≥ p85=60)', r == 'meets', f'got={r}')
        return r == 'meets'

    def test_pft_non_pft_event_unscored(self):
        """pyfp_trunk_lift is not in PFT table → unscored"""
        r = classify_pft('pyfp_trunk_lift', 10, 12, 'male', self.db)
        self.log_result('PFT non-PFT event → unscored', r == 'unscored', f'got={r}')
        return r == 'unscored'

    # ------------------------------------------------------------------ #
    # §6 — score_battery                                                   #
    # ------------------------------------------------------------------ #

    def test_score_battery_hfz_rubric(self):
        """score_battery on fitnessgram_hfz battery: all results have hfz key, pft=None"""
        bid = self._make_battery('fitnessgram_hfz', age=12, gender='male')
        battery = self.db.get_pyfp_battery(bid)
        results = [
            self._result(bid, 'pyfp_pacer', 35, 'laps'),
            self._result(bid, 'pyfp_curl_up', 22, 'reps'),
        ]
        scores = score_battery(battery, results, self.db)
        ok = (
            scores.get('pyfp_pacer', {}).get('hfz') is not None and
            scores.get('pyfp_pacer', {}).get('pft') is None and
            scores.get('pyfp_curl_up', {}).get('hfz') is not None
        )
        self.log_result('score_battery HFZ rubric keys correct', ok, str(scores))
        return ok

    def test_score_battery_pft_rubric(self):
        """score_battery on pft_2026 battery: pft key set, hfz=None"""
        bid = self._make_battery('pft_2026', age=12, gender='male')
        battery = self.db.get_pyfp_battery(bid)
        results = [self._result(bid, 'pyfp_pacer', 50, 'laps')]
        scores = score_battery(battery, results, self.db)
        ok = (
            scores.get('pyfp_pacer', {}).get('pft') is not None and
            scores.get('pyfp_pacer', {}).get('hfz') is None
        )
        self.log_result('score_battery PFT rubric keys correct', ok, str(scores))
        return ok

    def test_score_battery_both_rubric(self):
        """score_battery on both rubric: pyfp_pacer has both hfz and pft set"""
        bid = self._make_battery('both', age=12, gender='male')
        battery = self.db.get_pyfp_battery(bid)
        results = [self._result(bid, 'pyfp_pacer', 35, 'laps')]
        scores = score_battery(battery, results, self.db)
        ok = (
            scores.get('pyfp_pacer', {}).get('hfz') is not None and
            scores.get('pyfp_pacer', {}).get('pft') is not None
        )
        self.log_result('score_battery both rubric: pacer has HFZ+PFT', ok, str(scores))
        return ok

    def test_score_battery_deduplicates_attempts(self):
        """score_battery uses is_best=1 row when duplicates exist"""
        bid = self._make_battery('fitnessgram_hfz', age=12, gender='male')
        battery = self.db.get_pyfp_battery(bid)
        results = [
            {**self._result(bid, 'pyfp_curl_up', 5, 'reps'), 'is_best': 0},
            {**self._result(bid, 'pyfp_curl_up', 25, 'reps'), 'is_best': 1},
        ]
        scores = score_battery(battery, results, self.db)
        # 25 reps for 12yo male (hfz_min=18) should be hfz
        hfz = scores.get('pyfp_curl_up', {}).get('hfz')
        self.log_result('score_battery uses best attempt', hfz == 'hfz', f'hfz={hfz}')
        return hfz == 'hfz'

    # ------------------------------------------------------------------ #
    # §7 — Awards                                                          #
    # ------------------------------------------------------------------ #

    def _all_hfz_scores(self, bid, gender='male', age=12):
        """Build a scores dict where all HFZ events are 'hfz'."""
        from field_trainer.pyfp.events_registry import EVENTS
        battery = self.db.get_pyfp_battery(bid)
        return {
            ct: {'hfz': 'hfz', 'pft': None}
            for ct, ev in EVENTS.items() if 'fitnessgram_hfz' in ev['rubrics']
        }

    def _pft_scores(self, n_meets=6):
        """Build a scores dict with n_meets PFT events scored 'meets'."""
        from field_trainer.pyfp.events_registry import EVENTS
        pft_events = [ct for ct, ev in EVENTS.items() if 'pft_2026' in ev['rubrics']]
        scores = {}
        for i, ct in enumerate(pft_events):
            scores[ct] = {'hfz': None, 'pft': 'meets' if i < n_meets else 'below'}
        return scores

    def test_award_hfz_all_zones(self):
        """All HFZ events scored 'hfz' → hfz_all_zones awarded"""
        bid = self._make_battery('fitnessgram_hfz')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._all_hfz_scores(bid)
        awarded = compute_and_write_awards(battery, scores, self.db)
        rows = self.db.get_pyfp_awards(bid)
        ok = 'hfz_all_zones' in awarded and any(r['award_type'] == 'hfz_all_zones' for r in rows)
        self.log_result('Award hfz_all_zones earned + written to DB', ok, f'awarded={awarded}')
        return ok

    def test_award_hfz_not_earned_if_any_below(self):
        """Any HFZ event below_hfz → hfz_all_zones not awarded"""
        bid = self._make_battery('fitnessgram_hfz')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._all_hfz_scores(bid)
        scores['pyfp_pacer'] = {'hfz': 'below_hfz', 'pft': None}
        awarded = compute_and_write_awards(battery, scores, self.db)
        ok = 'hfz_all_zones' not in awarded
        self.log_result('Award hfz_all_zones NOT earned if any below', ok, f'awarded={awarded}')
        return ok

    def test_award_pft_3_of_6(self):
        """3 of 6 PFT events 'meets' → pft_3_of_6 awarded, pft_full_6 not"""
        bid = self._make_battery('pft_2026')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._pft_scores(n_meets=3)
        awarded = compute_and_write_awards(battery, scores, self.db)
        ok = 'pft_3_of_6' in awarded and 'pft_full_6' not in awarded
        self.log_result('Award pft_3_of_6 (not full_6) for 3 meets', ok, f'awarded={awarded}')
        return ok

    def test_award_pft_full_6(self):
        """All 6 PFT events 'meets' → both pft_3_of_6 and pft_full_6"""
        bid = self._make_battery('pft_2026')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._pft_scores(n_meets=6)
        awarded = compute_and_write_awards(battery, scores, self.db)
        ok = 'pft_3_of_6' in awarded and 'pft_full_6' in awarded
        self.log_result('Award pft_full_6 + pft_3_of_6 for all 6', ok, f'awarded={awarded}')
        return ok

    def test_award_pft_2_of_6_no_award(self):
        """Only 2 of 6 PFT meets → no award"""
        bid = self._make_battery('pft_2026')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._pft_scores(n_meets=2)
        awarded = compute_and_write_awards(battery, scores, self.db)
        ok = 'pft_3_of_6' not in awarded and 'pft_full_6' not in awarded
        self.log_result('No award for only 2 of 6 PFT meets', ok, f'awarded={awarded}')
        return ok

    def test_award_idempotent(self):
        """Running compute_and_write_awards twice doesn't duplicate rows"""
        bid = self._make_battery('fitnessgram_hfz')
        battery = self.db.get_pyfp_battery(bid)
        scores = self._all_hfz_scores(bid)
        compute_and_write_awards(battery, scores, self.db)
        compute_and_write_awards(battery, scores, self.db)
        rows = self.db.get_pyfp_awards(bid)
        count = sum(1 for r in rows if r['award_type'] == 'hfz_all_zones')
        ok = count == 1
        self.log_result('Award upsert is idempotent (1 row, not 2)', ok, f'count={count}')
        return ok

    # ------------------------------------------------------------------ #
    # Runner                                                               #
    # ------------------------------------------------------------------ #

    def run_all_tests(self):
        self.start_time = time.time()

        print('\n' + '='*70)
        print('  PYFP SCORING & AWARDS — UNIT TEST SUITE')
        print('='*70)
        print(f'  DB: {DB_PATH}')
        print(f'  Started: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('='*70)

        try:
            self.setup()
            print('  ✅ Setup complete')
        except Exception as e:
            print(f'  ❌ Setup failed: {e}')
            return False

        sections = [
            ('§1 — HFZ: higher-is-better', [
                self.test_hfz_pacer_in_zone,
                self.test_hfz_pacer_at_minimum,
                self.test_hfz_pacer_below_minimum,
                self.test_hfz_pushup_above_max,
                self.test_hfz_trunk_lift_at_max,
                self.test_hfz_shoulder_stretch_both_pass,
                self.test_hfz_shoulder_stretch_one_side,
            ]),
            ('§2 — HFZ: lower-is-better (time)', [
                self.test_hfz_mile_run_in_zone,
                self.test_hfz_mile_run_too_slow,
                self.test_hfz_shuttle_run_in_zone,
                self.test_hfz_shuttle_run_too_slow,
            ]),
            ('§3 — HFZ: range tests (BMI, skinfold)', [
                self.test_hfz_bmi_healthy,
                self.test_hfz_bmi_overweight,
                self.test_hfz_bmi_underweight,
                self.test_hfz_skinfold_healthy_male,
                self.test_hfz_skinfold_overweight_female,
            ]),
            ('§4 — HFZ edge cases', [
                self.test_hfz_age_clamp_high,
                self.test_hfz_age_clamp_low,
                self.test_hfz_unknown_event,
            ]),
            ('§5 — PFT classification', [
                self.test_pft_pacer_meets,
                self.test_pft_pacer_at_threshold,
                self.test_pft_pacer_below,
                self.test_pft_mile_run_meets,
                self.test_pft_mile_run_below,
                self.test_pft_plank_meets,
                self.test_pft_non_pft_event_unscored,
            ]),
            ('§6 — score_battery', [
                self.test_score_battery_hfz_rubric,
                self.test_score_battery_pft_rubric,
                self.test_score_battery_both_rubric,
                self.test_score_battery_deduplicates_attempts,
            ]),
            ('§7 — Awards', [
                self.test_award_hfz_all_zones,
                self.test_award_hfz_not_earned_if_any_below,
                self.test_award_pft_3_of_6,
                self.test_award_pft_full_6,
                self.test_award_pft_2_of_6_no_award,
                self.test_award_idempotent,
            ]),
        ]

        passed = failed = 0
        for section_title, tests in sections:
            self.print_header(section_title)
            for test_fn in tests:
                # Reset to a fresh battery between award tests
                if self._test_battery_id:
                    with self.db.get_connection() as conn:
                        conn.execute('DELETE FROM pyfp_award WHERE battery_id=?',
                                     (self._test_battery_id,))
                        conn.execute('DELETE FROM pyfp_event_result WHERE battery_id=?',
                                     (self._test_battery_id,))
                        conn.execute('DELETE FROM pyfp_assessment_battery WHERE battery_id=?',
                                     (self._test_battery_id,))
                    self._test_battery_id = None
                _CACHE.clear()
                try:
                    if test_fn():
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    self.log_result(test_fn.__name__, False, f'Exception: {e}')
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
        path = f'/tmp/pyfp_scoring_test_{ts}.txt'
        try:
            with open(path, 'w') as f:
                f.write(f'PYFP Scoring Unit Tests — {datetime.now().isoformat()}\n')
                f.write(f'Total={total} Passed={passed} Failed={failed}\n\n')
                for r in self.test_results:
                    f.write(f'{"PASS" if r["passed"] else "FAIL"}: {r["test"]}'
                            + (f' — {r["message"]}' if r['message'] else '') + '\n')
            print(f'\n  📄 Results: {path}')
        except Exception:
            pass

        return failed == 0


def main():
    tester = PyfpScoringTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
