"""PYFP scoring — HFZ classification and PFT percentile lookup."""
import json

_CACHE: dict = {}


def _load_json(path: str) -> dict:
    if path not in _CACHE:
        with open(path) as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def _default_path(rubric: str, db) -> str | None:
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT json_path FROM pyfp_scoring_table_version WHERE rubric=? AND is_default=1",
            (rubric,)
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT json_path FROM pyfp_scoring_table_version WHERE rubric=? ORDER BY version_id DESC",
                (rubric,)
            ).fetchone()
    return row['json_path'] if row else None


def _age_row(gender_data: dict, age: int) -> dict | None:
    if str(age) in gender_data:
        return gender_data[str(age)]
    ages = sorted(int(k) for k in gender_data)
    if not ages:
        return None
    clamped = max(ages[0], min(ages[-1], age))
    return gender_data.get(str(clamped))


def classify_hfz(course_type: str, raw_value: float, age: int, gender: str, db) -> str:
    """Return 'hfz', 'below_hfz', 'above_hfz', or 'unscored'."""
    path = _default_path('fitnessgram_hfz', db)
    if not path:
        return 'unscored'
    table = _load_json(path)
    ev = table.get('events', {}).get(course_type)
    if not ev:
        return 'unscored'
    row = _age_row(ev.get('by_age_gender', {}).get(gender, {}), age)
    if not row:
        return 'unscored'

    is_better = ev.get('is_better_higher', True)
    lo = row.get('hfz_min', 0)
    hi = row.get('hfz_max', 9999)

    if is_better:
        if raw_value < lo:
            return 'below_hfz'
        if raw_value > hi:
            return 'above_hfz'
        return 'hfz'
    else:
        if raw_value > hi:
            return 'below_hfz'
        if lo > 0 and raw_value < lo:
            return 'above_hfz'
        return 'hfz'


def classify_pft(course_type: str, raw_value: float, age: int, gender: str, db) -> str:
    """Return 'meets', 'below', or 'unscored'."""
    path = _default_path('pft_2026', db)
    if not path:
        return 'unscored'
    table = _load_json(path)
    ev = table.get('events', {}).get(course_type)
    if not ev:
        return 'unscored'
    row = _age_row(ev.get('by_age_gender', {}).get(gender, {}), age)
    if not row:
        return 'unscored'

    p85 = row.get('p85')
    if p85 is None:
        return 'unscored'

    is_better = ev.get('is_better_higher', True)
    if is_better:
        return 'meets' if raw_value >= p85 else 'below'
    else:
        return 'meets' if raw_value <= p85 else 'below'


def get_hfz_range(course_type: str, age: int, gender: str, db) -> dict | None:
    """
    Return the raw HFZ range for a specific event/age/gender, or None if not found.
    Keys: hfz_min, hfz_max, is_better_higher
    """
    path = _default_path('fitnessgram_hfz', db)
    if not path:
        return None
    table = _load_json(path)
    ev = table.get('events', {}).get(course_type)
    if not ev:
        return None
    row = _age_row(ev.get('by_age_gender', {}).get(gender, {}), age)
    if not row:
        return None
    return {
        'hfz_min': row.get('hfz_min', 0),
        'hfz_max': row.get('hfz_max', 9999),
        'is_better_higher': ev.get('is_better_higher', True),
    }


def get_pft_threshold(course_type: str, age: int, gender: str, db) -> dict | None:
    """
    Return the PFT 85th-percentile threshold for a specific event/age/gender, or None.
    Keys: p85, is_better_higher
    """
    path = _default_path('pft_2026', db)
    if not path:
        return None
    table = _load_json(path)
    ev = table.get('events', {}).get(course_type)
    if not ev:
        return None
    row = _age_row(ev.get('by_age_gender', {}).get(gender, {}), age)
    if not row or 'p85' not in row:
        return None
    return {'p85': row['p85'], 'is_better_higher': ev.get('is_better_higher', True)}


def score_battery(battery: dict, results: list, db) -> dict:
    """
    Return {course_type: {'hfz': classification, 'pft': classification}}
    for each event result (best attempt only).
    """
    from field_trainer.pyfp.events_registry import EVENTS

    age    = battery['age_at_test']
    gender = battery['gender']
    rubric = battery['rubric']

    # Deduplicate to best result per course_type
    best: dict[str, dict] = {}
    for r in results:
        ct = r['course_type']
        if ct not in best or r['is_best']:
            best[ct] = r

    scores: dict[str, dict] = {}
    for ct, r in best.items():
        rv = r['raw_value']
        ev_meta = EVENTS.get(ct, {})
        entry: dict = {'hfz': None, 'pft': None}

        if rubric in ('fitnessgram_hfz', 'both') and 'fitnessgram_hfz' in ev_meta.get('rubrics', set()):
            entry['hfz'] = classify_hfz(ct, rv, age, gender, db)

        if rubric in ('pft_2026', 'both') and 'pft_2026' in ev_meta.get('rubrics', set()):
            entry['pft'] = classify_pft(ct, rv, age, gender, db)

        scores[ct] = entry
    return scores
