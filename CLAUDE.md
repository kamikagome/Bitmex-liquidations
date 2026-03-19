# BitMEX Liquidation Data — Project Context

## BitMEX API Reference

### REST API
- **Base URL**: `https://www.bitmex.com`
- **Docs**: https://www.bitmex.com/app/restAPI
- **Rate Limits**:
  - Authenticated: 120 req/min
  - Unauthenticated: 30 req/min
  - Order/position endpoints: 10 req/sec (second layer)
- **Headers**: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`

### Liquidation Endpoint
- **Endpoint**: `GET /api/v1/liquidation`
- **Response Fields**:
  | Field | Type | Description |
  |-------|------|-------------|
  | `orderID` | string | Unique liquidation order ID |
  | `symbol` | string | Trading pair (e.g., `XBTUSD`) |
  | `side` | string | `Buy` or `Sell` |
  | `price` | number | Liquidation price |
  | `leavesQty` | number | Remaining unfilled quantity |
- **Example**:
  ```json
  { "orderID": "00000000-0063-1000-0000-000000044b5f", "symbol": "XBTUSD", "side": "Sell", "price": 69237, "leavesQty": 500 }
  ```

### WebSocket API
- **URL**: `wss://ws.bitmex.com/realtime`
- **Testnet**: `wss://ws.testnet.bitmex.com/realtime`
- **Python connector**: `pip install bitmex-ws` (repo: [official-ws/python](https://github.com/BitMEX/api-connectors/tree/master/official-ws/python))
- Orders/cancellations are NOT supported over WS — use HTTP for those
- Subscribe to `liquidation` topic for real-time liquidation stream

---

## GitHub Portfolio Ideas for BitMEX Liquidation Data

### 1. Real-Time Liquidation Dashboard (Web App)
**What it is**: A live web dashboard that streams liquidation events via WebSocket and visualizes them — ticker tape for big liq events, cumulative volume chart, per-symbol breakdown.

**Why it gets you hired**: Demonstrates WebSocket handling, time-series charting (D3.js or Recharts), React frontend, and understanding of derivatives market mechanics. Highly visual — impressive in a portfolio.

**Stack**: Python/Node WS backend → Redis → React + D3.js frontend
**Key signals to show**: Liq size, symbol, side, price — highlight "whale" liquidations over a threshold.

---

### 2. Liquidation Cascade Detector (Signal Engine)
**What it is**: A Python service that monitors real-time liquidation flow and detects cascade conditions — when liq events cluster in rapid succession near key price levels, it emits a signal.

**Why it gets you hired**: Shows quant thinking, event-driven architecture, and risk management intuition. Directly relevant to market-making and risk teams at crypto firms.

**Stack**: Python asyncio + BitMEX WS → signal logic → Telegram/Discord alert bot
**Key features**: Rolling liq volume window, cascade score, configurable thresholds.

---

### 3. Historical Liquidation Heatmap (Data Analysis)
**What it is**: Pulls historical liquidation data via REST, builds a price-level liquidation heatmap (like Coinglass), and shows where the densest liquidation clusters occurred relative to price action.

**Why it gets you hired**: Showcases data engineering (pagination, storage), pandas/numpy analysis, and Matplotlib/Plotly visualization. Demonstrates you understand open interest and leverage mechanics.

**Stack**: Python REST poller → PostgreSQL/SQLite → Jupyter notebook + Plotly
**Key features**: Time-bucketed liq heatmap, correlation with BTC price, export to PNG/HTML.

---

### 4. Liquidation-Driven Backtest Strategy
**What it is**: A backtesting framework where liquidation spikes serve as trading signals — the hypothesis being that large liq events cause short-term mean reversion or momentum depending on direction.

**Why it gets you hired**: Combines data engineering with systematic trading knowledge. Proves you can turn raw market data into testable hypotheses. Highly relevant for quant dev/researcher roles.

**Stack**: Python + `backtrader` or `vectorbt` + BitMEX historical data
**Key features**: Long/short signals on liq spike detection, Sharpe ratio, drawdown stats, parameter sweep.

---

### 5. Liquidation Aggregator + Multi-Exchange Comparison (Data Pipeline)
**What it is**: An ETL pipeline that ingests liquidation data from BitMEX, Binance, and Bybit, normalizes it into a unified schema, and stores it for querying. Includes a simple API to query liq history by symbol/timeframe.

**Why it gets you hired**: Demonstrates backend/data engineering chops — ingestion, normalization, storage, and serving. Multi-exchange scope shows industry breadth beyond one venue.

**Stack**: Python async ingestion → PostgreSQL → FastAPI query layer
**Key features**: Unified liquidation schema, dedup logic, REST query API, basic Grafana dashboard.

---

## Current Build: Real-Time Liquidation Dashboard (Streamlit)

### Architecture
```
BitMEX WS (wss://ws.bitmex.com/realtime)
  → subscribe: {"op": "subscribe", "args": ["liquidation"]}
  → actions: partial (snapshot), insert (new liq), update, delete
      ↓
ws_client.py (daemon thread, websocket-client lib)
  → filters insert/partial → normalizes → queue.put()
  → exponential backoff reconnection (2s → 60s)
      ↓
queue.Queue (thread-safe)
      ↓
app.py (Streamlit, reruns every 1.5s via streamlit-autorefresh)
  → drain queue → st.session_state.liq_events (cap 5000)
  → pandas DataFrame → Plotly charts
```

### Files
- `app.py` — Streamlit dashboard (metrics, live feed, 4 Plotly charts)
- `ws_client.py` — WebSocket client with reconnection logic
- `requirements.txt` — streamlit, streamlit-autorefresh, websocket-client, plotly, pandas

### USD Value Logic
- **Inverse contracts** (XBTUSD, ETHUSD): `leavesQty` IS the USD value (1 contract = 1 USD)
- **Linear contracts** (USDT pairs): `leavesQty * price` = USD notional

### Running
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Key Details
- No API key needed — liquidation topic is public
- WS rate limit: 720 connections/hour
- Unauthenticated REST: 30 req/min
- Colors: Buy (shorts liquidated) = green `#26a69a`, Sell (longs liquidated) = red `#ef5350`
