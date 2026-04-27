from __future__ import annotations

import time
from collections import deque
from typing import Any

from src.constants import logging


class Wserver:
    # socket_opened should be instance variable, not class variable!
    ltp: dict[str, float] = {}
    order_updates: deque = deque(maxlen=100)

    def __init__(self, session: Any, tokens: list[str]) -> None:
        self.api = session
        self.tokens = tokens
        self.socket_opened = False  # Instance variable - FIXED!
        logging.info(f"🔌 Wserver: Creating websocket for tokens: {tokens}")
        
        ret = self.api.broker.start_websocket(
            order_update_callback=self.event_handler_order_update,
            subscribe_callback=self.event_handler_quote_update,
            socket_open_callback=self.open_callback,
        )
        if ret:
            logging.info(f"✅ {ret} ws started")
        else:
            logging.warning(f"⚠️ start_websocket returned: {ret}")

    def open_callback(self) -> None:
        logging.info("🔌 Websocket open callback triggered!")
        self.socket_opened = True
        logging.info(f"🔌 socket_opened set to True")
        self.api.broker.subscribe(self.tokens, feed_type="d")
        logging.info(f"🔌 Subscribed to initial tokens: {self.tokens}")

    def event_handler_order_update(self, message: dict[str, Any]) -> None:
        self.order_updates.append(message)
        logging.debug(f"order_updates count: {len(self.order_updates)}")

    def event_handler_quote_update(self, message: dict[str, Any]) -> None:
        val = message.get("lp", False)
        if val:
            key = message["e"] + "|" + message["tk"]
            self.ltp[key] = float(val)
            logging.debug(f"📊 LTP update: {key} = {val}, total ltp keys: {len(self.ltp)}")

    def subscribe(self, tokens: list[str]) -> None:
        if self.socket_opened:
            self.api.broker.subscribe(tokens, feed_type="d")
            self.tokens = tokens
        else:
            logging.warning("Websocket not opened, cannot subscribe")


if __name__ == "__main__":
    from helper import Helper

    token = ["NSE|22", "NSE|34"]
    wserver = Wserver(Helper.api, token)
    while True:
        logging.debug(f"LTP: {wserver.ltp}")
        time.sleep(1)
        # wserver.tokens = ["NSE:25"]
