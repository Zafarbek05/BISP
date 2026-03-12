import os
import time
import mimetypes
from pathlib import Path
import streamlit as st
import src.chat_storage as db
import src.env_loader
import src.processed_storage as processed_storage
import src.rag_final_answer as rag_final_answer

# --- CONFIG & PATHS ---
st.set_page_config(page_title="Semantic Search Assistant", page_icon="🎓", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")
PROCESSED_DB_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_data.db")
ADMIN_PAGES = (
    "Admin Home",
    "Admin Users",
    "Admin Chats",
    "Admin Knowledge Base",
    "Admin Usage",
    "Chat",
)

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

# --- RATE LIMITING ---
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60  # seconds


def _prune_rate_limit(now=None):
    now = now or time.time()
    timestamps = st.session_state.get("rate_limit_timestamps", [])
    timestamps = [ts for ts in timestamps if now - ts < RATE_LIMIT_WINDOW]
    st.session_state.rate_limit_timestamps = timestamps
    return now, timestamps


def get_rate_limit_state():
    now, timestamps = _prune_rate_limit()
    used = len(timestamps)
    remaining = max(0, RATE_LIMIT_MAX - used)
    retry_after = 0
    if remaining == 0 and timestamps:
        retry_after = max(0, RATE_LIMIT_WINDOW - (now - min(timestamps)))
    return used, remaining, retry_after


def render_rate_limit(container):
    used, remaining, retry_after = get_rate_limit_state()
    with container:
        st.subheader("Rate Limit")
        st.progress(min(1.0, used / RATE_LIMIT_MAX))
        st.caption(f"{used}/{RATE_LIMIT_MAX} requests in the last {RATE_LIMIT_WINDOW} seconds")
    if remaining == 0:
        st.caption(f"Retry in {int(retry_after)}s")

# --- RAG STATUS HELPERS ---
def run_rag_with_status(prompt):
    with st.status("Working...", expanded=True) as status:
        try:
            if rag_final_answer.model_embed is None:
                status.write("Loading Embedding Model")
            else:
                status.write("Embedding Model Ready")
            rag_final_answer.get_embedder()

            if (rag_final_answer.data_cache.get("chunks") is None
                    or rag_final_answer.data_cache.get("vectors") is None):
                status.write("Loading Vectors")
            else:
                status.write("Vectors Ready")
            rag_final_answer.load_processed_data()

            status.write("Generating Answer")
            answer, sources = rag_final_answer.ask_gemini(prompt)
            status.update(label="Answer Ready", state="complete")
            return answer, sources
        except Exception:
            status.update(label="Answer Failed", state="error")
            raise

# --- AUTH ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None
if "rate_limit_timestamps" not in st.session_state:
    st.session_state.rate_limit_timestamps = []


def logout():
    for key in ["authenticated", "user_id", "username", "role", "session_id", "messages", "rate_limit_timestamps", "page"]:
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
                except db.IntegrityError:
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
                st.session_state.page = "Admin Home" if user["role"] == "admin" else "Chat"
                st.session_state.rate_limit_timestamps = []
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


def get_admin_pages():
    return list(ADMIN_PAGES)


def ensure_admin_page():
    admin_pages = get_admin_pages()
    if "page" not in st.session_state or st.session_state.page not in admin_pages:
        st.session_state.page = admin_pages[0]
    return admin_pages


def set_page(page_name):
    admin_pages = get_admin_pages()
    st.session_state.page = page_name if page_name in admin_pages else admin_pages[0]


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


def _mime_matches(expected, actual):
    if expected == actual:
        return True
    if not expected or not actual:
        return False
    expected_main = expected.split("/")[0]
    actual_main = actual.split("/")[0]
    if expected_main == actual_main and expected_main == "text":
        return True

    compatible = {
        "text/csv": {"text/plain", "text/csv"},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        },
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        },
    }
    return actual in compatible.get(expected, set())


def validate_upload(filename, file_bytes):
    expected_mime, _ = mimetypes.guess_type(filename)
    if not expected_mime:
        return False, "Unknown file extension."
    try:
        try:
            import magic as _magic
        except ImportError:
            return False, "python-magic not available. Install python-magic-bin on Windows."
        actual_mime = _magic.from_buffer(file_bytes, mime=True)
    except Exception as exc:
        return False, f"File type detection failed: {exc}"
    if not _mime_matches(expected_mime, actual_mime):
        return False, f"Type mismatch: expected {expected_mime}, detected {actual_mime}."
    return True, actual_mime


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

# --- PAGES ---

def render_chat_page():
    header = st.columns([0.8, 0.2], gap="small")

    with header[1]:
        if st.session_state.role == "admin":
            if st.button("Delete this chat", help="Delete this chat"):
                delete_current_chat()
                st.rerun()
        else:
            st.button("Delete this chat", help="Admins only", disabled=True)

    # Display Messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["sources"]:
                render_sources(message["sources"])

    # User Input
    if prompt := st.chat_input("Ask a question..."):
        used, remaining, retry_after = get_rate_limit_state()
        if remaining <= 0:
            render_rate_limit(rate_limit_placeholder)
            st.error(f"Rate limit exceeded. Try again in {int(retry_after)} seconds.")
            st.stop()
        st.session_state.rate_limit_timestamps.append(time.time())

        # 1. Show User Message & Save to State/DB
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})
        db.save_message(st.session_state.session_id, "user", prompt, user_id=st.session_state.user_id)

        # 2. Generate AI Answer
        with st.chat_message("assistant"):
            try:
                answer, sources = run_rag_with_status(prompt)
            except Exception as exc:
                st.error(str(exc))
                return

            st.markdown(answer)
            if sources:
                render_sources(sources)

            # Save Assistant Response
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
            db.save_message(st.session_state.session_id, "assistant", answer, sources,
                            user_id=st.session_state.user_id)

        # 3. AUTO-TITLE LOGIC (Run this LAST)
        # If this was the first interaction (User + AI = 2 messages), update the title
        if len(st.session_state.messages) == 2:
            new_title = (prompt[:30] + '..') if len(prompt) > 30 else prompt
            db.update_session_title(st.session_state.session_id, new_title, st.session_state.user_id)

            st.rerun()


def render_admin_home():
    st.title("Admin Home")
    counts = db.get_system_counts()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Users", counts["users"])
    col2.metric("Admins", counts["admins"])
    col3.metric("Sessions", counts["sessions"])
    col4.metric("Messages", counts["messages"])

    st.subheader("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    qa1.button("Manage Users", on_click=set_page, args=("Admin Users",))
    qa2.button("Manage Chats", on_click=set_page, args=("Admin Chats",))
    qa3.button("Manage Knowledge Base", on_click=set_page, args=("Admin Knowledge Base",))

    st.subheader("Knowledge Base Status")
    if os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH):
        st.success("System Online")
    else:
        st.error("System Offline")
    try:
        chunk_count = processed_storage.get_chunk_count()
        st.caption(f"Chunks: {chunk_count}")
    except Exception as exc:
        st.caption(f"Chunk count unavailable: {exc}")
    try:
        raw_files = [f for f in os.listdir(RAW_DATA_DIR) if os.path.isfile(os.path.join(RAW_DATA_DIR, f))]
        st.caption(f"Raw files: {len(raw_files)}")
    except Exception as exc:
        st.caption(f"Raw file count unavailable: {exc}")


def render_admin_users():
    st.title("Admin Users")
    users = db.list_users()
    if users:
        table = []
        for user_id, username, role, created_at in users:
            table.append({
                "id": user_id,
                "username": username,
                "role": role,
                "created_at": created_at
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("No users found.")

    st.subheader("Create User")
    with st.form("admin_create_user"):
        new_username = st.text_input("Username", key="admin_new_user_username")
        new_password = st.text_input("Password", type="password", key="admin_new_user_password")
        new_role = st.selectbox("Role", ["user", "admin"], index=0, key="admin_new_user_role")
        submitted = st.form_submit_button("Create user")
    if submitted:
        if not new_username or not new_password:
            st.error("Username and password are required.")
        else:
            try:
                db.create_user(new_username, new_password, role=new_role)
                st.success("User created.")
            except db.IntegrityError:
                st.error("Username already exists.")
            except ValueError as exc:
                st.error(str(exc))

    if not users:
        return

    user_map = {f"{u[1]} (id {u[0]}, {u[2]})": u[0] for u in users}

    st.subheader("Update Role")
    with st.form("admin_update_role"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_role_user")
        selected_role = st.selectbox("New role", ["user", "admin"], key="admin_role_value")
        submitted = st.form_submit_button("Update role")
    if submitted:
        target_id = user_map.get(selected_label)
        if target_id == st.session_state.user_id and selected_role != "admin":
            st.error("You cannot remove your own admin role.")
        else:
            try:
                db.update_user_role(target_id, selected_role)
                st.success("Role updated.")
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Reset Password")
    with st.form("admin_reset_password"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_pw_user")
        new_password = st.text_input("New password", type="password", key="admin_pw_value")
        confirm_password = st.text_input("Confirm password", type="password", key="admin_pw_confirm")
        submitted = st.form_submit_button("Reset password")
    if submitted:
        if not new_password:
            st.error("Password is required.")
        elif new_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            try:
                db.reset_user_password(user_map.get(selected_label), new_password)
                st.success("Password updated.")
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Delete User")
    with st.form("admin_delete_user"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_delete_user")
        confirm = st.checkbox("I understand this deletes the user and all their chats", key="admin_delete_confirm")
        submitted = st.form_submit_button("Delete user")
    if submitted:
        target_id = user_map.get(selected_label)
        if target_id == st.session_state.user_id:
            st.error("You cannot delete your own account.")
        elif not confirm:
            st.error("Confirmation is required.")
        else:
            db.delete_user(target_id)
            st.success("User deleted.")


def render_admin_chats():
    st.title("Admin Chats")
    users = db.list_users()
    filter_options = [("All users", None)]
    filter_options.extend([(f"{u[1]} (id {u[0]})", u[0]) for u in users])
    filter_label = st.selectbox("Filter by user", [opt[0] for opt in filter_options], key="admin_chat_filter")
    selected_user_id = dict(filter_options)[filter_label]

    sessions = db.list_sessions_admin(selected_user_id)
    if sessions:
        table = []
        for session_id, title, timestamp, user_id, username, message_count in sessions:
            table.append({
                "id": session_id,
                "title": title,
                "user": username,
                "user_id": user_id,
                "messages": message_count,
                "timestamp": timestamp
            })
        st.dataframe(table, use_container_width=True, hide_index=True)

        session_map = {
            f"{row[0]} | {row[4]} | {row[1]}": row[0]
            for row in sessions
        }
        with st.form("admin_delete_sessions"):
            selected = st.multiselect("Delete sessions", list(session_map.keys()))
            confirm = st.checkbox("I understand this deletes the selected chats", key="admin_delete_sessions_confirm")
            submitted = st.form_submit_button("Delete selected")
        if submitted:
            if not selected:
                st.error("Select at least one session.")
            elif not confirm:
                st.error("Confirmation is required.")
            else:
                for label in selected:
                    db.delete_session_admin(session_map[label])
                st.success(f"Deleted {len(selected)} session(s).")
    else:
        st.info("No sessions found.")


def render_admin_knowledge_base():
    st.title("Admin Knowledge Base")

    st.subheader("Upload and Refresh")
    uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True)
    if uploaded_files:
        saved_count = 0
        for f in uploaded_files:
            file_bytes = f.getvalue()
            is_valid, detail = validate_upload(f.name, file_bytes)
            if not is_valid:
                st.error(f"{f.name}: {detail}")
                continue
            with open(os.path.join(RAW_DATA_DIR, f.name), "wb") as w:
                w.write(file_bytes)
            saved_count += 1
        if saved_count:
            st.success(f"Uploaded {saved_count} file(s).")

    if st.button("Force Refresh", use_container_width=True):
        import subprocess, sys

        crawler = os.path.join(BASE_DIR, "src", "file_crawler.py")
        vector_db = os.path.join(BASE_DIR, "src", "build_vector_db.py")
        with st.status("Refreshing knowledge base...", expanded=True) as status:
            try:
                status.write("Running Crawler")
                subprocess.run([sys.executable, crawler], check=True)
                status.write("Building Vectors")
                subprocess.run([sys.executable, vector_db], check=True)
                status.update(label="Refresh Complete", state="complete")
                st.success("Refreshed!")
            except Exception as e:
                status.update(label="Refresh Failed", state="error")
                st.error(str(e))

    st.subheader("Raw Files")
    try:
        raw_files = sorted([f for f in os.listdir(RAW_DATA_DIR) if os.path.isfile(os.path.join(RAW_DATA_DIR, f))])
    except Exception as exc:
        st.error(str(exc))
        raw_files = []

    if raw_files:
        st.dataframe([{"file": f} for f in raw_files], use_container_width=True, hide_index=True)
        with st.form("admin_delete_raw_files"):
            selected = st.multiselect("Delete files", raw_files)
            confirm = st.checkbox("I understand this deletes files from disk", key="admin_delete_files_confirm")
            submitted = st.form_submit_button("Delete selected files")
        if submitted:
            if not selected:
                st.error("Select at least one file.")
            elif not confirm:
                st.error("Confirmation is required.")
            else:
                deleted = 0
                for filename in selected:
                    path = os.path.join(RAW_DATA_DIR, filename)
                    try:
                        os.remove(path)
                        deleted += 1
                    except Exception as exc:
                        st.error(f"Failed to delete {filename}: {exc}")
                if deleted:
                    st.success(f"Deleted {deleted} file(s).")
    else:
        st.info("No raw files found.")


def render_admin_usage():
    st.title("Admin Usage")
    rows = db.get_usage_by_user()
    total_sessions = sum(row[3] for row in rows)
    total_messages = sum(row[4] for row in rows)
    col1, col2 = st.columns(2)
    col1.metric("Total Sessions", total_sessions)
    col2.metric("Total Messages", total_messages)

    if rows:
        table = []
        for user_id, username, role, sessions, messages, last_session in rows:
            table.append({
                "id": user_id,
                "username": username,
                "role": role,
                "sessions": sessions,
                "messages": messages,
                "last_session": last_session
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("No usage data available.")


# --- SIDEBAR ---
with st.sidebar:
    st.title("Search Assistant")
    st.caption(f"Signed in as {st.session_state.username} ({st.session_state.role})")
    if st.button("Logout", use_container_width=True):
        logout()

    rate_limit_placeholder = st.empty()

    if st.session_state.role == "admin":
        st.subheader("Admin Panel")
        admin_pages = ensure_admin_page()
        st.radio("Navigation", admin_pages, key="page")
    else:
        st.session_state.page = "Chat"

    if st.session_state.page == "Chat":
        st.subheader("Chat History")

        if st.button("New Chat", use_container_width=True):
            new_chat()
            st.rerun()

        st.markdown("---")

        sessions = db.get_sessions(st.session_state.user_id)
        for s_id, s_title, s_time in sessions:
            if s_title == "New Chat" and hasattr(db, "get_session_message_count") and db.get_session_message_count(
                    s_id, st.session_state.user_id) == 0:
                if s_id != st.session_state.session_id:
                    continue

            is_current = (s_id == st.session_state.session_id)

            if st.button(truncate_title(s_title), key=f"session_{s_id}", disabled=is_current, use_container_width=True):
                load_chat(s_id)
                st.rerun()

        st.divider()

    if os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH):
        st.success("System Online")
    else:
        st.error("System Offline")


# --- MAIN CONTENT ---
if st.session_state.page == "Chat":
    render_chat_page()
elif st.session_state.page == "Admin Home":
    render_admin_home()
elif st.session_state.page == "Admin Users":
    render_admin_users()
elif st.session_state.page == "Admin Chats":
    render_admin_chats()
elif st.session_state.page == "Admin Knowledge Base":
    render_admin_knowledge_base()
elif st.session_state.page == "Admin Usage":
    render_admin_usage()

render_rate_limit(rate_limit_placeholder)
