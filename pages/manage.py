import os
import sys
import ctypes
from ctypes import wintypes

import streamlit as st

import src.chat_storage as db
import src.ollama_manager as ollama_manager
import src.pipeline as pipeline
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

st.title("Application Management")

users = db.list_users()
user_map = {f"{u[1]} (id {u[0]}, {u[2]})": u[0] for u in users}


def select_folders_with_tk(initial_dir=None):
    if sys.platform.startswith("win"):
        selected, error = _select_folders_windows_native()
        if selected or not error:
            return selected, error

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        return [], f"Tkinter is unavailable: {exc}"

    selected = []
    seen = set()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        current_dir = initial_dir or os.path.expanduser("~")

        while True:
            folder = filedialog.askdirectory(
                parent=root,
                title="Select folder for Knowledge Base",
                initialdir=current_dir,
                mustexist=True,
            )
            if not folder:
                break
            normalized = os.path.normpath(folder)
            if normalized not in seen:
                seen.add(normalized)
                selected.append(normalized)
            current_dir = normalized
    except Exception as exc:
        return [], f"Failed to open folder picker: {exc}"
    finally:
        if root is not None:
            root.destroy()

    return selected, None


def _select_folders_windows_native():
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    def _guid(text):
        import uuid

        u = uuid.UUID(text)
        data4 = (ctypes.c_ubyte * 8)(*u.bytes[8:])
        return GUID(u.time_low, u.time_mid, u.time_hi_version, data4)

    def _vt_call(ptr, index, restype, argtypes, *args):
        vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        fn = ctypes.WINFUNCTYPE(restype, *argtypes)(vtbl[index])
        return fn(*args)

    ole32 = ctypes.windll.ole32
    shell32 = ctypes.windll.shell32
    COINIT_APARTMENTTHREADED = 0x2
    CLSCTX_INPROC_SERVER = 0x1
    FOS_PICKFOLDERS = 0x20
    FOS_FORCEFILESYSTEM = 0x40
    FOS_ALLOWMULTISELECT = 0x200
    FOS_PATHMUSTEXIST = 0x800
    SIGDN_FILESYSPATH = 0x80058000
    ERROR_CANCELLED = 0x800704C7

    clsid_file_open_dialog = _guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")
    iid_file_open_dialog = _guid("D57C7288-D4AD-4768-BE02-9D969532D960")

    dialog_ptr = ctypes.c_void_p()
    hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr not in (0, 1):
        return [], f"Failed to initialize Windows folder picker (HRESULT {hr:#x})."

    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid_file_open_dialog),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(iid_file_open_dialog),
            ctypes.byref(dialog_ptr),
        )
        if hr != 0 or not dialog_ptr.value:
            return [], f"Failed to create folder picker dialog (HRESULT {hr:#x})."

        try:
            options = wintypes.DWORD()
            hr = _vt_call(
                dialog_ptr,
                10,  # IFileDialog::GetOptions
                wintypes.HRESULT,
                [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)],
                dialog_ptr,
                ctypes.byref(options),
            )
            if hr != 0:
                return [], f"Failed to read folder picker options (HRESULT {hr:#x})."

            options.value |= FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM | FOS_ALLOWMULTISELECT | FOS_PATHMUSTEXIST
            hr = _vt_call(
                dialog_ptr,
                9,  # IFileDialog::SetOptions
                wintypes.HRESULT,
                [ctypes.c_void_p, wintypes.DWORD],
                dialog_ptr,
                options.value,
            )
            if hr != 0:
                return [], f"Failed to set folder picker options (HRESULT {hr:#x})."

            title = "Select one or more folders"
            hr = _vt_call(
                dialog_ptr,
                17,  # IFileDialog::SetTitle
                wintypes.HRESULT,
                [ctypes.c_void_p, wintypes.LPCWSTR],
                dialog_ptr,
                title,
            )
            if hr != 0:
                return [], f"Failed to configure folder picker title (HRESULT {hr:#x})."

            hr = _vt_call(
                dialog_ptr,
                3,  # IModalWindow::Show
                wintypes.HRESULT,
                [ctypes.c_void_p, wintypes.HWND],
                dialog_ptr,
                None,
            )
            if hr == ERROR_CANCELLED:
                return [], None
            if hr != 0:
                return [], f"Folder picker did not open successfully (HRESULT {hr:#x})."

            array_ptr = ctypes.c_void_p()
            hr = _vt_call(
                dialog_ptr,
                27,  # IFileOpenDialog::GetResults
                wintypes.HRESULT,
                [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                dialog_ptr,
                ctypes.byref(array_ptr),
            )
            if hr != 0 or not array_ptr.value:
                return [], f"Failed to read selected folders (HRESULT {hr:#x})."

            try:
                count = wintypes.DWORD()
                hr = _vt_call(
                    array_ptr,
                    3,  # IShellItemArray::GetCount
                    wintypes.HRESULT,
                    [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)],
                    array_ptr,
                    ctypes.byref(count),
                )
                if hr != 0:
                    return [], f"Failed to count selected folders (HRESULT {hr:#x})."

                selected = []
                seen = set()
                for idx in range(count.value):
                    item_ptr = ctypes.c_void_p()
                    hr = _vt_call(
                        array_ptr,
                        4,  # IShellItemArray::GetItemAt
                        wintypes.HRESULT,
                        [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p)],
                        array_ptr,
                        idx,
                        ctypes.byref(item_ptr),
                    )
                    if hr != 0 or not item_ptr.value:
                        continue

                    try:
                        path_ptr = ctypes.c_wchar_p()
                        hr = _vt_call(
                            item_ptr,
                            5,  # IShellItem::GetDisplayName
                            wintypes.HRESULT,
                            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_wchar_p)],
                            item_ptr,
                            SIGDN_FILESYSPATH,
                            ctypes.byref(path_ptr),
                        )
                        if hr == 0 and path_ptr.value:
                            normalized = os.path.normpath(path_ptr.value)
                            if normalized not in seen:
                                seen.add(normalized)
                                selected.append(normalized)
                        if path_ptr:
                            ole32.CoTaskMemFree(path_ptr)
                    finally:
                        _vt_call(item_ptr, 2, wintypes.ULONG, [ctypes.c_void_p], item_ptr)  # IUnknown::Release

                return selected, None
            finally:
                _vt_call(array_ptr, 2, wintypes.ULONG, [ctypes.c_void_p], array_ptr)  # IUnknown::Release
        finally:
            _vt_call(dialog_ptr, 2, wintypes.ULONG, [ctypes.c_void_p], dialog_ptr)  # IUnknown::Release
    except Exception as exc:
        return [], f"Windows folder picker failed: {exc}"
    finally:
        ole32.CoUninitialize()


class _StreamlitLogWriter:
    def __init__(self, placeholder):
        self.placeholder = placeholder
        self.buffer = ""

    def write(self, text):
        if not text:
            return
        self.buffer += text
        self.placeholder.code(self.buffer)

    def flush(self):
        return

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
engine = (rag_settings.get("engine") or "cloud").strip().lower()
if engine not in {"cloud", "local"}:
    engine = "cloud"

saved_cloud_model = rag_settings.get("cloud_model") or rag_final_answer.DEFAULT_CLOUD_MODEL
saved_local_model = rag_settings.get("local_model") or rag_final_answer.DEFAULT_LOCAL_MODEL
ollama_url = rag_settings.get("ollama_url") or rag_final_answer.DEFAULT_OLLAMA_URL

selected_engine = st.selectbox(
    "Reasoning mode",
    ["cloud", "local"],
    index=0 if engine == "cloud" else 1,
)

available_cloud_models = [
    *rag_final_answer.SUPPORTED_CLOUD_MODELS,
    rag_final_answer.DEFAULT_CLOUD_MODEL,
]
available_cloud_models = list(dict.fromkeys(available_cloud_models))

if selected_engine == "cloud":
    if saved_cloud_model not in available_cloud_models:
        available_cloud_models.insert(0, saved_cloud_model)
    selected_model = st.selectbox(
        "Cloud model",
        available_cloud_models,
        index=available_cloud_models.index(saved_cloud_model),
    )
else:
    live_local_models, local_error = ollama_manager.list_local_models(ollama_url)
    local_models = list(live_local_models)
    if saved_local_model and saved_local_model not in local_models:
        local_models.insert(0, saved_local_model)
    if rag_final_answer.DEFAULT_LOCAL_MODEL not in local_models:
        local_models.append(rag_final_answer.DEFAULT_LOCAL_MODEL)

    if local_models:
        selected_model = st.selectbox(
            "Local model",
            local_models,
            index=local_models.index(saved_local_model) if saved_local_model in local_models else 0,
        )
        if local_error and not live_local_models:
            st.warning(local_error)
    else:
        selected_model = saved_local_model
        st.warning(local_error or "No local Ollama models found.")
        selected_model = st.text_input("Local model (manual)", value=saved_local_model)

if st.button("Save engine settings"):
    patch = {"rag": {"engine": selected_engine}}
    if selected_engine == "local":
        patch["rag"]["local_model"] = selected_model
        ok, msg = ollama_manager.ensure_ollama_running(ollama_url)
        (st.success if ok else st.error)(msg)
    else:
        patch["rag"]["cloud_model"] = selected_model
        ok, msg = ollama_manager.stop_ollama_server(ollama_url)
        (st.success if ok else st.error)(msg)
    settings_manager.update_settings(patch)
    st.success(f"Saved {selected_engine} reasoning with model: {selected_model}")

st.subheader("Knowledge Base Management")
effective_folders = settings_manager.get_effective_crawler_folders(settings, RAW_DATA_DIR)
st.write("Current effective folder(s):")
st.code("\n".join(effective_folders))

if "kb_selected_folders" not in st.session_state:
    st.session_state["kb_selected_folders"] = effective_folders or []

if st.button("Select folders"):
    picked, picker_error = select_folders_with_tk(
        initial_dir=st.session_state["kb_selected_folders"][0] if st.session_state["kb_selected_folders"] else RAW_DATA_DIR
    )
    if picker_error:
        st.error(picker_error)
    elif picked:
        st.session_state["kb_selected_folders"] = picked
        st.success(f"Selected {len(picked)} folder(s). Click save to apply.")
    else:
        st.warning("No folders selected. Tip: keep selecting folders; click Cancel when done.")

selected_folders = st.session_state.get("kb_selected_folders", [])
if selected_folders:
    st.write("Pending selection:")
    st.code("\n".join(selected_folders))

if st.button("Save and process"):
    settings_manager.update_settings({"crawler": {"folders": selected_folders}})
    st.info(f"Knowledge base folders saved ({len(selected_folders)}). Starting pipeline...")
    log_placeholder = st.empty()
    log_writer = _StreamlitLogWriter(log_placeholder)
    with st.status("Processing selected folders...", expanded=True) as status:
        status.write("Updating crawler settings")
        original_stdout = sys.stdout
        try:
            sys.stdout = log_writer
            status.write("Running crawler and vector builder")
            ok, error = pipeline.run_pipeline("manual from manage")
        finally:
            sys.stdout = original_stdout

        if ok:
            status.update(label="Pipeline completed", state="complete")
            st.success("Pipeline finished successfully. New folders are now processed.")
        else:
            status.update(label="Pipeline failed", state="error")
            st.error(f"Pipeline failed: {error}")

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