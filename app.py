import os
from pathlib import Path
import streamlit as st
import src.chat_storage as db
from src.rag_final_answer import ask_gemini

# --- CONFIG & PATHS ---
st.set_page_config(page_title="Semantic Search Assistant", page_icon="🎓", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")

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

# --- SESSION MANAGEMENT ---
if "session_id" not in st.session_state:
    sessions = db.get_sessions()
    if sessions:
        st.session_state.session_id = sessions[0][0]
        st.session_state.messages = db.get_messages(st.session_state.session_id)
    else:
        st.session_state.session_id = db.create_session(title="New Chat")
        st.session_state.messages = []
elif "messages" not in st.session_state:
    st.session_state.messages = db.get_messages(st.session_state.session_id)


def load_chat(session_id):
    st.session_state.session_id = session_id
    st.session_state.messages = db.get_messages(session_id)


def new_chat():
    new_id = db.create_session(title="New Chat")
    st.session_state.session_id = new_id
    st.session_state.messages = []


def truncate_title(title, max_len=28):
    if len(title) > max_len:
        return title[:max_len - 2] + ".."
    return title


def delete_current_chat():
    current_id = st.session_state.session_id
    # Ensure delete_session exists in your DB script, otherwise handle error
    if hasattr(db, "delete_session"):
        db.delete_session(current_id)
        remaining = db.get_sessions()
        if remaining:
            st.session_state.session_id = remaining[0][0]
            st.session_state.messages = db.get_messages(st.session_state.session_id)
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

    st.subheader("💬 Chat History")

    # NEW CHAT BUTTON (Moved to top for better UX)
    if st.button("➕ New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.markdown("---")  # Divider

    # SESSION LIST
    sessions = db.get_sessions()
    for s_id, s_title, s_time in sessions:
        # Skip empty new chats to keep list clean
        if s_title == "New Chat" and hasattr(db, "get_session_message_count") and db.get_session_message_count(
                s_id) == 0:
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

    # STATUS
    if os.path.exists(PROCESSED_PATH):
        st.success("🟢 System Online")
    else:
        st.error("🔴 System Offline")

# --- MAIN CHAT AREA ---
header = st.columns([0.8, 0.2], gap="small")

with header[1]:
    if st.button("🗑️", help="Delete this chat"):
        delete_current_chat()
        st.rerun()

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
    db.save_message(st.session_state.session_id, "user", prompt)

    # 2. Generate AI Answer
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer, sources = ask_gemini(prompt)
            st.markdown(answer)
            if sources:
                render_sources(sources)

            # Save Assistant Response
            st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
            db.save_message(st.session_state.session_id, "assistant", answer, sources)

    # 3. AUTO-TITLE LOGIC (Run this LAST)
    # If this was the first interaction (User + AI = 2 messages), update the title
    if len(st.session_state.messages) == 2:
        new_title = (prompt[:30] + '..') if len(prompt) > 30 else prompt
        db.update_session_title(st.session_state.session_id, new_title)

        st.rerun()
