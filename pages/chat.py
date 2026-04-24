import time

import streamlit as st

import src.chat_storage as db
from src.ui_core import (
    apply_theme,
    configure_page,
    delete_current_chat,
    ensure_active_session,
    get_rate_limit_state,
    init_auth_state,
    render_chat_messages,
    render_chat_sidebar_section,
    render_sidebar,
    run_rag_with_status,
)

configure_page("Chat")
apply_theme()
init_auth_state()

if not st.session_state.get("authenticated"):
    st.switch_page("app.py")

ensure_active_session()

render_sidebar(active="chat")
with st.sidebar:
    render_chat_sidebar_section()

st.title("Chat Workspace")
_, action_col = st.columns([0.8, 0.2])
with action_col:
    if st.session_state.get("role") == "admin" and st.button("Delete chat", use_container_width=True):
        delete_current_chat()
        st.rerun()

render_chat_messages()

if prompt := st.chat_input("Ask a question..."):
    _, remaining, retry_after = get_rate_limit_state()
    if remaining <= 0:
        st.error(f"Rate limit exceeded. Try again in {int(retry_after)}s")
        st.stop()

    st.session_state.rate_limit_timestamps.append(time.time())

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": [], "timestamp": time.time()})
    db.save_message(st.session_state.session_id, "user", prompt, user_id=st.session_state.user_id)

    with st.chat_message("assistant"):
        answer, sources = run_rag_with_status(prompt)
        st.markdown(answer)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources, "timestamp": time.time()}
    )
    db.save_message(st.session_state.session_id, "assistant", answer, sources, user_id=st.session_state.user_id)

    if len(st.session_state.messages) == 2:
        new_title = (prompt[:30] + "..") if len(prompt) > 30 else prompt
        db.update_session_title(st.session_state.session_id, new_title, st.session_state.user_id)
    st.rerun()
