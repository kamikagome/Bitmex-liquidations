"""BitMEX WebSocket client for streaming liquidation events."""

import json
import time
import threading
import logging
from queue import Queue
from datetime import datetime, timezone

import websocket

BITMEX_WS_URL = "wss://ws.bitmex.com/realtime"
SUBSCRIBE_MSG = json.dumps({"op": "subscribe", "args": ["liquidation"]})
RECONNECT_DELAY_BASE = 2
MAX_RECONNECT_DELAY = 60

logger = logging.getLogger(__name__)


class WsState:
    """Shared state between the WebSocket callbacks and the Streamlit UI."""
    def __init__(self):
        self.connected = False


def _on_open(ws, q, state):
    """Send subscription message on connection."""
    logger.info("WebSocket connected, subscribing to liquidation topic")
    state.connected = True
    ws.send(SUBSCRIBE_MSG)


def _on_message(ws, raw_msg, q):
    """Parse liquidation messages and put normalized dicts into the queue."""
    try:
        msg = json.loads(raw_msg)
    except json.JSONDecodeError:
        logger.warning("Failed to parse WebSocket message")
        return

    if msg.get("table") != "liquidation":
        return
    if msg.get("action") not in ("insert", "partial"):
        return

    now = datetime.now(timezone.utc).isoformat()
    for item in msg.get("data", []):
        event = {
            "timestamp": now,
            "orderID": item.get("orderID", ""),
            "symbol": item.get("symbol", ""),
            "side": item.get("side", ""),
            "price": item.get("price", 0),
            "leavesQty": item.get("leavesQty", 0),
        }
        q.put(event)


def _on_error(ws, error):
    logger.error("WebSocket error: %s", error)


def _on_close(ws, close_status_code, close_msg, state):
    logger.info("WebSocket closed: %s %s", close_status_code, close_msg)
    state.connected = False


def _run_ws_loop(q: Queue, state: WsState):
    """Connect to BitMEX WS with automatic reconnection and exponential backoff."""
    delay = RECONNECT_DELAY_BASE
    while True:
        did_connect = False
        try:
            ws = websocket.WebSocketApp(
                BITMEX_WS_URL,
                on_open=lambda ws: _on_open(ws, q, state),
                on_message=lambda ws, msg: _on_message(ws, msg, q),
                on_error=_on_error,
                on_close=lambda ws, code, msg: _on_close(ws, code, msg, state),
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
            did_connect = state.connected or did_connect
        except Exception as e:
            logger.error("WebSocket exception: %s", e)

        # Only reset backoff if we actually established a connection
        if did_connect:
            delay = RECONNECT_DELAY_BASE

        logger.info("Reconnecting in %ds...", delay)
        time.sleep(delay)
        delay = min(delay * 2, MAX_RECONNECT_DELAY)


def start_ws_thread(q: Queue) -> tuple[threading.Thread, WsState]:
    """Spawn a daemon thread that streams liquidation events into the queue.

    Returns (thread, state) where state.connected reflects live WS status.
    """
    state = WsState()
    thread = threading.Thread(target=_run_ws_loop, args=(q, state), daemon=True)
    thread.start()
    return thread, state


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    q = Queue()
    print("Connecting to BitMEX WebSocket... (Ctrl+C to stop)")
    thread = start_ws_thread(q)
    try:
        while True:
            if not q.empty():
                event = q.get()
                print(json.dumps(event, indent=2))
            else:
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
