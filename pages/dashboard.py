import os
from datetime import datetime

import pandas as pd
import streamlit as st

import src.chat_storage as db
import src.processed_storage as processed_storage
import src.settings_manager as settings_manager
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
    st.subheader("Gemini API Usage Dashboard")
    
    # Auto-update logic using a fragment or similar mechanism in newer Streamlit, 
    # but for compatibility, we'll use a timer and st.rerun if needed or just 
    # a simple periodic refresh.
    
    @st.fragment(run_every=30)
    def render_usage_section():
        try:
            latest_usage = db.get_latest_gemini_usage()
            summary = db.get_gemini_usage_summary(days=1)
            available_models = db.get_available_models()
        except Exception as e:
            st.error(f"Database error: {e}")
            latest_usage = None
            summary = None
            available_models = []
        
        container = st.container()
        
        if not latest_usage:
            container.info("Usage data unavailable. Try interacting with the AI to generate usage data.")
            if st.button("Test Gemini API Connection"):
                try:
                    from src.rag_final_answer import generate_with_gemini
                    # Simple test prompt
                    res = generate_with_gemini("Ping", "You are a tester. Reply with Pong.", "gemini-2.5-flash")
                    st.success(f"Gemini API Response: {res}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gemini API Error: {e}")
            return

        # Metrics display
        m_col1, m_col2, m_col3 = container.columns(3)
        
        # RPM usage
        rpm_limit = latest_usage.get('limit_rpm') or 15
        rpm_rem = latest_usage.get('remaining_rpm')

                # Model Selection
        selected_model = container.selectbox(
            "Select Model for Rate Limit Analysis",
            options=available_models if available_models else [latest_usage.get('model_name')],
            index=0
        )
        
        with m_col1:
            st.metric("RPM Limit", rpm_limit)
        
        # Quota usage
        q_consumed_total = summary['total_consumed'] if summary else 0
        q_limit = latest_usage.get('quota_total') or 1000000 # Default fallback
        
        with m_col2:
            st.metric("Total Tokens (Today)", f"{q_consumed_total:,}")
        with m_col3:
            st.metric("Daily Quota", f"{q_limit:,}")

        # Visual progress bars
        st.write("---")
        
        # Token/Quota Usage Progress
        q_usage_pct = (q_consumed_total / q_limit * 100) if q_limit > 0 else 0
        
        # Progress bar color logic
        bar_color = "#28a745" # Green
        if q_usage_pct >= 90:
            bar_color = "#dc3545" # Red
        elif q_usage_pct >= 75:
            bar_color = "#ffc107" # Yellow
            
        st.markdown(f"""
            <div style="margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-weight: bold; color: #555;">Daily Token Usage</span>
                    <span style="font-weight: bold; color: {bar_color};">{q_usage_pct:.1f}%</span>
                </div>
                <div style="width: 100%; background-color: #f0f2f6; border-radius: 10px; height: 12px; overflow: hidden; border: 1px solid #ddd;">
                    <div style="width: {min(q_usage_pct, 100):.1f}%; background: linear-gradient(90deg, {bar_color} 0%, {bar_color}dd 100%); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if q_usage_pct >= 90:
            st.error(f"CRITICAL: Token quota usage is at {q_usage_pct:.1f}%")
        elif q_usage_pct >= 75:
            st.warning(f"Warning: Token quota usage is at {q_usage_pct:.1f}%")

        # Peak Usage Graphs (AI Studio Style)
        st.subheader("Rate Limit Usage ")
        
        zoom_options = {
            "1 Minute (1h window)": ("1min", 1),
            "5 Minutes (4h window)": ("5min", 4),
            "10 Minutes (6h window)": ("10min", 6),
            "30 Minutes (12h window)": ("30min", 12),
            "1 Hour (24h window)": ("1h", 24),
            "6 Hours (7d window)": ("6h", 168) # 7 days
        }
        
        z_col1, z_col2 = st.columns([1, 2])
        with z_col1:
            zoom_label = st.selectbox(
                "Time Zoom Level",
                options=list(zoom_options.keys()),
                index=2 # Default to 10 min
            )
        
        interval_code, lookback_hours = zoom_options[zoom_label]
        st.caption(f"{zoom_label} tracking (Tashkent Time).")
        
        # Get enough history for the lookback
        days_to_fetch = max(1, lookback_hours // 24 + 1)
        history = db.get_gemini_usage_history(days=days_to_fetch, model_name=selected_model)
        
        if history:
            df = pd.DataFrame(history)
            # Database stores in UTC
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            # Convert to Tashkent Time (UTC+5)
            df['timestamp'] = df['timestamp'] + pd.Timedelta(hours=5)
            
            # 1. Calculate per-minute usage first (to find peaks)
            df['minute'] = df['timestamp'].dt.floor('1min')
            minute_usage = df.groupby('minute').agg({
                'timestamp': 'count',
                'input_tokens': 'sum'
            }).rename(columns={'timestamp': 'rpm', 'input_tokens': 'tpm'})
            
            # 2. Find the peak (max) RPM/TPM for each selected window
            minute_usage['window'] = minute_usage.index.floor(interval_code)
            window_peaks = minute_usage.groupby('window').agg({
                'rpm': 'max',
                'tpm': 'max'
            })
            
            # Resample to ensure we show a continuous timeline
            now_tashkent = pd.Timestamp.utcnow() + pd.Timedelta(hours=5)
            now_tashkent = now_tashkent.replace(tzinfo=None)
            
            end_time = now_tashkent.floor(interval_code)
            start_time = end_time - pd.Timedelta(hours=lookback_hours)
            
            all_windows = pd.date_range(start=start_time, end=end_time, freq=interval_code)
            plot_df = window_peaks.reindex(all_windows, fill_value=0)
            
            # Format index based on interval
            if interval_code == "1h" or interval_code == "6h":
                plot_df.index = plot_df.index.strftime('%m-%d %H:00')
            else:
                plot_df.index = plot_df.index.strftime('%H:%M')
            
            # RPD history (7 days)
            daily_rpd_history = db.get_gemini_usage_history(days=7, model_name=selected_model)
            if daily_rpd_history:
                rpd_df = pd.DataFrame(daily_rpd_history)
                rpd_df['date'] = pd.to_datetime(rpd_df['timestamp']).dt.date
                daily_rpd = rpd_df.groupby('date').size().rename('requests_per_day')
            else:
                daily_rpd = pd.Series(dtype=int)

            g_col1, g_col2, g_col3 = st.columns(3)
            
            with g_col1:
                st.caption("Peak Requests Per Minute (RPM)")
                st.area_chart(plot_df['rpm'], height=200, color="#4285F4")
            
            with g_col2:
                st.caption("Peak Input Tokens Per Minute (TPM)")
                st.area_chart(plot_df['tpm'], height=200, color="#FBBC05")
                
            with g_col3:
                st.caption("Requests Per Day (RPD)")
                if not daily_rpd.empty:
                    st.bar_chart(daily_rpd, height=200, color="#34A853")
                else:
                    st.info("No daily data.")
        else:
            st.info("Insufficient historical data for peak usage graphs.")

        # RPM Progress (If available)
        if rpm_rem is not None:
            rpm_usage_pct = (rpm_limit - rpm_rem) / rpm_limit * 100
            
            rpm_bar_color = "#28a745"
            if rpm_usage_pct >= 90:
                rpm_bar_color = "#dc3545"
            elif rpm_usage_pct >= 75:
                rpm_bar_color = "#ffc107"
                
            st.markdown(f"""
                <div style="margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-weight: bold; color: #555;">RPM Usage</span>
                        <span style="font-weight: bold; color: {rpm_bar_color};">{rpm_usage_pct:.1f}%</span>
                    </div>
                    <div style="width: 100%; background-color: #f0f2f6; border-radius: 10px; height: 12px; overflow: hidden; border: 1px solid #ddd;">
                        <div style="width: {min(rpm_usage_pct, 100):.1f}%; background: linear-gradient(90deg, {rpm_bar_color} 0%, {rpm_bar_color}dd 100%); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Detailed RPM headers unavailable. Tracking token usage instead.")

        # Export buttons
        exp_col1, exp_col2 = st.columns([1, 4])
        with exp_col1:
            history = db.get_gemini_usage_history(days=30)
            if history:
                df_history = pd.DataFrame(history)
                csv = df_history.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export CSV",
                    data=csv,
                    file_name=f"gemini_usage_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="gemini_csv_download"
                )
                
                json_data = df_history.to_json(orient='records')
                st.download_button(
                    label="Export JSON",
                    data=json_data,
                    file_name=f"gemini_usage_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    key="gemini_json_download"
                )

    render_usage_section()
    
    # Auto-refresh every 30 seconds
    # Note: st.rerun() would reload the whole page. 
    # In newer streamlit we could use st.fragment, but for now let's use a simple sleep/rerun or rely on user interaction.
    # The requirement says "updates automatically every 30 seconds without reloading the page".
    # This usually requires st.empty() + a loop or st.fragment.
    # Since I cannot easily add a background thread in Streamlit without issues, 
    # I'll use the experimental fragment if available or a simple timer.
    
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
    
    settings = settings_manager.load_settings()
    configured_folders = settings_manager.get_configured_crawler_folders(settings)
    
    # 1. Configured Source Folders (Admin Defined)
    st.markdown("### Configured Source Folders")
    if configured_folders:
        for folder in configured_folders:
            with st.expander(f"📁 {folder}", expanded=True):
                try:
                    items = sorted(os.listdir(folder))
                    if items:
                        item_data = []
                        for item in items:
                            full_path = os.path.join(folder, item)
                            is_dir = os.path.isdir(full_path)
                            item_data.append({
                                "Name": item,
                                "Type": "Folder" if is_dir else "File",
                                "Size (KB)": round(os.path.getsize(full_path) / 1024, 2) if not is_dir else "-"
                            })
                        st.dataframe(item_data, use_container_width=True, hide_index=True)
                    else:
                        st.info("Folder is empty.")
                except Exception as e:
                    st.error(f"Error reading folder: {e}")
    else:
        st.info("No custom folders configured by admin.")

    st.write("---")

    # 2. Raw Source Folders (Default data/raw)
    st.markdown("### Raw Source Folders")
    try:
        items = sorted(os.listdir(RAW_DATA_DIR))
        with st.expander(f"📁 {RAW_DATA_DIR}", expanded=True):
            if items:
                item_data = []
                for item in items:
                    full_path = os.path.join(RAW_DATA_DIR, item)
                    is_dir = os.path.isdir(full_path)
                    item_data.append({
                        "Name": item,
                        "Type": "Folder" if is_dir else "File",
                        "Size (KB)": round(os.path.getsize(full_path) / 1024, 2) if not is_dir else "-"
                    })
                st.dataframe(item_data, use_container_width=True, hide_index=True)
            else:
                st.info("No files or folders found in raw directory.")
    except Exception as exc:
        st.warning(f"Could not access raw directory: {exc}")
        
    st.markdown("</div>", unsafe_allow_html=True)
