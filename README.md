# BitMEX Liquidation Dashboard

A real-time liquidation monitoring dashboard built with Streamlit and the BitMEX public WebSocket API.

> **Learning project** — built to explore the BitMEX API and practice building real-time data pipelines with [Claude Code](https://claude.ai/code).

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.30+-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Streams live liquidation events from BitMEX via WebSocket and visualizes them in a Streamlit dashboard that auto-refreshes every 1.5 seconds.

**Dashboard panels:**

| Panel | Description |
|-------|-------------|
| Header metrics | Total liquidations, total USD value, Buy:Sell ratio, session uptime |
| Live feed | Scrolling table of the 100 most recent events |
| Price histogram | Where liquidations cluster by price level (per symbol) |
| Buy vs Sell volume | Cumulative USD liquidated by side |
| Timeline | Liquidation volume over time in 1-minute buckets |
| Top symbols | Which markets are generating the most liquidation activity |

**Sidebar** shows live WebSocket connection status and event buffer count.

---

## How it works

```
BitMEX WebSocket  →  ws_client.py  →  queue.Queue  →  app.py (Streamlit)
(public, no auth)    daemon thread     thread-safe     reruns every 1.5s
```

- `ws_client.py` subscribes to the `liquidation` topic and puts normalized events into a thread-safe queue. Reconnects automatically with exponential backoff (2s → 60s).
- `app.py` drains the queue into `st.session_state` on every rerun and renders all charts from the accumulated in-memory buffer (capped at 5,000 events).
- No API key or authentication required — liquidation data is public.

---

## Quickstart

```bash
git clone <repo-url>
cd bitmex_liq

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

> During quiet markets, liquidation events may take a few minutes to appear. The dashboard shows a waiting state until the first event arrives.

### Test the WebSocket connection standalone

```bash
python ws_client.py
```

Prints liquidation events to the console as they arrive. Press `Ctrl+C` to stop.

---

## Project structure

```
bitmex_liq/
├── app.py            # Streamlit dashboard
├── ws_client.py      # BitMEX WebSocket client + reconnection logic
├── requirements.txt  # Python dependencies
└── README.md
```

---

## BitMEX API notes

- **WebSocket URL**: `wss://ws.bitmex.com/realtime`
- **Subscribe message**: `{"op": "subscribe", "args": ["liquidation"]}`
- **Liquidation fields**: `orderID`, `symbol`, `side`, `price`, `leavesQty`
- **Rate limit**: 720 connections/hour (unauthenticated)
- **USD value**: Inverse contracts (XBTUSD, ETHUSD) — `leavesQty` is the USD value. Linear contracts (USDT pairs) — `leavesQty × price`.

Full API docs: https://www.bitmex.com/app/restAPI

---

## Built with

- [Streamlit](https://streamlit.io/) — dashboard UI and auto-refresh
- [websocket-client](https://github.com/websocket-client/websocket-client) — WebSocket connection
- [Plotly Express](https://plotly.com/python/plotly-express/) — interactive charts
- [pandas](https://pandas.pydata.org/) — data manipulation
- [Claude Code](https://claude.ai/code) — AI-assisted development

---

## License

MIT
