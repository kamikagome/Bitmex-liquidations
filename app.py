"""BitMEX Real-Time Liquidation Dashboard."""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from queue import Queue
from datetime import datetime, timezone
import pandas as pd
import plotly.express as px

from ws_client import start_ws_thread

# --- Page config ---
st.set_page_config(
    page_title="BitMEX Liquidations",
    page_icon="💀",
    layout="wide",
)

# --- Auto-refresh every 1.5s ---
st_autorefresh(interval=1500, key="data_refresh")

# --- Session state init (once per tab) ---
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.liq_events = []
    st.session_state.queue = Queue()
    st.session_state.start_time = datetime.now(timezone.utc)
    st.session_state.ws_thread, st.session_state.ws_state = start_ws_thread(
        st.session_state.queue
    )


# --- Drain queue ---
def drain_queue():
    q = st.session_state.queue
    new_events = []
    while not q.empty():
        try:
            new_events.append(q.get_nowait())
        except Exception:
            break
    if new_events:
        st.session_state.liq_events.extend(new_events)
        if len(st.session_state.liq_events) > 5000:
            st.session_state.liq_events = st.session_state.liq_events[-5000:]


drain_queue()


# --- USD value calculation ---
def calc_usd_value(row):
    """Inverse contracts (XBTUSD): leavesQty IS USD. Linear (USDT): qty * price."""
    if row["symbol"].endswith("USD") and "USDT" not in row["symbol"]:
        return row["leavesQty"]
    return row["leavesQty"] * row["price"]


# --- Build DataFrame ---
df = pd.DataFrame(st.session_state.liq_events)
if not df.empty:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["usd_value"] = df.apply(calc_usd_value, axis=1)

# --- Color map ---
COLORS = {"Buy": "#26a69a", "Sell": "#ef5350"}

# --- Sidebar ---
with st.sidebar:
    st.title("Status")
    if st.session_state.ws_state.connected:
        st.success("WebSocket: Connected")
    else:
        st.warning("WebSocket: Connecting...")

    uptime = datetime.now(timezone.utc) - st.session_state.start_time
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    st.metric("Session Uptime", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    st.metric("Events Buffered", len(st.session_state.liq_events))

    st.divider()
    st.caption("Data: BitMEX WebSocket (public, no auth)")
    st.caption("Refresh: 1.5s")

# --- Header ---
st.title("BitMEX Real-Time Liquidation Dashboard")

# --- Metrics row ---
col1, col2, col3, col4 = st.columns(4)

if df.empty:
    col1.metric("Total Liquidations", 0)
    col2.metric("Total USD Value", "$0")
    col3.metric("Buy : Sell", "N/A")
    col4.metric("Symbols Active", 0)
else:
    col1.metric("Total Liquidations", f"{len(df):,}")

    total_usd = df["usd_value"].sum()
    if total_usd >= 1_000_000:
        col2.metric("Total USD Value", f"${total_usd / 1_000_000:.2f}M")
    elif total_usd >= 1_000:
        col2.metric("Total USD Value", f"${total_usd / 1_000:.1f}K")
    else:
        col2.metric("Total USD Value", f"${total_usd:,.0f}")

    buy_count = len(df[df["side"] == "Buy"])
    sell_count = len(df[df["side"] == "Sell"])
    if sell_count > 0:
        ratio = buy_count / sell_count
        col3.metric("Buy : Sell", f"{ratio:.2f} : 1")
    else:
        col3.metric("Buy : Sell", f"{buy_count} : 0")

    col4.metric("Symbols Active", df["symbol"].nunique())

# --- Empty state ---
if df.empty:
    st.info(
        "Waiting for liquidation events... "
        "During quiet markets this may take a few minutes."
    )
    st.stop()

# --- Live feed ---
st.subheader("Live Liquidation Feed")
display_df = (
    df.sort_values("timestamp", ascending=False)
    .head(100)[["timestamp", "symbol", "side", "price", "leavesQty", "usd_value"]]
)
st.dataframe(display_df, use_container_width=True, height=300)

# --- Charts row 1 ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Liquidation Clusters by Price")
    symbols = sorted(df["symbol"].unique().tolist())
    selected_symbol = st.selectbox("Symbol", symbols, index=0, key="hist_symbol")
    df_sym = df[df["symbol"] == selected_symbol]
    fig = px.histogram(
        df_sym,
        x="price",
        weights="leavesQty",
        nbins=50,
        color="side",
        color_discrete_map=COLORS,
        labels={"price": "Price", "leavesQty": "Volume"},
    )
    fig.update_layout(barmode="stack", height=370)
    st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    st.subheader("Cumulative Volume by Side")
    side_agg = df.groupby("side")["usd_value"].sum().reset_index()
    fig = px.bar(
        side_agg,
        x="side",
        y="usd_value",
        color="side",
        color_discrete_map=COLORS,
        labels={"usd_value": "USD Value", "side": "Side"},
    )
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

# --- Charts row 2 ---
st.subheader("Liquidation Volume Over Time (1-min buckets)")
df_timeline = df.copy()
df_timeline["minute"] = df_timeline["timestamp"].dt.floor("1min")
timeline = df_timeline.groupby(["minute", "side"])["usd_value"].sum().reset_index()
fig = px.bar(
    timeline,
    x="minute",
    y="usd_value",
    color="side",
    color_discrete_map=COLORS,
    labels={"minute": "Time", "usd_value": "USD Value"},
    barmode="stack",
)
fig.update_layout(height=350)
st.plotly_chart(fig, use_container_width=True)

# --- Charts row 3 ---
st.subheader("Top Symbols by Liquidation Volume")
symbol_agg = (
    df.groupby("symbol")["usd_value"]
    .sum()
    .reset_index()
    .sort_values("usd_value", ascending=False)
    .head(10)
)
fig = px.bar(
    symbol_agg,
    x="symbol",
    y="usd_value",
    color="usd_value",
    color_continuous_scale="Reds",
    labels={"symbol": "Symbol", "usd_value": "USD Value"},
)
fig.update_layout(height=350)
st.plotly_chart(fig, use_container_width=True)
