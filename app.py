import os
import sqlite3
from pathlib import Path
import streamlit as st
import src.chat_storage as db
from src.rag_final_answer import ask_gemini

# --- CONFIG & PATHS ---
st.set_page_config(page_title="Semantic Search Assistant", page_icon="🎓", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")
PROCESSED_DB_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_data.db")

if not os.path.exists(RAW_DATA_DIR):
    os.makedirs(RAW_DATA_DIR)

# --- CSS FIX ---
st.markdown("""
    <style>
    /* Main Background */
    .main { background-color: #f5f7f9; }

    /* Chat Bubbles */
    .stChatMessage { border-radius: 15px; }

    /* SIDEBAR BUTTONS - THE FIX */
    /* 1. Force the container div to stretch to 100% */
    [data-testid="stSidebar"] div.stButton {
        width: 100%;
        padding-bottom: 5px; /* Add breathing room between buttons */
    }

    /* 2. Force the actual button to fill the container */
    [data-testid="stSidebar"] button {
        width: 100% !important;
        border-radius: 8px;
        text-align: left;       /* Left align text for better readability */
        padding-left: 15px;     /* nice spacing for text */
        white-space: nowrap;    /* Prevent wrapping */
        overflow: hidden;       /* specific to truncating */
        text-overflow: ellipsis;/* Add ... if too long */
        height: 3rem;           /* Make them slightly taller */
    }

    /* 3. Style for the currently active chat (disabled button) */
    [data-testid="stSidebar"] button:disabled {
        background-color: #e6eefc;
        color: #1a3d7c;
        border-color: #c6d7f5;
        font-weight: bold;
        opacity: 1; /* Fixes dimming issue */
    }

    /* 4. "New Chat" button special styling (optional, makes it stand out) */
    [data-testid="stSidebar"] div.stButton > button:active {
        border-color: #4CAF50;
    }
    </style>
    """, unsafe_allow_html=True)

# --- AUTH ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None


def logout():
    for key in ["authenticated", "user_id", "username", "role", "session_id", "messages"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def show_login():
    st.title("Login")

    if db.get_user_count() == 0:
        st.info("No users found. Create the first admin account.")
        with st.form("create_admin"):
            username = st.text_input("Admin username")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create admin")

        if submitted:
            if not username or not password:
                st.error("Username and password are required.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    user_id = db.create_user(username, password, role="admin")
                    db.assign_legacy_sessions(user_id)
                    st.success("Admin account created. Please log in.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")
    else:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

        if submitted:
            user = db.verify_user(username, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user_id = user["id"]
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                for key in ["session_id", "messages"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            else:
                st.error("Invalid username or password.")


if not st.session_state.authenticated:
    show_login()
    st.stop()

# --- SESSION MANAGEMENT ---
def ensure_active_session():
    user_id = st.session_state.user_id
    sessions = db.get_sessions(user_id)
    current_id = st.session_state.get("session_id")
    if current_id is None or not db.session_belongs_to_user(current_id, user_id):
        if sessions:
            st.session_state.session_id = sessions[0][0]
            st.session_state.messages = db.get_messages(st.session_state.session_id, user_id)
        else:
            st.session_state.session_id = db.create_session(title="New Chat", user_id=user_id)
            st.session_state.messages = []
    elif "messages" not in st.session_state:
        st.session_state.messages = db.get_messages(current_id, user_id)


ensure_active_session()


def load_chat(session_id):
    st.session_state.session_id = session_id
    st.session_state.messages = db.get_messages(session_id, st.session_state.user_id)


def new_chat():
    new_id = db.create_session(title="New Chat", user_id=st.session_state.user_id)
    st.session_state.session_id = new_id
    st.session_state.messages = []


def truncate_title(title, max_len=28):
    if len(title) > max_len:
        return title[:max_len - 2] + ".."
    return title


def delete_current_chat():
    if st.session_state.role != "admin":
        st.warning("Only admins can delete chats.")
        return
    current_id = st.session_state.session_id
    # Ensure delete_session exists in your DB script, otherwise handle error
    if hasattr(db, "delete_session"):
        db.delete_session(current_id, st.session_state.user_id)
        remaining = db.get_sessions(st.session_state.user_id)
        if remaining:
            st.session_state.session_id = remaining[0][0]
            st.session_state.messages = db.get_messages(st.session_state.session_id, st.session_state.user_id)
        else:
            new_chat()
    else:
        st.error("delete_session function missing in chat_storage.py")


def resolve_source_path(source_name):
    """Resolve a source label to an existing local file path when possible."""
    if not source_name:
        return None

    source_name = str(source_name).strip()
    candidates = []

    if os.path.isabs(source_name):
        candidates.append(source_name)
    candidates.append(os.path.join(RAW_DATA_DIR, source_name))
    candidates.append(os.path.join(BASE_DIR, source_name))

    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return os.path.abspath(normalized)
    return None


def render_sources(sources):
    """Render exactly one source link that opens the source folder."""
    if not sources:
        return

    for source in sources:
        source_text = str(source).strip()
        if not source_text:
            continue

        resolved_path = resolve_source_path(source_text)
        label = os.path.basename(source_text) or source_text

        if resolved_path and os.path.isdir(resolved_path):
            folder_path = resolved_path
        elif resolved_path:
            folder_path = os.path.dirname(resolved_path)
        else:
            # Fall back to the raw data directory so the link still opens a folder.
            folder_path = RAW_DATA_DIR

        st.markdown(f"**Source:** [{label}]({Path(folder_path).resolve().as_uri()})")
        return

# --- SIDEBAR ---
with st.sidebar:
    st.title("Search Assistant")
    st.caption(f"Signed in as {st.session_state.username} ({st.session_state.role})")
    if st.button("Logout", use_container_width=True):
        logout()

    st.subheader("💬 Chat History")

    # NEW CHAT BUTTON (Moved to top for better UX)
    if st.button("➕ New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.markdown("---")  # Divider

    # SESSION LIST
    sessions = db.get_sessions(st.session_state.user_id)
    for s_id, s_title, s_time in sessions:
        # Skip empty new chats to keep list clean
        if s_title == "New Chat" and hasattr(db, "get_session_message_count") and db.get_session_message_count(
                s_id, st.session_state.user_id) == 0:
            if s_id != st.session_state.session_id:
                continue

        is_current = (s_id == st.session_state.session_id)

        # We assume styling handles width, but use_container_width=True is a backup
        if st.button(truncate_title(s_title), key=f"session_{s_id}", disabled=is_current, use_container_width=True):
            load_chat(s_id)
            st.rerun()

    st.divider()

    # KNOWLEDGE BASE
    st.subheader("⚙️ Knowledge Base")
    with st.expander("Upload & Refresh"):
        if st.session_state.role != "admin":
            st.info("Admin only.")
        else:
            uploaded_files = st.file_uploader("Upload Docs", accept_multiple_files=True)
            if uploaded_files:
                for f in uploaded_files:
                    with open(os.path.join(RAW_DATA_DIR, f.name), "wb") as w:
                        w.write(f.getbuffer())
                st.success("Files uploaded!")

            if st.button("🔄 Force Refresh", use_container_width=True):
                import subprocess, sys

                crawler = os.path.join(BASE_DIR, "src", "file_crawler.py")
                vector_db = os.path.join(BASE_DIR, "src", "build_vector_db.py")
                try:
                    subprocess.run([sys.executable, crawler], check=True)
                    subprocess.run([sys.executable, vector_db], check=True)
                    st.success("Refreshed!")
                except Exception as e:
                    st.error(str(e))

    # USER MANAGEMENT (ADMIN)
    if st.session_state.role == "admin":
        st.subheader("Users")
        with st.expander("Create User"):
            with st.form("create_user"):
                new_username = st.text_input("Username", key="new_user_username")
                new_password = st.text_input("Password", type="password", key="new_user_password")
                new_role = st.selectbox("Role", ["user", "admin"], index=0, key="new_user_role")
                submitted = st.form_submit_button("Create user")
            if submitted:
                if not new_username or not new_password:
                    st.error("Username and password are required.")
                else:
                    try:
                        db.create_user(new_username, new_password, role=new_role)
                        st.success("User created.")
                    except sqlite3.IntegrityError:
                        st.error("Username already exists.")
                    except ValueError as exc:
                        st.error(str(exc))

    # STATUS
    if os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH):
        st.success("🟢 System Online")
    else:
        st.error("🔴 System Offline")

# --- MAIN CHAT AREA ---
header = st.columns([0.8, 0.2], gap="small")

with header[1]:
    if st.session_state.role == "admin":
        if st.button("🗑️", help="Delete this chat"):
            delete_current_chat()
            st.rerun()
    else:
        st.button("🗑️", help="Admins only", disabled=True)

# Display Messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["sources"]:
            render_sources(message["sources"])

# User Input
if prompt := st.chat_input("Ask a question..."):
    # 1. Show User Message & Save to State/DB
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
    db.save_message(st.session_state.session_id, "user", prompt, user_id=st.session_state.user_id)

    # 2. Generate AI Answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, sources = ask_gemini(prompt)
            st.markdown(answer)
            if sources:
                render_sources(sources)

            # Save Assistant Response
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
            db.save_message(st.session_state.session_id, "assistant", answer, sources, user_id=st.session_state.user_id)

    # 3. AUTO-TITLE LOGIC (Run this LAST)
    # If this was the first interaction (User + AI = 2 messages), update the title
    if len(st.session_state.messages) == 2:
        new_title = (prompt[:30] + '..') if len(prompt) > 30 else prompt
        db.update_session_title(st.session_state.session_id, new_title, st.session_state.user_id)

        st.rerun()


