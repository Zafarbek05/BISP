import os
import warnings

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=False)

try:
    from sqlcipher3 import dbapi2 as sqlcipher
    _HAS_SQLCIPHER = True
except Exception as exc:
    import sqlite3 as sqlcipher
    _HAS_SQLCIPHER = False
    _SQLCIPHER_IMPORT_ERROR = exc

_WARNED_FALLBACK = False


def _get_db_key():
    key = os.getenv("DB_KEY", "")
    if not _HAS_SQLCIPHER:
        return key or None
    if not key:
        raise ValueError("DB_KEY is not set. Add it to your .env file.")
    normalized = key.strip().lower()
    if normalized in {"change-me", "changeme", "default"}:
        raise ValueError("DB_KEY must be set to a non-default value in .env.")
    return key


def connect(path):
    global _WARNED_FALLBACK
    key = _get_db_key()
    conn = sqlcipher.connect(path)
    if _HAS_SQLCIPHER:
        # Use a parameterized PRAGMA to avoid leaking the key in logs.
        try:
            conn.execute("PRAGMA key = ?", (key,))
        except Exception:
            safe_key = key.replace("'", "''")
            conn.execute(f"PRAGMA key = '{safe_key}'")
    else:
        if not _WARNED_FALLBACK:
            warnings.warn(
                "sqlcipher3 is not available; using sqlite3 without encryption.",
                RuntimeWarning,
            )
            _WARNED_FALLBACK = True
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


IntegrityError = sqlcipher.IntegrityError
