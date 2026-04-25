import mimetypes
import os
import re
import subprocess
import sys
import time
from html import escape

import streamlit as st
from streamlit_lottie import st_lottie
from streamlit_option_menu import option_menu

import src.chat_storage as db
import src.ollama_manager as ollama_manager
import src.processed_storage as processed_storage
import src.rag_final_answer as rag_final_answer
import src.settings_manager as settings_manager
from src.ui_utils import LOTTIE_SCANNING_URL, inject_custom_css, load_lottieurl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")
PROCESSED_DB_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_data.db")

RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60


def ensure_paths():
    os.makedirs(RAW_DATA_DIR, exist_ok=True)


def configure_page(title="Semantic Search Assistant"):
    st.set_page_config(page_title=title, page_icon=":speech_balloon:", layout="wide")


def apply_theme():
    inject_custom_css()
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] > .main { padding-top: .6rem; }
        [data-testid="stSidebar"] { border-right: 1px solid rgba(80,120,200,.25); }
        .sidebar-brand { padding: .8rem; border: 1px solid rgba(80,120,200,.2); border-radius: 12px; margin-bottom: .8rem; }
        .section-title { margin: .3rem 0 .6rem; font-weight: 700; }
        .chat-meta { color: #7b8a9f; font-size: .82rem; margin-bottom: .2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_auth_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user_id", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault("role", None)
    st.session_state.setdefault("session_id", None)
    st.session_state.setdefault("rate_limit_timestamps", [])


def logout():
    for key in ["authenticated", "user_id", "username", "role", "session_id", "messages", "rate_limit_timestamps"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def show_login():
    st.title("Secure Access")
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
        return

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
            st.session_state.rate_limit_timestamps = []
            for key in ["session_id", "messages"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        else:
            st.error("Invalid username or password.")


def require_admin():
    if st.session_state.get("role") != "admin":
        st.error("Admin access required.")
        st.stop()


def render_sidebar(active="chat"):
    with st.sidebar:
        st.markdown(
            f"""<div class=\"sidebar-brand\"><b>Semantic Search Assistant</b><br/>{st.session_state.get("username")} ({st.session_state.get("role")})</div>""",
            unsafe_allow_html=True,
        )
        if st.button("Logout", use_container_width=True):
            logout()

        if st.session_state.get("role") == "admin":
            st.markdown("<div class=\"section-title\">Navigation</div>", unsafe_allow_html=True)

            nav_options = ["Dashboard", "Manage", "Chat"]
            nav_icons = ["speedometer2", "folder-symlink", "chat-right-text"]
            active_to_index = {"dashboard": 0, "manage": 1, "chat": 2}

            selected = option_menu(
                menu_title=None,
                options=nav_options,
                icons=nav_icons,
                default_index=active_to_index.get(active, 0),
                styles={"nav-link-selected": {"background-color": "#0077b6"}},
            )

            target_pages = {
                "Dashboard": "pages/dashboard.py",
                "Manage": "pages/manage.py",
                "Chat": "pages/chat.py",
            }
            target_page = target_pages.get(selected)
            current_page = target_pages.get(active.title())
            if target_page and target_page != current_page:
                st.switch_page(target_page)


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


def load_chat(session_id):
    st.session_state.session_id = session_id
    st.session_state.messages = db.get_messages(session_id, st.session_state.user_id)


def new_chat():
    new_id = db.create_session(title="New Chat", user_id=st.session_state.user_id)
    st.session_state.session_id = new_id
    st.session_state.messages = []


def delete_current_chat():
    if st.session_state.role != "admin":
        st.warning("Only admins can delete chats.")
        return
    current_id = st.session_state.session_id
    if hasattr(db, "delete_session"):
        db.delete_session(current_id, st.session_state.user_id)
        sessions = db.get_sessions(st.session_state.user_id)
        if sessions:
            load_chat(sessions[0][0])
        else:
            new_chat()


def get_active_model_label():
    try:
        settings = settings_manager.load_settings()
        rag_settings = settings.get("rag", {}) if isinstance(settings, dict) else {}
    except Exception:
        rag_settings = {}
    engine = (rag_settings.get("engine") or "cloud").strip().lower()
    if engine == "local":
        return f"Local - {rag_settings.get('local_model') or rag_final_answer.DEFAULT_LOCAL_MODEL}"
    return f"Cloud - {rag_settings.get('cloud_model') or rag_final_answer.DEFAULT_CLOUD_MODEL}"


def run_rag_with_status(prompt):
    with st.status("Working...", expanded=True) as status:
        animation_json = load_lottieurl(LOTTIE_SCANNING_URL)
        if animation_json:
            st_lottie(animation_json, height=150, key="loading")
        if rag_final_answer.model_embed is None:
            status.write("Loading embedding model")
        rag_final_answer.get_embedder()
        if rag_final_answer.data_cache.get("chunks") is None or rag_final_answer.data_cache.get("vectors") is None:
            status.write("Loading vectors")
        rag_final_answer.load_processed_data()
        status.write("Generating answer")
        answer, sources = rag_final_answer.ask_rag(prompt)
        status.update(label="Answer ready", state="complete")
        return answer, sources


def render_chat_sidebar_section():
    st.markdown("<div class=\"section-title\">Chat History</div>", unsafe_allow_html=True)
    if st.button("New chat", use_container_width=True):
        new_chat()
        st.rerun()
    current_session_id = st.session_state.get("session_id")
    sessions = list(db.get_sessions(st.session_state.user_id))
    for idx, (s_id, s_title, _) in enumerate(sessions):
        is_current = s_id == current_session_id
        title = (s_title or "").strip()
        if not title or title.lower() == "new chat":
            title = f"Chat {idx + 1}"
        label = title if len(title) <= 28 else title[:26] + ".."
        if st.button(label, key=f"session_{s_id}", disabled=is_current, use_container_width=True):
            load_chat(s_id)
            st.rerun()


def render_chat_messages():
    def _strip_source_markers(text):
        if not text:
            return text
        cleaned_lines = []
        for line in text.splitlines():
            if re.search(r"SOURCE FILE\s*:", line, flags=re.IGNORECASE):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines).strip()

    def _resolve_source_path(sources):
        if not sources:
            return None
        for source in sources:
            if not source:
                continue
            candidate = os.path.abspath(str(source))
            if os.path.exists(candidate):
                return candidate
        return None

    for message in st.session_state.messages:
        role = message.get("role", "assistant")
        with st.chat_message(role):
            meta = get_active_model_label() if role == "assistant" else "You"
            st.markdown(f"<div class=\"chat-meta\">{escape(meta)}</div>", unsafe_allow_html=True)
            content = message.get("content", "")
            st.markdown(_strip_source_markers(content))

            if role == "assistant":
                source_path = _resolve_source_path(message.get("sources", []))
                if source_path:
                    folder_path = os.path.dirname(source_path)
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Open source folder", key=f"open_folder_{message.get('timestamp', id(message))}"):
                            open_in_explorer(folder_path)
                    with col2:
                        if st.button("Open source file", key=f"open_file_{message.get('timestamp', id(message))}"):
                            open_in_explorer(source_path)


def validate_upload(filename, file_bytes):
    expected_mime, _ = mimetypes.guess_type(filename)
    if not expected_mime:
        return False, "Unknown file extension."
    try:
        import magic as _magic

        actual_mime = _magic.from_buffer(file_bytes, mime=True)
    except Exception as exc:
        return False, f"File type detection failed: {exc}"
    if expected_mime != actual_mime and expected_mime.split("/")[0] != "text":
        return False, f"Type mismatch: expected {expected_mime}, detected {actual_mime}."
    return True, actual_mime


def open_in_explorer(path):
    if not path:
        return
    target = os.path.abspath(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isdir(target):
                subprocess.Popen(["explorer", target])
            else:
                os.startfile(target)
    except Exception as exc:
        st.error(f"Failed to open folder: {exc}")
