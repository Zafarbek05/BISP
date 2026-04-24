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
a, b, c, d = st.columns(4)
a.metric("Users", counts["users"])
b.metric("Admins", counts["admins"])
c.metric("Sessions", counts["sessions"])
d.metric("Messages", counts["messages"])

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
st.write(f"Status: {'Online' if kb_online else 'Offline'}")
try:
    st.write(f"Chunks: {processed_storage.get_chunk_count()}")
except Exception as exc:
    st.warning(str(exc))

st.subheader("File and Folder Dashboard")
st.write(f"Raw folder: `{RAW_DATA_DIR}`")
try:
    raw_files = sorted([f for f in os.listdir(RAW_DATA_DIR) if os.path.isfile(os.path.join(RAW_DATA_DIR, f))])
except Exception as exc:
    raw_files = []
    st.warning(str(exc))

if raw_files:
    st.dataframe([{"file": name} for name in raw_files], use_container_width=True, hide_index=True)
else:
    st.info("No raw files found.")
