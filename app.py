import os
import time
import mimetypes
import subprocess
import sys
import importlib
from pathlib import Path
import streamlit as st
import src.chat_storage as db
import src.env_loader
import src.processed_storage as processed_storage
import src.rag_final_answer as rag_final_answer
import src.settings_manager as settings_manager
import src.ollama_manager as ollama_manager

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
            answer, sources = get_rag_answer(prompt)
            status.update(label="Answer Ready", state="complete")
            return answer, sources
        except Exception:
            status.update(label="Answer Failed", state="error")
            raise


def get_rag_answer(prompt):
    ask_fn = getattr(rag_final_answer, "ask_rag", None)
    if ask_fn is None:
        try:
            importlib.reload(rag_final_answer)
        except Exception:
            pass
        ask_fn = getattr(rag_final_answer, "ask_rag", None)

    if ask_fn is not None:
        return ask_fn(prompt)

    settings = settings_manager.load_settings()
    engine = (settings.get("rag", {}) or {}).get("engine", "cloud")
    if engine == "cloud" and hasattr(rag_final_answer, "ask_gemini"):
        return rag_final_answer.ask_gemini(prompt)

    module_path = getattr(rag_final_answer, "__file__", "unknown")
    raise AttributeError(
        "rag_final_answer.ask_rag is missing. "
        f"Loaded module: {module_path}. "
        "Restart the app to reload updated code."
    )

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


def format_timestamp(epoch_seconds):
    if not epoch_seconds:
        return "Never"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch_seconds))
    except Exception:
        return "Unknown"


def open_in_explorer(path):
    if not path:
        return
    target = os.path.abspath(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isdir(target):
                subprocess.Popen(["explorer", target])
            else:
                subprocess.Popen(["explorer", "/select,", target])
        elif sys.platform == "darwin":
            if os.path.isdir(target):
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["open", "-R", target])
        else:
            folder = target if os.path.isdir(target) else os.path.dirname(target)
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        st.error(f"Failed to open folder: {exc}")


def open_native_file(path):
    if not path:
        return
    target = os.path.abspath(path)
    if not os.path.exists(target):
        st.error("File not found.")
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception as exc:
        st.error(f"Failed to open file: {exc}")


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
    try:
        settings = settings_manager.load_settings()
        crawl_folders = settings_manager.get_effective_crawler_folders(
            settings,
            RAW_DATA_DIR,
            base_dir=BASE_DIR
        )
        for folder in crawl_folders:
            candidates.append(os.path.join(folder, source_name))
    except Exception:
        pass

    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return os.path.abspath(normalized)

    matches = processed_storage.get_paths_by_name(source_name)
    existing = [path for path in matches if os.path.exists(path)]
    if existing:
        existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return os.path.abspath(existing[0])

    return None


def resolve_source_entries(sources):
    entries = []
    seen = set()
    for source in sources or []:
        source_text = str(source).strip()
        if not source_text:
            continue

        resolved_path = resolve_source_path(source_text)
        label = os.path.basename(resolved_path or source_text) or source_text

        file_path = None
        if resolved_path and os.path.isfile(resolved_path):
            file_path = resolved_path

        if resolved_path and os.path.isdir(resolved_path):
            folder_path = resolved_path
        elif resolved_path:
            folder_path = os.path.dirname(resolved_path)
        else:
            folder_path = RAW_DATA_DIR

        dedupe_key = resolved_path or folder_path or source_text
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        entries.append({
            "label": label,
            "file_path": file_path,
            "folder_path": folder_path
        })
    return entries


def render_sources(sources, context_key=""):
    """Render source folder links and native open actions."""
    entries = resolve_source_entries(sources)
    if not entries:
        return

    st.caption("Sources")
    for idx, entry in enumerate(entries):
        folder_path = entry["folder_path"]
        folder_uri = Path(folder_path).resolve().as_uri()
        st.markdown(f"Folder: [{folder_path}]({folder_uri})")

        cols = st.columns([0.45, 0.25, 0.3], gap="small")
        cols[0].markdown(f"File: `{entry['label']}`")

        file_key = f"open_file_{context_key}_{idx}"
        folder_key = f"open_folder_{context_key}_{idx}"
        cols[1].button(
            "Open file",
            key=file_key,
            on_click=open_native_file,
            args=(entry["file_path"],),
            disabled=not entry["file_path"]
        )
        cols[2].button(
            "Open folder",
            key=folder_key,
            on_click=open_in_explorer,
            args=(entry["file_path"] or entry["folder_path"],)
        )

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
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["sources"]:
                render_sources(message["sources"], context_key=f"{message['role']}_{idx}")

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
                render_sources(sources, context_key=f"live_{len(st.session_state.messages)}")

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

    settings = settings_manager.load_settings()
    rag_settings = settings.get("rag", {})
    engine_options = ["Cloud (Gemini)", "Local (Ollama)"]
    engine_map = {
        "Cloud (Gemini)": "cloud",
        "Local (Ollama)": "local",
    }
    current_engine = (rag_settings.get("engine") or "cloud").lower()
    engine_index = 1 if current_engine == "local" else 0

    st.subheader("Reasoning Engine")
    selected_engine = st.selectbox("Engine", engine_options, index=engine_index, key="rag_engine_select")
    st.caption(f"Cloud model: {rag_settings.get('cloud_model', 'gemini-2.5-flash')}")
    st.caption(f"Local model: {rag_settings.get('local_model', 'gemma2:2b')}")
    if st.button("Save engine", use_container_width=True, key="save_rag_engine"):
        selected_key = engine_map[selected_engine]
        action_label = "Loading Ollama" if selected_key == "local" else "Stopping Ollama"
        ok, message = False, ""
        with st.status(action_label, expanded=False) as status:
            settings_manager.update_settings({"rag": {"engine": selected_key}})
            settings = settings_manager.load_settings()
            rag_settings = settings.get("rag", {})
            ollama_url = rag_settings.get("ollama_url") or rag_final_answer.DEFAULT_OLLAMA_URL
            if selected_key == "local":
                ok, message = ollama_manager.ensure_ollama_running(ollama_url)
            else:
                ok, message = ollama_manager.stop_ollama_server(ollama_url)
            if ok:
                status.update(label="Engine Updated", state="complete")
            else:
                status.update(label="Engine Update Failed", state="error")
        if ok:
            st.success(message)
        else:
            st.error(message)

    configured_folders = settings_manager.get_configured_crawler_folders(settings, base_dir=BASE_DIR)
    effective_folders = settings_manager.get_effective_crawler_folders(settings, RAW_DATA_DIR, base_dir=BASE_DIR)

    st.subheader("Crawler Folders")
    st.caption("Leave empty to use the default data/raw folder.")
    folders_text = st.text_area(
        "Folders (one per line)",
        value="\n".join(configured_folders),
        height=120
    )
    if st.button("Save folders", use_container_width=True):
        lines = [line.strip() for line in folders_text.splitlines() if line.strip()]
        normalized = settings_manager.clean_crawler_folders(lines, base_dir=BASE_DIR)
        missing = [path for path in normalized if not os.path.exists(path)]
        if missing:
            st.error("These folders do not exist:\n" + "\n".join(missing))
        else:
            settings_manager.update_settings({"crawler": {"folders": normalized}})
            st.success("Crawler folders updated.")
            settings = settings_manager.load_settings()
            configured_folders = settings_manager.get_configured_crawler_folders(settings, base_dir=BASE_DIR)
            effective_folders = settings_manager.get_effective_crawler_folders(settings, RAW_DATA_DIR, base_dir=BASE_DIR)

    if not configured_folders:
        st.info(f"No folders configured. Using default: {RAW_DATA_DIR}")

    if effective_folders:
        st.caption("Active crawler folders:")
        for idx, folder in enumerate(effective_folders):
            cols = st.columns([0.75, 0.25], gap="small")
            cols[0].markdown(f"`{folder}`")
            cols[1].button(
                "Open folder",
                key=f"open_crawler_folder_{idx}",
                on_click=open_in_explorer,
                args=(folder,)
            )

    st.subheader("Upload and Refresh")
    upload_targets = effective_folders or [RAW_DATA_DIR]
    upload_target = st.selectbox("Upload destination", upload_targets, index=0)

    uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True)
    if uploaded_files:
        saved_count = 0
        for f in uploaded_files:
            file_bytes = f.getvalue()
            is_valid, detail = validate_upload(f.name, file_bytes)
            if not is_valid:
                st.error(f"{f.name}: {detail}")
                continue
            os.makedirs(upload_target, exist_ok=True)
            with open(os.path.join(upload_target, f.name), "wb") as w:
                w.write(file_bytes)
            saved_count += 1
        if saved_count:
            st.success(f"Uploaded {saved_count} file(s).")

    if st.button("Force Refresh", use_container_width=True):
        request_id = settings_manager.request_pipeline_refresh(st.session_state.username)
        st.success(f"Refresh requested (id {request_id}).")

    settings = settings_manager.load_settings()
    pipeline_state = settings.get("pipeline", {})
    request_id = int(pipeline_state.get("refresh_request_id") or 0)
    last_id = int(pipeline_state.get("last_refresh_id") or 0)
    if request_id > last_id:
        st.warning("Refresh queued. The pipeline will run shortly.")
    last_status = pipeline_state.get("last_refresh_status")
    last_time = pipeline_state.get("last_refresh_at")
    if last_status:
        st.caption(f"Last refresh: {format_timestamp(last_time)} ({last_status})")
    last_error = pipeline_state.get("last_refresh_error")
    if last_error and last_status == "error":
        st.error(f"Last refresh error: {last_error}")

    st.subheader("Raw Files")
    folder_for_listing = st.selectbox("Folder", upload_targets, index=0, key="raw_files_folder")
    listing_cols = st.columns([0.75, 0.25], gap="small")
    listing_cols[0].markdown(f"`{folder_for_listing}`")
    listing_cols[1].button(
        "Open folder",
        key="open_raw_folder",
        on_click=open_in_explorer,
        args=(folder_for_listing,)
    )
    try:
        raw_files = sorted([f for f in os.listdir(folder_for_listing)
                            if os.path.isfile(os.path.join(folder_for_listing, f))])
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
                    path = os.path.join(folder_for_listing, filename)
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
