import streamlit as st

from src.ui_core import apply_theme, configure_page, ensure_paths, init_auth_state, show_login

configure_page()
apply_theme()
ensure_paths()
init_auth_state()

if not st.session_state.authenticated:
    show_login()
    st.stop()

if st.session_state.role == "admin":
    st.switch_page("pages/dashboard.py")
else:
    st.switch_page("pages/chat.py")
