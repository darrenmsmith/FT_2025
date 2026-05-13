from field_trainer.db_manager import DatabaseManager

_DB_PATH = '/opt/data/field_trainer.db'
_KEY = 'default_landing'
_VALID = {'coach_dashboard', 'pyfp'}


def get_default_landing() -> str:
    db = DatabaseManager(_DB_PATH)
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT setting_value FROM settings WHERE setting_key = ?", (_KEY,)
        ).fetchone()
    return row['setting_value'] if row else 'coach_dashboard'


def set_default_landing(value: str) -> None:
    if value not in _VALID:
        raise ValueError(f"default_landing must be one of {_VALID}")
    db = DatabaseManager(_DB_PATH)
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE settings SET setting_value = ? WHERE setting_key = ?", (value, _KEY)
        )
