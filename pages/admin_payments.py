from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import src.chat_storage as db
import src.utils.payments as payments
from src.ui_core import (
    apply_theme,
    configure_page,
    init_auth_state,
    render_sidebar,
    require_admin,
)

# --- PAGE CONFIG ---
configure_page("Payments & Subscriptions")
apply_theme()
init_auth_state()

# --- AUTH CHECK ---
if not st.session_state.get("authenticated"):
    st.switch_page("app.py")

require_admin()
render_sidebar(active="payments")

# Account for Tashkent time (UTC+5)
tashkent_now = datetime.utcnow() + timedelta(hours=5)

# Log for debugging (will only show in console)
print(f"Rendering Payments page for user: {st.session_state.get('username')} at {tashkent_now}")

st.title("Payments & Subscriptions")

# --- A. FINANCIAL OVERVIEW ---
with st.spinner("Loading financial data..."):
    try:
        kpis = db.get_payment_kpis()
    except Exception as e:
        st.error(f"Error loading KPIs: {e}")
        kpis = {"revenue_mtd": 0, "conversion_rate": 0, "active_subscriptions": 0}

col1, col2, col3 = st.columns(3)
with col1:
    with st.container(border=True):
        st.metric("Total Revenue (MTD)", f"{kpis['revenue_mtd']:,} UZS")
with col2:
    with st.container(border=True):
        st.metric("Conversion Rate", f"{kpis['conversion_rate']:.1f}%")
with col3:
    with st.container(border=True):
        st.metric("Active Subscriptions", kpis['active_subscriptions'])

st.write("")

# --- VISUAL ANALYTICS ---
st.subheader("Revenue Trends")

period_options = {
    "Last Day (Hourly)": "1d",
    "Last Week (Daily)": "7d",
    "Last 30 Days (Daily)": "30d",
    "Last Year (Monthly)": "1y"
}

period_labels = list(period_options.keys())
period_values = list(period_options.values())

selected_period_label = st.selectbox("Select Time Period", options=period_labels, index=0)
selected_period = period_options[selected_period_label]

period_label_map = {
    "1d": "Last 24 Hours",
    "7d": "Last 7 Days",
    "30d": "Last 30 Days",
    "1y": "Last 12 Months"
}

with st.spinner(f"Calculating trends - {period_label_map[selected_period]}..."):
    try:
        revenue_data = db.get_revenue_trends(selected_period)
    except Exception as e:
        st.error(f"Error loading revenue trends: {e}")
        revenue_data = []

if revenue_data:
    rev_df = pd.DataFrame(revenue_data)
    
    if selected_period == "1d":
        rev_df['period'] = pd.to_datetime(rev_df['period'], format='%Y-%m-%d %H:00')
        rev_df = rev_df.set_index('period')
        all_periods = pd.date_range(start=rev_df.index.min(), end=tashkent_now, freq='h')
        rev_df = rev_df.reindex(all_periods, fill_value=0)
        chart_label = "Hourly Revenue"
    elif selected_period == "1y":
        rev_df['period'] = pd.to_datetime(rev_df['period'], format='%Y-%m')
        rev_df = rev_df.set_index('period')
        all_periods = pd.date_range(start=rev_df.index.min(), end=tashkent_now, freq='MS')
        rev_df = rev_df.reindex(all_periods, fill_value=0)
        chart_label = "Monthly Revenue"
    else:
        rev_df['period'] = pd.to_datetime(rev_df['period'])
        rev_df = rev_df.set_index('period')
        end_date = tashkent_now.date()
        if selected_period == "7d":
            all_periods = pd.date_range(start=rev_df.index.min(), end=end_date, freq='D')
        else:
            all_periods = pd.date_range(start=rev_df.index.min(), end=end_date, freq='D')
        rev_df = rev_df.reindex(all_periods, fill_value=0)
        chart_label = "Daily Revenue"
    
    st.area_chart(rev_df['total'], color="#0077b6", height=250, use_container_width=True)
else:
    st.info(f"No successful transactions recorded in the {period_label_map[selected_period].lower()}.")

st.write("")

# --- B. SANDBOX: GENERATE TEST PAYMENT ---
with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("Sandbox: Generate Test Payment")
    
    users = db.list_users()
    user_options = {f"{u[1]} (ID: {u[0]})": u[0] for u in users}
    
    sb_col1, sb_col2, sb_col3 = st.columns(3)
    with sb_col1:
        selected_user_label = st.selectbox("Select User", options=list(user_options.keys()))
        user_id = user_options[selected_user_label]
    with sb_col2:
        amount = st.number_input("Amount (UZS)", min_value=1000, step=1000, value=15000)
    with sb_col3:
        provider = st.selectbox("Payment Provider", options=["Click", "Payme"])
    
    if st.button("Generate Payment Link", use_container_width=True):
        order_id = db.create_order(user_id, amount, provider)
        
        if provider == "Click":
            link = payments.generate_click_link(amount, order_id)
        else:
            link = payments.generate_payme_link(amount, order_id)
            
        st.success(f"Order #{order_id} created successfully!")
        st.link_button(f"Pay with {provider}", link, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.write("")

# --- C. TRANSACTION LEDGER ---
with st.container():
    st.markdown('<div class="stCard">', unsafe_allow_html=True)
    st.subheader("Transaction Ledger")
    
    with st.spinner("Fetching transactions..."):
        try:
            transactions = db.get_transactions()
        except Exception as e:
            st.error(f"Error loading transactions: {e}")
            transactions = []

    if transactions:
        df = pd.DataFrame(transactions)
        
        # Search filter
        search = st.text_input("Search transactions...", placeholder="Username, Provider, or Status")
        if search:
            df = df[
                df['username'].str.contains(search, case=False) | 
                df['provider'].str.contains(search, case=False) | 
                df['status'].str.contains(search, case=False)
            ]
        
        # Display DataFrame with formatting
        def color_status(val):
            if val == 'success': return 'color: #28a745; font-weight: bold;'
            if val == 'failed': return 'color: #dc3545; font-weight: bold;'
            return 'color: #ffc107;'

        st.dataframe(
            df.style.map(color_status, subset=['status']),
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "Order ID",
                "username": "User",
                "amount": st.column_config.NumberColumn("Amount", format="%d UZS"),
                "created_at": "Date",
                "external_id": "Ref ID"
            }
        )
        
        # Manual Confirmation (Simulation)
        st.write("### Simulation: Manual Confirmation")
        pending_txs = [t for t in transactions if t['status'] == 'pending']
        if pending_txs:
            tx_options = {f"Order #{t['id']} - {t['username']} ({t['amount']} UZS)": t['id'] for t in pending_txs}
            confirm_tx_label = st.selectbox("Select Pending Order to Confirm", options=list(tx_options.keys()))
            confirm_tx_id = tx_options[confirm_tx_label]
            
            if st.button("Confirm Payment Successfully", type="primary"):
                db.update_transaction_status(confirm_tx_id, 'success', external_id=f"SIM-{datetime.now().strftime('%H%M%S')}")
                st.success(f"Transaction #{confirm_tx_id} confirmed!")
                st.rerun()
        else:
            st.info("No pending transactions to confirm.")
            
    else:
        st.info("No transactions found.")
    st.markdown("</div>", unsafe_allow_html=True)
