import os

import streamlit as st

import src.chat_storage as db
import src.ollama_manager as ollama_manager
import src.rag_final_answer as rag_final_answer
import src.settings_manager as settings_manager
from src.ui_core import (
    RAW_DATA_DIR,
    apply_theme,
    configure_page,
    init_auth_state,
    render_sidebar,
    require_admin,
    validate_upload,
)

configure_page("Admin Manage")
apply_theme()
init_auth_state()

if not st.session_state.get("authenticated"):
    st.switch_page("app.py")

require_admin()
render_sidebar(active="manage")

st.title("Management")

users = db.list_users()
user_map = {f"{u[1]} (id {u[0]}, {u[2]})": u[0] for u in users}

st.subheader("Create User")
with st.form("manage_create_user"):
    new_username = st.text_input("Username")
    new_password = st.text_input("Password", type="password")
    new_role = st.selectbox("Role", ["user", "admin"], index=0)
    create_submit = st.form_submit_button("Create user")
if create_submit:
    if not new_username or not new_password:
        st.error("Username and password are required.")
    else:
        try:
            db.create_user(new_username, new_password, role=new_role)
            st.success("User created.")
        except Exception as exc:
            st.error(str(exc))

st.subheader("Update Role")
with st.form("manage_update_role"):
    selected_label = st.selectbox("User", list(user_map.keys())) if user_map else None
    selected_role = st.selectbox("New role", ["user", "admin"], index=0)
    role_submit = st.form_submit_button("Update role")
if role_submit and selected_label:
    try:
        db.update_user_role(user_map[selected_label], selected_role)
        st.success("Role updated.")
    except Exception as exc:
        st.error(str(exc))

st.subheader("Engine Management")
settings = settings_manager.load_settings()
rag_settings = settings.get("rag", {})
engine = rag_settings.get("engine", "cloud")
selected_engine = st.selectbox("Engine", ["cloud", "local"], index=0 if engine == "cloud" else 1)
if st.button("Save engine"):
    settings_manager.update_settings({"rag": {"engine": selected_engine}})
    ollama_url = rag_settings.get("ollama_url") or rag_final_answer.DEFAULT_OLLAMA_URL
    if selected_engine == "local":
        ok, msg = ollama_manager.ensure_ollama_running(ollama_url)
    else:
        ok, msg = ollama_manager.stop_ollama_server(ollama_url)
    (st.success if ok else st.error)(msg)

st.subheader("Upload Files")
uploaded_files = st.file_uploader("Upload documents", accept_multiple_files=True)
if uploaded_files:
    saved_count = 0
    for uploaded_file in uploaded_files:
        file_bytes = uploaded_file.getvalue()
        is_valid, detail = validate_upload(uploaded_file.name, file_bytes)
        if not is_valid:
            st.error(f"{uploaded_file.name}: {detail}")
            continue
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
        with open(os.path.join(RAW_DATA_DIR, uploaded_file.name), "wb") as target:
            target.write(file_bytes)
        saved_count += 1
    if saved_count:
        st.success(f"Uploaded {saved_count} file(s).")
