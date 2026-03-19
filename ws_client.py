"""BitMEX WebSocket client for streaming liquidation events."""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Optional

import websocket

BITMEX_WS_URL: str = "wss://ws.bitmex.com/realtime"
SUBSCRIBE_MSG: str = json.dumps({"op": "subscribe", "args": ["liquidation"]})
RECONNECT_DELAY_BASE: int = 2
MAX_RECONNECT_DELAY: int = 60

logger = logging.getLogger(__name__)


class WsState:
    """Shared state between the WebSocket callbacks and the Streamlit UI.

    ``connected`` is written from the WS callback thread and read from the UI
    thread.  CPython's GIL makes single bool reads/writes effectively atomic,
    but this is an implementation detail, not a language guarantee.  Add a
    ``threading.Lock`` if stricter correctness is required.

    ``_connect_count`` is incremented in ``_on_open`` and is used by
    ``_run_ws_loop`` to detect whether a connection was established during a
    given ``run_forever()`` call — ``state.connected`` cannot be used for this
    because ``_on_close`` resets it to ``False`` before ``run_forever`` returns.
    """

    def __init__(self) -> None:
        self.connected: bool = False
        self._connect_count: int = 0


def _on_open(_ws: websocket.WebSocketApp, _q: Queue, state: WsState) -> None:
    """Send subscription message and update state on successful connection."""
    logger.info("WebSocket connected, subscribing to liquidation topic")
    state.connected = True
    state._connect_count += 1
    _ws.send(SUBSCRIBE_MSG)


def _on_message(_ws: websocket.WebSocketApp, raw_msg: str, q: Queue) -> None:
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


def _on_error(_ws: websocket.WebSocketApp, error: Exception) -> None:
    """Log WebSocket errors."""
    logger.error("WebSocket error: %s", error)


def _on_close(
    _ws: websocket.WebSocketApp,
    close_status_code: Optional[int],
    close_msg: Optional[str],
    state: WsState,
) -> None:
    """Update connection state on close."""
    logger.info("WebSocket closed: %s %s", close_status_code, close_msg)
    state.connected = False


def _run_ws_loop(q: Queue, state: WsState) -> None:
    """Connect to BitMEX WS with automatic reconnection and exponential backoff."""
    delay = RECONNECT_DELAY_BASE
    while True:
        count_before = state._connect_count
        try:
            ws = websocket.WebSocketApp(
                BITMEX_WS_URL,
                on_open=lambda _ws: _on_open(_ws, q, state),
                on_message=lambda _ws, msg: _on_message(_ws, msg, q),
                on_error=_on_error,
                on_close=lambda _ws, code, msg: _on_close(_ws, code, msg, state),
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception as e:
            logger.error("WebSocket exception: %s", e)

        # Reset backoff only if a connection was actually established.
        # state.connected cannot be used here — _on_close sets it to False
        # before run_forever() returns, so we track via _connect_count instead.
        if state._connect_count > count_before:
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
    q: Queue = Queue()
    print("Connecting to BitMEX WebSocket... (Ctrl+C to stop)")
    thread, _ = start_ws_thread(q)
    try:
        while True:
            try:
                event = q.get(timeout=0.5)
                print(json.dumps(event, indent=2))
            except Empty:
                pass
    except KeyboardInterrupt:
        print("\nStopped.")
