import sqlite3
import json
import os
from datetime import datetime

# Define DB Path relative to this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "chat_history.db")


def init_db():
    """Creates the necessary tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

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
                     timestamp
                     DATETIME
                     DEFAULT
                     CURRENT_TIMESTAMP
                 )''')

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


def create_session(title="New Chat"):
    """Starts a new chat session and returns its ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id


def save_message(session_id, role, content, sources=None):
    """Saves a single message to the DB."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Convert list of sources to JSON string for storage
    sources_json = json.dumps(sources) if sources else None

    c.execute("INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)",
              (session_id, role, content, sources_json))
    conn.commit()
    conn.close()


def get_sessions():
    """Returns a list of all chat sessions (newest first)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, timestamp FROM sessions ORDER BY id DESC")
    sessions = c.fetchall()
    conn.close()
    return sessions


def get_messages(session_id):
    """Loads all messages for a specific session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content, sources FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
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


def get_session_message_count(session_id):
    """Returns the number of messages in a session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM messages WHERE session_id = ?", (session_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def update_session_title(session_id, new_title):
    """Updates the title of a chat session."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, session_id))
    conn.commit()
    conn.close()


def delete_session(session_id):
    """Deletes a chat session and all its messages."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# Initialize DB on first run
init_db()
