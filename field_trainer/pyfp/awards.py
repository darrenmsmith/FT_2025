"""PYFP award computation — writes to pyfp_award table."""
import json
from datetime import datetime


def compute_and_write_awards(battery: dict, scores: dict, db) -> list[str]:
    """
    Evaluate scores for award eligibility, persist earned awards, and return
    a list of award_type strings that were earned.
    """
    from field_trainer.pyfp.events_registry import EVENTS

    rubric     = battery['rubric']
    battery_id = battery['battery_id']
    now        = datetime.utcnow().isoformat()
    awarded: list[str] = []

    # --- HFZ All Zones ---
    if rubric in ('fitnessgram_hfz', 'both'):
        hfz_events = [ct for ct, ev in EVENTS.items() if 'fitnessgram_hfz' in ev['rubrics']]
        hfz_results = {ct: scores.get(ct, {}).get('hfz', 'unscored') for ct in hfz_events}
        all_scored = all(v != 'unscored' for v in hfz_results.values())
        all_in     = all(v in ('hfz', 'above_hfz') for v in hfz_results.values())
        if hfz_events and all_scored and all_in:
            _upsert_award(battery_id, 'hfz_all_zones', now, hfz_results, db)
            awarded.append('hfz_all_zones')

    # --- PFT 3-of-6 and Full-6 ---
    if rubric in ('pft_2026', 'both'):
        pft_events  = [ct for ct, ev in EVENTS.items() if 'pft_2026' in ev['rubrics']]
        pft_results = {ct: scores.get(ct, {}).get('pft', 'unscored') for ct in pft_events}
        meets_count = sum(1 for v in pft_results.values() if v == 'meets')

        if meets_count >= 3:
            _upsert_award(battery_id, 'pft_3_of_6', now, pft_results, db)
            awarded.append('pft_3_of_6')
        if pft_events and meets_count == len(pft_events):
            _upsert_award(battery_id, 'pft_full_6', now, pft_results, db)
            awarded.append('pft_full_6')

    return awarded


def _upsert_award(battery_id: str, award_type: str, now: str, criteria: dict, db) -> None:
    with db.get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO pyfp_award
                   (battery_id, award_type, awarded_at, criteria_met)
               VALUES (?, ?, ?, ?)""",
            (battery_id, award_type, now, json.dumps(criteria)),
        )
