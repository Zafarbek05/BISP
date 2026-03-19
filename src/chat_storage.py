import json
import os

import bcrypt

try:
    from . import db_cipher
except ImportError:
    import db_cipher

# Define DB Path relative to this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chat_history.db")


IntegrityError = db_cipher.IntegrityError


def _get_conn():
    return db_cipher.connect(DB_PATH)


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def init_db():
    """Creates the necessary tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _get_conn()
    c = conn.cursor()

    # Table for Users
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     username
                     TEXT
                     UNIQUE
                     NOT
                     NULL,
                     password_hash
                     TEXT
                     NOT
                     NULL,
                     role
                     TEXT
                     NOT
                     NULL,
                     created_at
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )''')

    # Table for Chat Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     title
                     TEXT,
                     user_id
                     INTEGER,
                     timestamp
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )''')

    # Ensure user_id column exists for older DBs
    c.execute("PRAGMA table_info(sessions)")
    session_columns = [row[1] for row in c.fetchall()]
    if "user_id" not in session_columns:
        c.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER")

    # Table for Messages
    c.execute('''CREATE TABLE IF NOT EXISTS messages
    (
        id
        INTEGER
        PRIMARY
        KEY
        AUTOINCREMENT,
        session_id
        INTEGER,
        role
        TEXT,
        content
        TEXT,
        sources
        TEXT,
        FOREIGN
        KEY
                 (
        session_id
                 ) REFERENCES sessions
                 (
                     id
                 ))''')

    conn.commit()
    conn.close()


def get_user_count():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count


def create_user(username, password, role="user"):
    if not username or not password:
        raise ValueError("Username and password are required.")
    role = role.strip().lower()
    if role not in {"admin", "user"}:
        raise ValueError("Invalid role.")

    normalized = _normalize_username(username)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = _get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
              (normalized, password_hash, role))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user_by_username(username):
    normalized = _normalize_username(username)
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (normalized,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "password_hash": row[2], "role": row[3]}


def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return {"id": user["id"], "username": user["username"], "role": user["role"]}
    return None


def assign_legacy_sessions(user_id):
    """Assign any legacy sessions without a user_id to the given user."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (user_id,))
    conn.commit()
    conn.close()


def session_belongs_to_user(session_id, user_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    row = c.fetchone()
    conn.close()
    return bool(row)


def create_session(title="New Chat", user_id=None):
    """Starts a new chat session and returns its ID."""
    if user_id is None:
        raise ValueError("user_id is required to create a session.")
    conn = _get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO sessions (title, user_id) VALUES (?, ?)", (title, user_id))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id, role, content, sources=None, user_id=None):
    """Saves a single message to the DB."""
    conn = _get_conn()
    c = conn.cursor()

    # Convert list of sources to JSON string for storage
    sources_json = json.dumps(sources) if sources else None

    if user_id is not None:
        c.execute("SELECT 1 FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        if not c.fetchone():
            conn.close()
            return False

    c.execute("INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)",
              (session_id, role, content, sources_json))
    conn.commit()
    conn.close()
    return True


def get_sessions(user_id):
    """Returns a list of all chat sessions (newest first)."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, timestamp FROM sessions WHERE user_id = ? ORDER BY id DESC", (user_id,))
    sessions = c.fetchall()
    conn.close()
    return sessions


def get_messages(session_id, user_id):
    """Loads all messages for a specific session."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""SELECT m.role, m.content, m.sources
                 FROM messages m
                 JOIN sessions s ON m.session_id = s.id
                 WHERE m.session_id = ? AND s.user_id = ?
                 ORDER BY m.id ASC""", (session_id, user_id))
    rows = c.fetchall()
    conn.close()

    messages = []
    for r in rows:
        messages.append({
            "role": r[0],
            "content": r[1],
            "sources": json.loads(r[2]) if r[2] else []
        })
    return messages


def get_session_message_count(session_id, user_id):
    """Returns the number of messages in a session."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""SELECT COUNT(*)
                 FROM messages m
                 JOIN sessions s ON m.session_id = s.id
                 WHERE m.session_id = ? AND s.user_id = ?""", (session_id, user_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def update_session_title(session_id, new_title, user_id):
    """Updates the title of a chat session."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE sessions SET title = ? WHERE id = ? AND user_id = ?", (new_title, session_id, user_id))
    conn.commit()
    conn.close()


def delete_session(session_id, user_id):
    """Deletes a chat session and all its messages."""
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""DELETE FROM messages
                 WHERE session_id IN (SELECT id FROM sessions WHERE id = ? AND user_id = ?)""",
              (session_id, user_id))
    c.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
    conn.commit()
    conn.close()


def list_users():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return rows


def update_user_role(user_id, role):
    role = role.strip().lower()
    if role not in {"admin", "user"}:
        raise ValueError("Invalid role.")
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()


def reset_user_password(user_id, password):
    if not password:
        raise ValueError("Password is required.")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = _get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""DELETE FROM messages
                 WHERE session_id IN (SELECT id FROM sessions WHERE user_id = ?)""", (user_id,))
    c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def list_sessions_admin(user_id=None):
    conn = _get_conn()
    c = conn.cursor()
    if user_id is None:
        c.execute("""SELECT s.id, s.title, s.timestamp, s.user_id, u.username,
                            (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
                     FROM sessions s
                     JOIN users u ON s.user_id = u.id
                     ORDER BY s.id DESC""")
    else:
        c.execute("""SELECT s.id, s.title, s.timestamp, s.user_id, u.username,
                            (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
                     FROM sessions s
                     JOIN users u ON s.user_id = u.id
                     WHERE s.user_id = ?
                     ORDER BY s.id DESC""", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def delete_session_admin(session_id):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def get_usage_by_user():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("""SELECT u.id, u.username, u.role,
                        COUNT(DISTINCT s.id) AS sessions,
                        COUNT(m.id) AS messages,
                        MAX(s.timestamp) AS last_session
                 FROM users u
                 LEFT JOIN sessions s ON s.user_id = u.id
                 LEFT JOIN messages m ON m.session_id = s.id
                 GROUP BY u.id
                 ORDER BY u.id ASC""")
    rows = c.fetchall()
    conn.close()
    return rows


def get_system_counts():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    admins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sessions")
    sessions = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM messages")
    messages = c.fetchone()[0]
    conn.close()
    return {"users": users, "admins": admins, "sessions": sessions, "messages": messages}


# Initialize DB on first run
init_db()
