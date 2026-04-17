from __future__ import annotations
from typing import Dict, List, Any, Optional, Callable
from src.constants import logging
import time


class Wserver:
    socket_opened: bool = False
    ltp: Dict[str, float] = {}
    order_update: Dict[str, Any] = {}

    def __init__(self, session: Any, tokens: List[str]) -> None:
        self.api = session
        self.tokens = tokens
        ret = self.api.broker.start_websocket(
            order_update_callback=self.event_handler_order_update,
            subscribe_callback=self.event_handler_quote_update,
            socket_open_callback=self.open_callback,
        )
        if ret:
            logging.info(f"{ret} ws started")

    def open_callback(self) -> None:
        self.socket_opened = True
        self.api.broker.subscribe(self.tokens, feed_type="d")

    def event_handler_order_update(self, message: Dict[str, Any]) -> None:
        self.order_update["message"] = message

    def event_handler_quote_update(self, message: Dict[str, Any]) -> None:
        val = message.get("lp", False)
        if val:
            key = message["e"] + "|" + message["tk"]
            self.ltp[key] = float(val)
            print(f"[WS] {key} = {val}")
        else:
            print(f"[WS] No lp in message: {message}")

    def subscribe(self, tokens: List[str]) -> None:
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
        print(wserver.ltp)
        time.sleep(1)
        # wserver.tokens = ["NSE:25"]
