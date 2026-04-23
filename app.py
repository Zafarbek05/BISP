import os
import time
import mimetypes
import subprocess
import sys
import importlib
from string import Template
from pathlib import Path
from html import escape
import streamlit as st
import src.chat_storage as db
import src.processed_storage as processed_storage
import src.rag_final_answer as rag_final_answer
import src.settings_manager as settings_manager
import src.ollama_manager as ollama_manager

# --- CONFIG & PATHS ---
st.set_page_config(page_title="Semantic Search Assistant", page_icon="🎓", layout="wide")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")
PROCESSED_DB_PATH = os.path.join(BASE_DIR, "data", "processed", "processed_data.db")
ADMIN_PAGES = (
    "Admin Home",
    "Admin Users",
    "Admin Chats",
    "Admin Knowledge Base",
    "Admin Usage",
    "Chat",
)

if not os.path.exists(RAW_DATA_DIR):
    os.makedirs(RAW_DATA_DIR)

# --- UI THEME ---
theme_base = (st.get_option("theme.base") or "light").lower()
is_light_theme = theme_base == "light"

theme_tokens = {
    "bg_start": "#f5f8ff" if is_light_theme else "#040b16",
    "bg_mid": "#eef4ff" if is_light_theme else "#07111f",
    "bg_end": "#e8eefb" if is_light_theme else "#0b1627",
    "header_bg": "rgba(255, 255, 255, 0.78)" if is_light_theme else "rgba(4, 11, 22, 0.62)",
    "grid_line": "rgba(26, 44, 74, 0.05)" if is_light_theme else "rgba(255, 255, 255, 0.025)",
    "panel": "rgba(255, 255, 255, 0.72)" if is_light_theme else "rgba(12, 24, 40, 0.76)",
    "panel_border": "rgba(79, 140, 255, 0.14)" if is_light_theme else "rgba(122, 162, 255, 0.16)",
    "text": "#10213a" if is_light_theme else "#e8f0ff",
    "muted": "#5d7192" if is_light_theme else "#8ea3c4",
    "accent": "#1478ff" if is_light_theme else "#6ee7ff",
    "accent_2": "#3a68ff" if is_light_theme else "#4f8cff",
    "success": "#16a34a" if is_light_theme else "#4ade80",
    "warning": "#d97706",
    "danger": "#dc2626" if is_light_theme else "#fb7185",
    "shadow": "0 20px 50px rgba(39, 71, 125, 0.12)" if is_light_theme else "0 24px 60px rgba(1, 8, 20, 0.45)",
    "sidebar_bg": "linear-gradient(180deg, rgba(248, 251, 255, 0.96), rgba(237, 243, 255, 0.94))"
                  if is_light_theme else
                  "linear-gradient(180deg, rgba(5, 13, 24, 0.95), rgba(7, 17, 31, 0.94))",
    "chat_bg": "rgba(255, 255, 255, 0.72)" if is_light_theme else "rgba(9, 21, 36, 0.68)",
    "chat_user_bg": "rgba(229, 238, 255, 0.95)" if is_light_theme else "rgba(21, 40, 67, 0.84)",
    "input_bg": "rgba(255, 255, 255, 0.92)" if is_light_theme else "rgba(8, 19, 32, 0.9)",
    "admin_chip": "rgba(20, 120, 255, 0.12)" if is_light_theme else "rgba(110, 231, 255, 0.14)",
    "border_subtle": "rgba(16, 33, 58, 0.08)" if is_light_theme else "rgba(232, 240, 255, 0.11)",
    "radius_sm": "12px",
    "radius_md": "16px",
    "radius_lg": "22px",
    "space_1": "0.375rem",
    "space_2": "0.5rem",
    "space_3": "0.75rem",
    "space_4": "1rem",
    "space_5": "1.5rem",
    "space_6": "2rem",
    "font_sm": "0.82rem",
    "font_md": "0.96rem",
    "font_lg": "1.16rem",
    "font_xl": "clamp(1.9rem, 3vw, 2.8rem)",
    "content_max": "1200px",
}

theme_css = Template("""
    <style>
    :root {
        --panel: $panel;
        --panel-border: $panel_border;
        --border-subtle: $border_subtle;
        --text: $text;
        --muted: $muted;
        --accent: $accent;
        --accent-2: $accent_2;
        --success: $success;
        --warning: $warning;
        --danger: $danger;
        --shadow: $shadow;
        --admin-chip: $admin_chip;
        --radius-sm: $radius_sm;
        --radius-md: $radius_md;
        --radius-lg: $radius_lg;
        --space-1: $space_1;
        --space-2: $space_2;
        --space-3: $space_3;
        --space-4: $space_4;
        --space-5: $space_5;
        --space-6: $space_6;
        --font-sm: $font_sm;
        --font-md: $font_md;
        --font-lg: $font_lg;
        --font-xl: $font_xl;
        --content-max: $content_max;
    }

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background:
            radial-gradient(circle at top left, rgba(79, 140, 255, 0.18), transparent 32%),
            radial-gradient(circle at top right, rgba(110, 231, 255, 0.10), transparent 28%),
            linear-gradient(180deg, $bg_start 0%, $bg_mid 45%, $bg_end 100%);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: $header_bg;
        backdrop-filter: blur(12px);
        border-bottom: 1px solid $panel_border;
    }

    [data-testid="stAppViewContainer"] > .main {
        background-image:
            linear-gradient($grid_line 1px, transparent 1px),
            linear-gradient(90deg, $grid_line 1px, transparent 1px);
        background-size: 36px 36px;
    }

    [data-testid="block-container"] {
        max-width: var(--content-max);
        margin: 0 auto;
        padding-top: var(--space-6);
        padding-bottom: var(--space-6);
        padding-left: var(--space-4);
        padding-right: var(--space-4);
    }

    .page-shell {
        position: relative;
        display: grid;
        gap: var(--space-5);
    }

    .workspace-shell::before {
        content: "";
        position: absolute;
        inset: -0.2rem -0.2rem auto -0.2rem;
        height: 170px;
        pointer-events: none;
        background: radial-gradient(circle at 75% 0%, color-mix(in srgb, var(--accent-2) 14%, transparent), transparent 58%);
        z-index: -1;
    }

    .page-hero {
        padding: calc(var(--space-5) + var(--space-2)) calc(var(--space-5) + var(--space-3));
        border-radius: var(--radius-lg);
        border: 1px solid var(--panel-border);
        background:
            linear-gradient(135deg, rgba(79, 140, 255, 0.18), var(--panel) 42%, rgba(110, 231, 255, 0.08));
        box-shadow: var(--shadow);
    }

    .page-kicker {
        font-size: var(--font-sm);
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--accent);
        font-weight: 700;
        margin-bottom: var(--space-2);
    }

    .page-title {
        font-size: var(--font-xl);
        line-height: 1.05;
        margin: 0;
        font-weight: 800;
        color: var(--text);
    }

    .page-subtitle {
        margin-top: var(--space-2);
        max-width: 58rem;
        color: var(--muted);
        font-size: var(--font-md);
    }

    .page-header-actions {
        margin-top: var(--space-3);
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-3);
    }

    .panel {
        padding: var(--space-5);
        margin-bottom: var(--space-5);
        border-radius: var(--radius-md);
        background: var(--panel);
        border: 1px solid var(--panel-border);
        box-shadow: var(--shadow);
        backdrop-filter: blur(18px);
    }

    .panel.tight {
        padding-top: calc(var(--space-4) + var(--space-1));
    }

    .admin-shell {
        position: relative;
    }

    .admin-shell::before {
        content: "";
        position: absolute;
        inset: -0.4rem -0.4rem auto -0.4rem;
        height: 220px;
        pointer-events: none;
        background: radial-gradient(circle at 20% 0%, color-mix(in srgb, var(--accent) 20%, transparent), transparent 58%);
        z-index: -1;
    }

    .admin-shell .page-hero {
        border-radius: var(--radius-lg);
        background:
            linear-gradient(125deg, color-mix(in srgb, var(--accent) 18%, transparent), var(--panel) 48%, color-mix(in srgb, var(--accent-2) 18%, transparent));
    }

    .admin-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        margin: 0 0 var(--space-3);
        padding: var(--space-1) var(--space-3);
        border-radius: 999px;
        border: 1px solid var(--border-subtle);
        background: var(--admin-chip);
        color: var(--text);
        font-size: var(--font-sm);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
    }

    .badge {
        display: inline-flex;
        align-items: center;
        gap: var(--space-2);
        margin: 0 0 var(--space-3);
        padding: var(--space-1) var(--space-3);
        border-radius: 999px;
        border: 1px solid var(--border-subtle);
        font-size: var(--font-sm);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
    }

    .badge-info {
        background: color-mix(in srgb, var(--accent) 16%, transparent);
        color: var(--accent);
    }

    .badge-admin {
        background: var(--admin-chip);
        color: var(--text);
    }

    .badge-success {
        background: color-mix(in srgb, var(--success) 20%, transparent);
        color: var(--success);
    }

    .admin-panel-note {
        margin: -0.2rem 0 var(--space-4);
        color: var(--muted);
        font-size: var(--font-md);
    }

    .admin-toolbar {
        margin-top: 0.3rem;
        display: grid;
        gap: 0.75rem;
    }

    .admin-shell [data-testid="stDataFrame"] {
        border-radius: 18px;
        box-shadow: 0 16px 40px rgba(1, 8, 20, 0.14);
    }

    .admin-shell .stForm {
        padding: 0.35rem 0.1rem 0.2rem;
    }

    .section-label {
        margin-bottom: var(--space-4);
        color: var(--text);
        font-size: var(--font-lg);
        font-weight: 700;
        letter-spacing: 0.01em;
    }

    .metric-card {
        padding: calc(var(--space-4) + var(--space-1)) var(--space-4);
        border-radius: var(--radius-md);
        background: linear-gradient(180deg, color-mix(in srgb, var(--panel) 86%, white 14%), var(--panel));
        border: 1px solid var(--panel-border);
        box-shadow: var(--shadow);
    }

    .stats-row {
        margin-top: var(--space-5);
        margin-bottom: var(--space-5);
    }

    .section-separator {
        height: 1px;
        margin: var(--space-4) 0;
        border-radius: 999px;
        background: linear-gradient(
            90deg,
            color-mix(in srgb, var(--panel-border) 60%, transparent),
            color-mix(in srgb, var(--border-subtle) 100%, transparent),
            color-mix(in srgb, var(--panel-border) 60%, transparent)
        );
    }

    .metric-label {
        color: var(--muted);
        font-size: var(--font-sm);
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: var(--space-2);
    }

    .metric-value {
        color: var(--text);
        font-size: 1.75rem;
        line-height: 1;
        font-weight: 800;
    }

    .metric-note {
        margin-top: var(--space-2);
        color: var(--accent);
        font-size: var(--font-sm);
    }

    .metric-note.metric-positive {
        color: var(--success);
    }

    .card {
        padding: var(--space-5);
        border-radius: var(--radius-md);
        border: 1px solid var(--panel-border);
        background: color-mix(in srgb, var(--panel) 93%, transparent);
    }

    .card-title {
        color: var(--text);
        font-size: var(--font-lg);
        font-weight: 700;
        margin-bottom: var(--space-2);
    }

    .card-body {
        color: var(--muted);
        font-size: var(--font-md);
    }

    .card-footer {
        margin-top: var(--space-3);
        color: var(--muted);
        font-size: var(--font-sm);
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.42rem 0.78rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: var(--text);
        font-size: 0.85rem;
        font-weight: 600;
    }

    .status-pill::before {
        content: "";
        width: 0.6rem;
        height: 0.6rem;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 14px currentColor;
    }

    .status-pill.online::before { background: var(--success); }
    .status-pill.offline::before { background: var(--danger); }

    .source-card {
        padding: var(--space-4);
        margin: var(--space-2) 0 var(--space-4);
        border-radius: var(--radius-md);
        border: 1px solid var(--panel-border);
        background: color-mix(in srgb, var(--panel) 92%, transparent);
    }

    .source-title {
        color: var(--muted);
        font-size: var(--font-sm);
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: var(--space-1);
    }

    .source-file {
        color: var(--text);
        font-weight: 600;
    }

    .login-shell {
        max-width: 540px;
        margin: 3rem auto 0;
    }

    .login-shell h1 {
        margin-bottom: 0.35rem;
    }

    [data-testid="stSidebar"] {
        background:
            $sidebar_bg,
            radial-gradient(circle at top, rgba(79, 140, 255, 0.16), transparent 30%);
        border-right: 1px solid var(--panel-border);
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1rem;
    }

    [data-testid="stSidebar"] div.stButton {
        width: 100%;
        padding-bottom: 0.42rem;
    }

    .sidebar-brand {
        padding: 1rem 1rem 1.1rem;
        border-radius: 18px;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, rgba(79, 140, 255, 0.22), color-mix(in srgb, var(--panel) 92%, transparent));
        border: 1px solid var(--panel-border);
    }

    .sidebar-title {
        color: var(--text);
        font-size: 1.15rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
    }

    .sidebar-subtitle {
        color: var(--muted);
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .sidebar-section {
        margin: 1.1rem 0 0.7rem;
        color: var(--muted);
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        font-weight: 700;
    }

    [data-testid="stSidebar"] button,
    .stButton > button,
    .stDownloadButton > button {
        width: 100% !important;
        min-height: 3rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--panel-border);
        background: linear-gradient(180deg, color-mix(in srgb, var(--panel) 76%, rgba(79, 140, 255, 0.04)), var(--panel));
        color: var(--text);
        box-shadow: 0 14px 30px rgba(1, 8, 20, 0.10);
        transition: all 0.18s ease;
    }

    [data-testid="stSidebar"] button {
        text-align: left;
        padding-left: 0.95rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    [data-testid="stSidebar"] button:hover,
    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: color-mix(in srgb, var(--accent) 45%, white);
        transform: translateY(-1px);
    }

    [data-testid="stSidebar"] button:disabled {
        background: linear-gradient(180deg, rgba(79, 140, 255, 0.22), color-mix(in srgb, var(--panel) 95%, transparent));
        border-color: color-mix(in srgb, var(--accent) 24%, white);
        color: var(--text);
        opacity: 1;
        font-weight: 700;
    }

    .stChatMessage {
        border-radius: var(--radius-md);
        border: 1px solid var(--panel-border);
        padding: var(--space-3);
        background: $chat_bg;
        box-shadow: 0 6px 14px rgba(1, 8, 20, 0.07);
    }

    [data-testid="stChatMessageAvatarUser"] + div .stChatMessage {
        background: $chat_user_bg;
    }

    .chat-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: var(--space-3);
        margin-bottom: var(--space-2);
    }

    .chat-meta-time {
        color: var(--muted);
        font-size: var(--font-sm);
    }

    .chat-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        border: 1px solid var(--border-subtle);
        padding: 0.22rem var(--space-2);
        font-size: var(--font-sm);
        color: var(--accent);
        background: color-mix(in srgb, var(--accent) 12%, transparent);
    }

    .chat-badge.user {
        color: var(--text);
        background: color-mix(in srgb, var(--panel) 90%, transparent);
    }

    .chat-thinking {
        margin-bottom: var(--space-2);
        color: var(--muted);
        font-size: var(--font-md);
    }

    .chat-input-hint {
        margin-top: calc(var(--space-3) * -1);
        margin-bottom: var(--space-4);
        color: var(--muted);
        font-size: var(--font-sm);
    }

    [data-testid="stChatInput"] {
        background: $input_bg;
        border: 1px solid var(--panel-border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow);
    }

    [data-testid="stMetric"] {
        background: transparent;
        border: none;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    .stTextArea textarea,
    .stTextInput input,
    .stNumberInput input,
    .stDateInput input {
        background: $input_bg !important;
        color: var(--text) !important;
        border: 1px solid var(--panel-border) !important;
        border-radius: var(--radius-sm) !important;
    }

    .stRadio > div,
    .stCheckbox {
        color: var(--text);
    }

    [data-testid="stDataFrame"] {
        border-radius: var(--radius-md);
        overflow: hidden;
        border: 1px solid var(--panel-border);
        background: color-mix(in srgb, var(--panel) 94%, transparent);
    }

    .stAlert {
        border-radius: var(--radius-md);
        border-width: 1px;
    }

    .stMarkdown, p, label, .stCaption {
        color: var(--text);
    }

    .stCaption {
        color: var(--muted);
    }

    hr, [data-testid="stDivider"] {
        border-color: var(--panel-border);
    }
    </style>
    """).substitute(theme_tokens)

st.markdown(theme_css, unsafe_allow_html=True)

# --- RATE LIMITING ---
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60  # seconds


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


def render_rate_limit(container):
    used, remaining, retry_after = get_rate_limit_state()
    with container:
        st.subheader("Rate Limit")
        st.progress(min(1.0, used / RATE_LIMIT_MAX))
        st.caption(f"{used}/{RATE_LIMIT_MAX} requests in the last {RATE_LIMIT_WINDOW} seconds")
    if remaining == 0:
        st.caption(f"Retry in {int(retry_after)}s")


def render_page_header(title, subtitle, kicker="Control Surface", actions=None):
    actions_html = f'<div class="page-header-actions">{actions}</div>' if actions else ""
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-kicker">{escape(str(kicker))}</div>
            <h1 class="page-title">{escape(str(title))}</h1>
            <div class="page-subtitle">{escape(str(subtitle))}</div>
            {actions_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badge(text, kind="info"):
    allowed = {"info", "admin", "success"}
    kind = kind if kind in allowed else "info"
    st.markdown(f'<div class="badge badge-{kind}">{escape(str(text))}</div>', unsafe_allow_html=True)


def render_admin_pill(text):
    render_badge(text, kind="admin")


def render_admin_panel_note(text):
    st.markdown(f'<div class="admin-panel-note">{text}</div>', unsafe_allow_html=True)


def open_panel(label=None, tight=False):
    panel_class = "panel tight" if tight else "panel"
    st.markdown(f'<div class="{panel_class}">', unsafe_allow_html=True)
    if label:
        st.markdown(f'<div class="section-label">{escape(str(label))}</div>', unsafe_allow_html=True)


def close_panel():
    st.markdown("</div>", unsafe_allow_html=True)


def render_card(title, body, footer=None, tone="default"):
    tone_class = f" card-{tone}" if tone and tone != "default" else ""
    body_html = escape(str(body)).replace("\n", "<br>")
    st.markdown(f'<div class="card{tone_class}">', unsafe_allow_html=True)
    st.markdown(f'<div class="card-title">{escape(str(title))}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="card-body">{body_html}</div>', unsafe_allow_html=True)
    if footer:
        st.markdown(f'<div class="card-footer">{escape(str(footer))}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_separator():
    st.markdown('<div class="section-separator"></div>', unsafe_allow_html=True)


def render_stat_kpi(column, label, value, delta=None):
    note_class = "metric-note metric-positive" if delta and str(delta).strip().startswith(("+", "↑")) else "metric-note"
    delta_html = f'<div class="{note_class}">{escape(str(delta))}</div>' if delta else ""
    column.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{escape(str(label))}</div>
            <div class="metric-value">{escape(str(value))}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_card(column, label, value, note):
    render_stat_kpi(column, label, value, delta=note)


def render_system_pill(is_online):
    status_class = "online" if is_online else "offline"
    status_text = "System Online" if is_online else "System Offline"
    st.markdown(f'<div class="status-pill {status_class}">{status_text}</div>', unsafe_allow_html=True)


def get_page_shell_config(page_name):
    configs = {
        "Chat": {
            "title": "AI Search Console",
            "subtitle": "Interact with the knowledge base through a cleaner chat surface and quick source access.",
            "kicker": "Conversation",
            "badge": "Workspace",
            "badge_kind": "info",
        },
        "Admin Home": {
            "title": "Admin Home",
            "subtitle": "Monitor the platform, jump to critical controls, and keep the knowledge base healthy.",
            "kicker": "Operations",
            "badge": "Admin Workspace",
            "badge_kind": "admin",
        },
        "Admin Users": {
            "title": "Admin Users",
            "subtitle": "Create accounts, assign roles, and handle access management without touching application logic.",
            "kicker": "Identity",
            "badge": "Identity & Access",
            "badge_kind": "admin",
        },
        "Admin Chats": {
            "title": "Admin Chats",
            "subtitle": "Audit conversation history, filter by owner, and remove sessions when required.",
            "kicker": "Conversation Ops",
            "badge": "Conversation Governance",
            "badge_kind": "admin",
        },
        "Admin Knowledge Base": {
            "title": "Admin Knowledge Base",
            "subtitle": "Configure retrieval, manage crawler folders, upload source files, and trigger refreshes.",
            "kicker": "Index Management",
            "badge": "Knowledge Operations",
            "badge_kind": "admin",
        },
        "Admin Usage": {
            "title": "Admin Usage",
            "subtitle": "Track adoption across users and get a high-level view of session and message volume.",
            "kicker": "Analytics",
            "badge": "Platform Analytics",
            "badge_kind": "admin",
        },
    }
    default = {
        "title": page_name,
        "subtitle": "",
        "kicker": "Workspace",
        "badge": "Workspace",
        "badge_kind": "info",
    }
    return configs.get(page_name, default)


def render_app_shell(page_name):
    shell_class = "admin-shell" if page_name.startswith("Admin") else "workspace-shell"
    st.markdown(f'<div class="page-shell {shell_class}">', unsafe_allow_html=True)
    config = get_page_shell_config(page_name)
    badge_text = config.get("badge")
    if badge_text:
        render_badge(badge_text, config.get("badge_kind", "info"))
    render_page_header(
        config.get("title", page_name),
        config.get("subtitle", ""),
        kicker=config.get("kicker", "Workspace")
    )


def close_app_shell():
    st.markdown("</div>", unsafe_allow_html=True)


def get_active_model_label():
    try:
        settings = settings_manager.load_settings()
        rag_settings = settings.get("rag", {}) if isinstance(settings, dict) else {}
    except Exception:
        rag_settings = {}

    engine = (rag_settings.get("engine") or "cloud").strip().lower()
    if engine == "local":
        model = rag_settings.get("local_model") or rag_final_answer.DEFAULT_LOCAL_MODEL
        return f"Local · {model}"
    model = rag_settings.get("cloud_model") or rag_final_answer.DEFAULT_CLOUD_MODEL
    return f"Cloud · {model}"


def format_chat_clock(epoch_seconds):
    if not epoch_seconds:
        return "Now"
    try:
        return time.strftime("%H:%M", time.localtime(epoch_seconds))
    except Exception:
        return "Now"


def normalize_loaded_messages(messages):
    normalized = []
    active_model = get_active_model_label()
    for message in messages or []:
        item = dict(message)
        item.setdefault("timestamp", None)
        if item.get("role") == "assistant":
            item.setdefault("model_label", active_model)
        normalized.append(item)
    return normalized


def render_chat_meta(role, timestamp_text, model_label=None):
    badge_value = model_label if role == "assistant" else "You"
    badge_class = "chat-badge" if role == "assistant" else "chat-badge user"
    st.markdown(
        f"""
        <div class="chat-meta">
            <span class="chat-meta-time">{escape(str(timestamp_text))}</span>
            <span class="{badge_class}">{escape(str(badge_value))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_section(label):
    st.markdown(f'<div class="sidebar-section">{label}</div>', unsafe_allow_html=True)


def render_admin_sidebar_nav():
    admin_pages = ensure_admin_page()
    render_sidebar_section("Admin Panel")
    for page in admin_pages:
        is_current = st.session_state.page == page
        if st.button(page, key=f"admin_nav_{page}", disabled=is_current, use_container_width=True):
            set_page(page)
            st.rerun()

# --- RAG STATUS HELPERS ---
def run_rag_with_status(prompt):
    with st.status("Working...", expanded=True) as status:
        try:
            if rag_final_answer.model_embed is None:
                status.write("Loading Embedding Model")
            else:
                status.write("Embedding Model Ready")
            rag_final_answer.get_embedder()

            if (rag_final_answer.data_cache.get("chunks") is None
                    or rag_final_answer.data_cache.get("vectors") is None):
                status.write("Loading Vectors")
            else:
                status.write("Vectors Ready")
            rag_final_answer.load_processed_data()

            status.write("Generating Answer")
            answer, sources = get_rag_answer(prompt)
            status.update(label="Answer Ready", state="complete")
            return answer, sources
        except Exception:
            status.update(label="Answer Failed", state="error")
            raise


def get_rag_answer(prompt):
    ask_fn = getattr(rag_final_answer, "ask_rag", None)
    if ask_fn is None:
        try:
            importlib.reload(rag_final_answer)
        except Exception:
            pass
        ask_fn = getattr(rag_final_answer, "ask_rag", None)

    if ask_fn is not None:
        return ask_fn(prompt)

    settings = settings_manager.load_settings()
    engine = (settings.get("rag", {}) or {}).get("engine", "cloud")
    if engine == "cloud" and hasattr(rag_final_answer, "ask_gemini"):
        return rag_final_answer.ask_gemini(prompt)

    module_path = getattr(rag_final_answer, "__file__", "unknown")
    raise AttributeError(
        "rag_final_answer.ask_rag is missing. "
        f"Loaded module: {module_path}. "
        "Restart the app to reload updated code."
    )

# --- AUTH ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.role = None
if "rate_limit_timestamps" not in st.session_state:
    st.session_state.rate_limit_timestamps = []


def logout():
    for key in ["authenticated", "user_id", "username", "role", "session_id", "messages", "rate_limit_timestamps", "page"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def show_login():
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    render_page_header("Secure Access", "Sign in to the semantic search workspace.", kicker="Authentication")

    if db.get_user_count() == 0:
        open_panel("Create initial admin")
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
        close_panel()
    else:
        open_panel("Account login")
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
                st.session_state.page = "Admin Home" if user["role"] == "admin" else "Chat"
                st.session_state.rate_limit_timestamps = []
                for key in ["session_id", "messages"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
            else:
                st.error("Invalid username or password.")
        close_panel()
    st.markdown("</div>", unsafe_allow_html=True)


if not st.session_state.authenticated:
    show_login()
    st.stop()

# --- SESSION MANAGEMENT ---
def ensure_active_session():
    user_id = st.session_state.user_id
    sessions = db.get_sessions(user_id)
    current_id = st.session_state.get("session_id")
    if current_id is None or not db.session_belongs_to_user(current_id, user_id):
        if sessions:
            st.session_state.session_id = sessions[0][0]
            st.session_state.messages = normalize_loaded_messages(
                db.get_messages(st.session_state.session_id, user_id)
            )
        else:
            st.session_state.session_id = db.create_session(title="New Chat", user_id=user_id)
            st.session_state.messages = []
    elif "messages" not in st.session_state:
        st.session_state.messages = normalize_loaded_messages(db.get_messages(current_id, user_id))


ensure_active_session()


def load_chat(session_id):
    st.session_state.session_id = session_id
    st.session_state.messages = normalize_loaded_messages(db.get_messages(session_id, st.session_state.user_id))


def new_chat():
    new_id = db.create_session(title="New Chat", user_id=st.session_state.user_id)
    st.session_state.session_id = new_id
    st.session_state.messages = []


def truncate_title(title, max_len=28):
    if len(title) > max_len:
        return title[:max_len - 2] + ".."
    return title


def get_admin_pages():
    return list(ADMIN_PAGES)


def ensure_admin_page():
    admin_pages = get_admin_pages()
    if "page" not in st.session_state or st.session_state.page not in admin_pages:
        st.session_state.page = admin_pages[0]
    return admin_pages


def set_page(page_name):
    admin_pages = get_admin_pages()
    st.session_state.page = page_name if page_name in admin_pages else admin_pages[0]


def delete_current_chat():
    if st.session_state.role != "admin":
        st.warning("Only admins can delete chats.")
        return
    current_id = st.session_state.session_id
    # Ensure delete_session exists in your DB script, otherwise handle error
    if hasattr(db, "delete_session"):
        db.delete_session(current_id, st.session_state.user_id)
        remaining = db.get_sessions(st.session_state.user_id)
        if remaining:
            st.session_state.session_id = remaining[0][0]
            st.session_state.messages = normalize_loaded_messages(
                db.get_messages(st.session_state.session_id, st.session_state.user_id)
            )
        else:
            new_chat()
    else:
        st.error("delete_session function missing in chat_storage.py")


def _mime_matches(expected, actual):
    if expected == actual:
        return True
    if not expected or not actual:
        return False
    expected_main = expected.split("/")[0]
    actual_main = actual.split("/")[0]
    if expected_main == actual_main and expected_main == "text":
        return True

    compatible = {
        "text/csv": {"text/plain", "text/csv"},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/zip",
        },
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/zip",
        },
    }
    return actual in compatible.get(expected, set())


def validate_upload(filename, file_bytes):
    expected_mime, _ = mimetypes.guess_type(filename)
    if not expected_mime:
        return False, "Unknown file extension."
    try:
        try:
            import magic as _magic
        except ImportError:
            return False, "python-magic not available. Install python-magic-bin on Windows."
        actual_mime = _magic.from_buffer(file_bytes, mime=True)
    except Exception as exc:
        return False, f"File type detection failed: {exc}"
    if not _mime_matches(expected_mime, actual_mime):
        return False, f"Type mismatch: expected {expected_mime}, detected {actual_mime}."
    return True, actual_mime


def format_timestamp(epoch_seconds):
    if not epoch_seconds:
        return "Never"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch_seconds))
    except Exception:
        return "Unknown"


def open_in_explorer(path):
    if not path:
        return
    target = os.path.abspath(path)
    try:
        if sys.platform.startswith("win"):
            if os.path.isdir(target):
                subprocess.Popen(["explorer", target])
            else:
                subprocess.Popen(["explorer", "/select,", target])
        elif sys.platform == "darwin":
            if os.path.isdir(target):
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["open", "-R", target])
        else:
            folder = target if os.path.isdir(target) else os.path.dirname(target)
            subprocess.Popen(["xdg-open", folder])
    except Exception as exc:
        st.error(f"Failed to open folder: {exc}")


def open_native_file(path):
    if not path:
        return
    target = os.path.abspath(path)
    if not os.path.exists(target):
        st.error("File not found.")
        return
    try:
        if sys.platform.startswith("win"):
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception as exc:
        st.error(f"Failed to open file: {exc}")


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
    try:
        settings = settings_manager.load_settings()
        crawl_folders = settings_manager.get_effective_crawler_folders(
            settings,
            RAW_DATA_DIR,
            base_dir=BASE_DIR
        )
        for folder in crawl_folders:
            candidates.append(os.path.join(folder, source_name))
    except Exception:
        pass

    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.exists(normalized):
            return os.path.abspath(normalized)

    matches = processed_storage.get_paths_by_name(source_name)
    existing = [path for path in matches if os.path.exists(path)]
    if existing:
        existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return os.path.abspath(existing[0])

    return None


def resolve_source_entries(sources):
    entries = []
    seen = set()
    for source in sources or []:
        source_text = str(source).strip()
        if not source_text:
            continue

        resolved_path = resolve_source_path(source_text)
        label = os.path.basename(resolved_path or source_text) or source_text

        file_path = None
        if resolved_path and os.path.isfile(resolved_path):
            file_path = resolved_path

        if resolved_path and os.path.isdir(resolved_path):
            folder_path = resolved_path
        elif resolved_path:
            folder_path = os.path.dirname(resolved_path)
        else:
            folder_path = RAW_DATA_DIR

        dedupe_key = resolved_path or folder_path or source_text
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        entries.append({
            "label": label,
            "file_path": file_path,
            "folder_path": folder_path
        })
    return entries


def render_sources(sources, context_key=""):
    """Render source folder links and native open actions."""
    entries = resolve_source_entries(sources)
    if not entries:
        return

    st.caption("Sources")
    for idx, entry in enumerate(entries):
        folder_path = entry["folder_path"]
        folder_uri = Path(folder_path).resolve().as_uri()
        st.markdown('<div class="source-card">', unsafe_allow_html=True)
        st.markdown('<div class="source-title">Source Location</div>', unsafe_allow_html=True)
        st.markdown(f"Folder: [{folder_path}]({folder_uri})")

        cols = st.columns([0.45, 0.25, 0.3], gap="small")
        cols[0].markdown(f'<div class="source-file">File: {entry["label"]}</div>', unsafe_allow_html=True)

        file_key = f"open_file_{context_key}_{idx}"
        folder_key = f"open_folder_{context_key}_{idx}"
        cols[1].button(
            "Open file",
            key=file_key,
            on_click=open_native_file,
            args=(entry["file_path"],),
            disabled=not entry["file_path"]
        )
        cols[2].button(
            "Open folder",
            key=folder_key,
            on_click=open_in_explorer,
            args=(entry["file_path"] or entry["folder_path"],)
        )
        st.markdown("</div>", unsafe_allow_html=True)

# --- PAGES ---

def render_chat_page():
    render_app_shell("Chat")
    open_panel(tight=True)
    header = st.columns([0.8, 0.2], gap="small")

    with header[1]:
        if st.session_state.role == "admin":
            if st.button("Delete this chat", help="Delete this chat"):
                delete_current_chat()
                st.rerun()
        else:
            st.button("Delete this chat", help="Admins only", disabled=True)

    # Display Messages
    for idx, message in enumerate(st.session_state.messages):
        role = message.get("role", "assistant")
        timestamp = format_chat_clock(message.get("timestamp"))
        model_label = message.get("model_label") or get_active_model_label()
        with st.chat_message(role):
            render_chat_meta(role, timestamp, model_label=model_label)
            st.markdown(message.get("content", ""))
            if message.get("sources"):
                render_sources(message["sources"], context_key=f"{role}_{idx}")

    st.markdown('<div class="chat-input-hint">Ask a focused question for best retrieval quality.</div>', unsafe_allow_html=True)

    # User Input
    if prompt := st.chat_input("Ask a question..."):
        used, remaining, retry_after = get_rate_limit_state()
        if remaining <= 0:
            render_rate_limit(rate_limit_placeholder)
            st.error(f"Rate limit exceeded. Try again in {int(retry_after)} seconds.")
            st.stop()
        st.session_state.rate_limit_timestamps.append(time.time())

        # 1. Show User Message & Save to State/DB
        user_ts = time.time()
        with st.chat_message("user"):
            render_chat_meta("user", format_chat_clock(user_ts))
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt, "sources": [], "timestamp": user_ts})
        db.save_message(st.session_state.session_id, "user", prompt, user_id=st.session_state.user_id)

        # 2. Generate AI Answer
        with st.chat_message("assistant"):
            st.markdown('<div class="chat-thinking">Thinking…</div>', unsafe_allow_html=True)
            try:
                answer, sources = run_rag_with_status(prompt)
            except Exception as exc:
                st.error(str(exc))
                return

            assistant_ts = time.time()
            model_label = get_active_model_label()
            render_chat_meta("assistant", format_chat_clock(assistant_ts), model_label=model_label)
            st.markdown(answer)
            if sources:
                render_sources(sources, context_key=f"live_{len(st.session_state.messages)}")

            # Save Assistant Response
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "timestamp": assistant_ts,
                    "model_label": model_label,
                }
            )
            db.save_message(st.session_state.session_id, "assistant", answer, sources,
                            user_id=st.session_state.user_id)

        # 3. AUTO-TITLE LOGIC (Run this LAST)
        # If this was the first interaction (User + AI = 2 messages), update the title
        if len(st.session_state.messages) == 2:
            new_title = (prompt[:30] + '..') if len(prompt) > 30 else prompt
            db.update_session_title(st.session_state.session_id, new_title, st.session_state.user_id)

            st.rerun()
    close_panel()
    close_app_shell()


def render_admin_home():
    render_app_shell("Admin Home")
    counts = db.get_system_counts()
    st.markdown('<div class="stats-row">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    render_stat_card(col1, "Users", counts["users"], "Registered accounts")
    render_stat_card(col2, "Admins", counts["admins"], "Privileged operators")
    render_stat_card(col3, "Sessions", counts["sessions"], "Tracked conversations")
    render_stat_card(col4, "Messages", counts["messages"], "Stored exchanges")
    st.markdown('</div>', unsafe_allow_html=True)

    render_card(
        "Operations Focus",
        "Use quick actions to jump into user management, chat governance, and knowledge base maintenance.",
        footer="Tip: review knowledge base status before triggering refreshes."
    )

    open_panel("Quick Actions")
    render_admin_panel_note("Use these shortcuts to jump directly into common admin operations.")
    st.markdown('<div class="admin-toolbar">', unsafe_allow_html=True)
    qa1, qa2, qa3 = st.columns(3)
    qa1.button("Manage Users", on_click=set_page, args=("Admin Users",))
    qa2.button("Manage Chats", on_click=set_page, args=("Admin Chats",))
    qa3.button("Manage Knowledge Base", on_click=set_page, args=("Admin Knowledge Base",))
    st.markdown('</div>', unsafe_allow_html=True)
    close_panel()

    open_panel("Knowledge Base Status")
    is_online = os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH)
    render_system_pill(is_online)
    try:
        chunk_count = processed_storage.get_chunk_count()
        st.caption(f"Chunks: {chunk_count}")
    except Exception as exc:
        st.caption(f"Chunk count unavailable: {exc}")
    try:
        raw_files = [f for f in os.listdir(RAW_DATA_DIR) if os.path.isfile(os.path.join(RAW_DATA_DIR, f))]
        st.caption(f"Raw files: {len(raw_files)}")
    except Exception as exc:
        st.caption(f"Raw file count unavailable: {exc}")
    close_panel()
    close_app_shell()


def render_admin_users():
    render_app_shell("Admin Users")
    users = db.list_users()
    open_panel("User Directory")
    render_admin_panel_note("Review account ownership and role distribution before applying security changes.")
    if users:
        table = []
        for user_id, username, role, created_at in users:
            table.append({
                "id": user_id,
                "username": username,
                "role": role,
                "created_at": created_at
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("No users found.")
    close_panel()

    open_panel("Create User")
    render_admin_panel_note("Create operators with minimum required privileges.")
    with st.form("admin_create_user"):
        new_username = st.text_input("Username", key="admin_new_user_username")
        new_password = st.text_input("Password", type="password", key="admin_new_user_password")
        new_role = st.selectbox("Role", ["user", "admin"], index=0, key="admin_new_user_role")
        submitted = st.form_submit_button("Create user")
    if submitted:
        if not new_username or not new_password:
            st.error("Username and password are required.")
        else:
            try:
                db.create_user(new_username, new_password, role=new_role)
                st.success("User created.")
            except db.IntegrityError:
                st.error("Username already exists.")
            except ValueError as exc:
                st.error(str(exc))
    close_panel()

    if not users:
        close_app_shell()
        return

    user_map = {f"{u[1]} (id {u[0]}, {u[2]})": u[0] for u in users}

    open_panel("Update Role")
    render_admin_panel_note("Role updates apply immediately to permissions and page access.")
    with st.form("admin_update_role"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_role_user")
        selected_role = st.selectbox("New role", ["user", "admin"], key="admin_role_value")
        submitted = st.form_submit_button("Update role")
    if submitted:
        target_id = user_map.get(selected_label)
        if target_id == st.session_state.user_id and selected_role != "admin":
            st.error("You cannot remove your own admin role.")
        else:
            try:
                db.update_user_role(target_id, selected_role)
                st.success("Role updated.")
            except ValueError as exc:
                st.error(str(exc))
    close_panel()

    open_panel("Reset Password")
    render_admin_panel_note("Password resets invalidate old credentials right away.")
    with st.form("admin_reset_password"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_pw_user")
        new_password = st.text_input("New password", type="password", key="admin_pw_value")
        confirm_password = st.text_input("Confirm password", type="password", key="admin_pw_confirm")
        submitted = st.form_submit_button("Reset password")
    if submitted:
        if not new_password:
            st.error("Password is required.")
        elif new_password != confirm_password:
            st.error("Passwords do not match.")
        else:
            try:
                db.reset_user_password(user_map.get(selected_label), new_password)
                st.success("Password updated.")
            except ValueError as exc:
                st.error(str(exc))
    close_panel()

    open_panel("Delete User")
    render_admin_panel_note("This action permanently removes user data including sessions and messages.")
    with st.form("admin_delete_user"):
        selected_label = st.selectbox("User", list(user_map.keys()), key="admin_delete_user")
        confirm = st.checkbox("I understand this deletes the user and all their chats", key="admin_delete_confirm")
        submitted = st.form_submit_button("Delete user")
    if submitted:
        target_id = user_map.get(selected_label)
        if target_id == st.session_state.user_id:
            st.error("You cannot delete your own account.")
        elif not confirm:
            st.error("Confirmation is required.")
        else:
            db.delete_user(target_id)
            st.success("User deleted.")
    close_panel()
    close_app_shell()


def render_admin_chats():
    render_app_shell("Admin Chats")
    users = db.list_users()
    open_panel("Chat Sessions")
    render_admin_panel_note("Filter, inspect, and remove sessions to keep workspace data clean.")
    filter_options = [("All users", None)]
    filter_options.extend([(f"{u[1]} (id {u[0]})", u[0]) for u in users])
    filter_label = st.selectbox("Filter by user", [opt[0] for opt in filter_options], key="admin_chat_filter")
    selected_user_id = dict(filter_options)[filter_label]

    sessions = db.list_sessions_admin(selected_user_id)
    if sessions:
        table = []
        for session_id, title, timestamp, user_id, username, message_count in sessions:
            table.append({
                "id": session_id,
                "title": title,
                "user": username,
                "user_id": user_id,
                "messages": message_count,
                "timestamp": timestamp
            })
        st.dataframe(table, use_container_width=True, hide_index=True)

        session_map = {
            f"{row[0]} | {row[4]} | {row[1]}": row[0]
            for row in sessions
        }
        with st.form("admin_delete_sessions"):
            selected = st.multiselect("Delete sessions", list(session_map.keys()))
            confirm = st.checkbox("I understand this deletes the selected chats", key="admin_delete_sessions_confirm")
            submitted = st.form_submit_button("Delete selected")
        if submitted:
            if not selected:
                st.error("Select at least one session.")
            elif not confirm:
                st.error("Confirmation is required.")
            else:
                for label in selected:
                    db.delete_session_admin(session_map[label])
                st.success(f"Deleted {len(selected)} session(s).")
    else:
        st.info("No sessions found.")
    close_panel()
    close_app_shell()


def render_admin_knowledge_base():
    render_app_shell("Admin Knowledge Base")

    settings = settings_manager.load_settings()
    rag_settings = settings.get("rag", {})
    engine_options = ["Cloud (Gemini)", "Local (Ollama)"]
    engine_map = {
        "Cloud (Gemini)": "cloud",
        "Local (Ollama)": "local",
    }
    current_engine = (rag_settings.get("engine") or "cloud").lower()
    engine_index = 1 if current_engine == "local" else 0

    open_panel("Reasoning Engine")
    render_admin_panel_note("Switch between cloud and local reasoning engines without leaving the dashboard.")
    selected_engine = st.selectbox("Engine", engine_options, index=engine_index, key="rag_engine_select")
    st.caption(f"Cloud model: {rag_settings.get('cloud_model', 'gemini-2.5-flash')}")
    st.caption(f"Local model: {rag_settings.get('local_model', 'gemma2:2b')}")
    if st.button("Save engine", use_container_width=True, key="save_rag_engine"):
        selected_key = engine_map[selected_engine]
        action_label = "Loading Ollama" if selected_key == "local" else "Stopping Ollama"
        ok, message = False, ""
        with st.status(action_label, expanded=False) as status:
            settings_manager.update_settings({"rag": {"engine": selected_key}})
            settings = settings_manager.load_settings()
            rag_settings = settings.get("rag", {})
            ollama_url = rag_settings.get("ollama_url") or rag_final_answer.DEFAULT_OLLAMA_URL
            if selected_key == "local":
                ok, message = ollama_manager.ensure_ollama_running(ollama_url)
            else:
                ok, message = ollama_manager.stop_ollama_server(ollama_url)
            if ok:
                status.update(label="Engine Updated", state="complete")
            else:
                status.update(label="Engine Update Failed", state="error")
        if ok:
            st.success(message)
        else:
            st.error(message)
    close_panel()

    configured_folders = settings_manager.get_configured_crawler_folders(settings, base_dir=BASE_DIR)
    effective_folders = settings_manager.get_effective_crawler_folders(settings, RAW_DATA_DIR, base_dir=BASE_DIR)

    open_panel("Crawler Folders")
    render_admin_panel_note("Set one or more source folders used by the ingestion pipeline.")
    st.caption("Leave empty to use the default data/raw folder.")
    folders_text = st.text_area(
        "Folders (one per line)",
        value="\n".join(configured_folders),
        height=120
    )
    if st.button("Save folders", use_container_width=True):
        lines = [line.strip() for line in folders_text.splitlines() if line.strip()]
        normalized = settings_manager.clean_crawler_folders(lines, base_dir=BASE_DIR)
        missing = [path for path in normalized if not os.path.exists(path)]
        if missing:
            st.error("These folders do not exist:\n" + "\n".join(missing))
        else:
            settings_manager.update_settings({"crawler": {"folders": normalized}})
            st.success("Crawler folders updated.")
            settings = settings_manager.load_settings()
            configured_folders = settings_manager.get_configured_crawler_folders(settings, base_dir=BASE_DIR)
            effective_folders = settings_manager.get_effective_crawler_folders(settings, RAW_DATA_DIR, base_dir=BASE_DIR)

    if not configured_folders:
        st.info(f"No folders configured. Using default: {RAW_DATA_DIR}")

    if effective_folders:
        st.caption("Active crawler folders:")
        for idx, folder in enumerate(effective_folders):
            cols = st.columns([0.75, 0.25], gap="small")
            cols[0].markdown(f"`{folder}`")
            cols[1].button(
                "Open folder",
                key=f"open_crawler_folder_{idx}",
                on_click=open_in_explorer,
                args=(folder,)
            )
    close_panel()

    open_panel("Upload and Refresh")
    render_admin_panel_note("Upload validated documents, then queue a refresh to index new content.")
    upload_targets = effective_folders or [RAW_DATA_DIR]
    upload_target = st.selectbox("Upload destination", upload_targets, index=0)

    uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True)
    if uploaded_files:
        saved_count = 0
        for f in uploaded_files:
            file_bytes = f.getvalue()
            is_valid, detail = validate_upload(f.name, file_bytes)
            if not is_valid:
                st.error(f"{f.name}: {detail}")
                continue
            os.makedirs(upload_target, exist_ok=True)
            with open(os.path.join(upload_target, f.name), "wb") as w:
                w.write(file_bytes)
            saved_count += 1
        if saved_count:
            st.success(f"Uploaded {saved_count} file(s).")

    if st.button("Force Refresh", use_container_width=True):
        request_id = settings_manager.request_pipeline_refresh(st.session_state.username)
        st.success(f"Refresh requested (id {request_id}).")

    settings = settings_manager.load_settings()
    pipeline_state = settings.get("pipeline", {})
    request_id = int(pipeline_state.get("refresh_request_id") or 0)
    last_id = int(pipeline_state.get("last_refresh_id") or 0)
    if request_id > last_id:
        st.warning("Refresh queued. The pipeline will run shortly.")
    last_status = pipeline_state.get("last_refresh_status")
    last_time = pipeline_state.get("last_refresh_at")
    if last_status:
        st.caption(f"Last refresh: {format_timestamp(last_time)} ({last_status})")
    last_error = pipeline_state.get("last_refresh_error")
    if last_error and last_status == "error":
        st.error(f"Last refresh error: {last_error}")
    close_panel()

    open_panel("Raw Files")
    render_admin_panel_note("Manage files currently available for indexing in selected source folders.")
    folder_for_listing = st.selectbox("Folder", upload_targets, index=0, key="raw_files_folder")
    listing_cols = st.columns([0.75, 0.25], gap="small")
    listing_cols[0].markdown(f"`{folder_for_listing}`")
    listing_cols[1].button(
        "Open folder",
        key="open_raw_folder",
        on_click=open_in_explorer,
        args=(folder_for_listing,)
    )
    try:
        raw_files = sorted([f for f in os.listdir(folder_for_listing)
                            if os.path.isfile(os.path.join(folder_for_listing, f))])
    except Exception as exc:
        st.error(str(exc))
        raw_files = []

    if raw_files:
        st.dataframe([{"file": f} for f in raw_files], use_container_width=True, hide_index=True)
        with st.form("admin_delete_raw_files"):
            selected = st.multiselect("Delete files", raw_files)
            confirm = st.checkbox("I understand this deletes files from disk", key="admin_delete_files_confirm")
            submitted = st.form_submit_button("Delete selected files")
        if submitted:
            if not selected:
                st.error("Select at least one file.")
            elif not confirm:
                st.error("Confirmation is required.")
            else:
                deleted = 0
                for filename in selected:
                    path = os.path.join(folder_for_listing, filename)
                    try:
                        os.remove(path)
                        deleted += 1
                    except Exception as exc:
                        st.error(f"Failed to delete {filename}: {exc}")
                if deleted:
                    st.success(f"Deleted {deleted} file(s).")
    else:
        st.info("No raw files found.")
    close_panel()
    close_app_shell()


def render_admin_usage():
    render_app_shell("Admin Usage")
    rows = db.get_usage_by_user()
    total_sessions = sum(row[3] for row in rows)
    total_messages = sum(row[4] for row in rows)
    st.markdown('<div class="stats-row">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    render_stat_card(col1, "Total Sessions", total_sessions, "Across all users")
    render_stat_card(col2, "Total Messages", total_messages, "Conversation volume")
    st.markdown('</div>', unsafe_allow_html=True)

    open_panel("Usage by User")
    render_admin_panel_note("Track engagement and activity by user to detect trends and anomalies.")
    if rows:
        table = []
        for user_id, username, role, sessions, messages, last_session in rows:
            table.append({
                "id": user_id,
                "username": username,
                "role": role,
                "sessions": sessions,
                "messages": messages,
                "last_session": last_session
            })
        st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.info("No usage data available.")
    close_panel()
    close_app_shell()


# --- SIDEBAR ---
with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-title">Semantic Search Assistant</div>
            <div class="sidebar-subtitle">Signed in as {st.session_state.username} ({st.session_state.role})</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Logout", use_container_width=True):
        logout()

    rate_limit_placeholder = st.empty()

    if st.session_state.role == "admin":
        render_admin_sidebar_nav()
    else:
        st.session_state.page = "Chat"

    if st.session_state.page == "Chat":
        render_sidebar_section("Chat History")

        if st.button("New Chat", use_container_width=True):
            new_chat()
            st.rerun()

        render_separator()

        sessions = db.get_sessions(st.session_state.user_id)
        for s_id, s_title, s_time in sessions:
            if s_title == "New Chat" and hasattr(db, "get_session_message_count") and db.get_session_message_count(
                    s_id, st.session_state.user_id) == 0:
                if s_id != st.session_state.session_id:
                    continue

            is_current = (s_id == st.session_state.session_id)

            if st.button(truncate_title(s_title), key=f"session_{s_id}", disabled=is_current, use_container_width=True):
                load_chat(s_id)
                st.rerun()

        render_separator()

    render_system_pill(os.path.exists(PROCESSED_PATH) and os.path.exists(PROCESSED_DB_PATH))


# --- MAIN CONTENT ---
if st.session_state.page == "Chat":
    render_chat_page()
elif st.session_state.page == "Admin Home":
    render_admin_home()
elif st.session_state.page == "Admin Users":
    render_admin_users()
elif st.session_state.page == "Admin Chats":
    render_admin_chats()
elif st.session_state.page == "Admin Knowledge Base":
    render_admin_knowledge_base()
elif st.session_state.page == "Admin Usage":
    render_admin_usage()

render_rate_limit(rate_limit_placeholder)
