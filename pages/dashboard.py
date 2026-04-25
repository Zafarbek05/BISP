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
with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("Session Statistics")
    usage_rows = db.get_usage_by_user()
    usage_data = [
        {
            "user_id": row[0],
            "username": row[1],
            "role": row[2],
            "sessions": row[3] or 0,
            "messages": row[4] or 0,
            "last_session": row[5],
        }
        for row in usage_rows
    ]

    total_sessions = counts["sessions"]
    total_messages = counts["messages"]
    active_users = sum(1 for row in usage_data if row["sessions"] > 0)
    avg_messages_per_session = round(total_messages / total_sessions, 2) if total_sessions else 0.0

    stat_col1, stat_col2, stat_col3 = st.columns(3)
    with stat_col1:
        st.metric("Active users", active_users)
    with stat_col2:
        st.metric("Avg messages/session", avg_messages_per_session)
    with stat_col3:
        st.metric("Avg sessions/user", round(total_sessions / counts["users"], 2) if counts["users"] else 0.0)

    if usage_data:
        chart_col1, chart_col2 = st.columns(2)
        usage_by_messages = sorted(usage_data, key=lambda item: item["messages"], reverse=True)
        usage_by_sessions = sorted(usage_data, key=lambda item: item["sessions"], reverse=True)
        with chart_col1:
            st.caption("Top users by messages")
            st.bar_chart(
                {row["username"]: row["messages"] for row in usage_by_messages[:8]},
                use_container_width=True,
            )
        with chart_col2:
            st.caption("Top users by sessions")
            st.bar_chart(
                {row["username"]: row["sessions"] for row in usage_by_sessions[:8]},
                use_container_width=True,
            )

        st.dataframe(
            usage_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "user_id": "User ID",
                "username": "Username",
                "role": "Role",
                "sessions": "Sessions",
                "messages": "Messages",
                "last_session": "Last Session",
            },
        )
    else:
        st.info("No usage data available yet.")
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
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
    st.markdown("</div>", unsafe_allow_html=True)
