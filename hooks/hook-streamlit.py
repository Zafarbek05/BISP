from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('streamlit')
datas += copy_metadata('altair')

hiddenimports = [
    'streamlit.runtime.scriptrunner.magic_funcs',
    'streamlit.web.cli',
    'streamlit.runtime.state.session_state_proxy',
    'streamlit.runtime.scriptrunner.script_run_context',
    'streamlit.runtime.scriptrunner',
    'streamlit.runtime',
    'streamlit.web',
]
