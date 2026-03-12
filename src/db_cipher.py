import os
from sqlcipher3 import dbapi2 as sqlcipher

try:
    from . import env_loader
except ImportError:
    import env_loader


def _get_db_key():
    key = os.getenv("DB_KEY")
    if not key:
        raise ValueError("DB_KEY is not set. Add it to your .env file.")
    normalized = key.strip().lower()
    if normalized in {"change-me", "changeme", "default"}:
        raise ValueError("DB_KEY must be set to a non-default value in .env.")
    return key


def connect(path):
    key = _get_db_key()
    conn = sqlcipher.connect(path)
    # Use a parameterized PRAGMA to avoid leaking the key in logs.
    try:
        conn.execute("PRAGMA key = ?", (key,))
    except Exception:
        safe_key = key.replace("'", "''")
        conn.execute(f"PRAGMA key = '{safe_key}'")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


IntegrityError = sqlcipher.IntegrityError
