import os

import streamlit as st

import src.chat_storage as db
import src.processed_storage as processed_storage
from src.ui_core import (
    PROCESSED_DB_PATH,
    PROCESSED_PATH,
    RAW_DATA_DIR,
    apply_theme,
    configure_page,
    init_auth_state,
    render_sidebar,
    require_admin,
)

configure_page("Admin Dashboard")
apply_theme()
init_auth_state()

if not st.session_state.get("authenticated"):
    st.switch_page("app.py")

require_admin()
render_sidebar(active="dashboard")

st.title("Admin Home")

counts = db.get_system_counts()
st.subheader("System Overview")
card_columns = st.columns(4)
metric_items = [
    ("Users", counts["users"]),
    ("Admins", counts["admins"]),
    ("Sessions", counts["sessions"]),
    ("Messages", counts["messages"]),
]
for col, (label, value) in zip(card_columns, metric_items):
    with col:
        with st.container(border=True):
            st.metric(label, value)

st.subheader("Users Dashboard")
users = db.list_users()
if users:
    st.dataframe(
        [{"id": u[0], "username": u[1], "role": u[2], "created_at": u[3]} for u in users],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No users found.")

st.subheader("Knowledge Base Dashboard")
kb_online = os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH)
kb_chunks = None
try:
    kb_chunks = processed_storage.get_chunk_count()
except Exception as exc:
    st.warning(str(exc))

st.dataframe(
    [
        {
            "component": "knowledge_base",
            "status": "Online" if kb_online else "Offline",
            "chunks": kb_chunks if kb_chunks is not None else "N/A",
        }
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("File and Folder Dashboard")
try:
    raw_files = sorted([f for f in os.listdir(RAW_DATA_DIR) if os.path.isfile(os.path.join(RAW_DATA_DIR, f))])
except Exception as exc:
    raw_files = []
    st.warning(str(exc))

st.dataframe(
    [
        {
            "raw_folder": RAW_DATA_DIR,
            "total_files": len(raw_files),
        }
    ],
    use_container_width=True,
    hide_index=True,
)

if raw_files:
    st.dataframe([{"file": name} for name in raw_files], use_container_width=True, hide_index=True)
else:
    st.info("No raw files found.")
