from __future__ import annotations
import asyncio
from os import path
from typing import Dict, Optional, Any

from src.api import Helper
from src.constants import logging, O_FUTL, TRADE_JSON
from src.wserver import Wserver


def get_dict_from_list(order_id: str) -> Dict[str, Any]:
    try:
        orders = Helper.orders()
        if orders:
            for item in orders:
                if item["order_id"] == order_id:
                    return item
        else:
            logging.warning(f"orders is {orders}")
        return {}
    except Exception as e:
        print(f"{e} in get dict from list")
        return {}


class TickRunner:
    def __init__(self, ws: Wserver, tokens_nearest: Dict[str, str]) -> None:
        self.ws = ws
        self.tokens_nearest = tokens_nearest
        self.fn: str = "create"
        self.ltps: Dict[str, float] = {}
        self.symbol: str = ""
        self.quantity: int = 0
        self.exchange: str = ""
        self.tag: str = ""
        self.entry_id: str = ""
        self.exit_id: str = ""
        self.exit_price: Optional[float] = None
        self.target_price: Optional[float] = None
        self._load_trade_from_file()

    def _load_trade_from_file(self) -> None:
        try:
            if path.exists(TRADE_JSON):
                data = O_FUTL.read_file(TRADE_JSON)
                if data and data.get("entry_id"):
                    self.entry_id = data.get("entry_id", "")
                    self.symbol = data.get("symbol", "")
                    self.quantity = data.get("quantity", 0)
                    self.exchange = data.get("exchange", "")
                    self.tag = data.get("tag", "")
                    self.exit_price = data.get("exit_price")
                    self.target_price = data.get("target_price")
                    if self.entry_id:
                        self.fn = "is_trade"
                        logging.info(f"Loaded trade: entry_id={self.entry_id}, symbol={self.symbol}")
        except Exception as e:
            logging.error(f"{e} _load_trade_from_file")

    def create(self) -> None:
        try:
            self._load_trade_from_file()
            if not self.entry_id:
                O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
                self.fn = "create"
        except Exception as e:
            logging.error(f"{e} while create")

    def is_trade(self) -> None:
        try:
            item = get_dict_from_list(self.entry_id)
            if item and item.get("status", None) == "COMPLETE":
                logging.info(f"Entry COMPLETE: {self.entry_id}, placing exit at {self.exit_price}")
                args = dict(
                    symbol=self.symbol,
                    exchange=self.exchange,
                    quantity=self.quantity,
                    disclosed_quantity=0,
                    side="SELL",
                    order_type="SL",
                    price=self.exit_price,
                    trigger_price=self.exit_price + 0.05,
                    tag=self.tag,
                )
                exit_id = Helper.one_side(args)
                if exit_id:
                    self.exit_id = exit_id
                    logging.info(f"Exit order placed: {exit_id} for {self.symbol}")
                    O_FUTL.write_file(TRADE_JSON, {
                        "entry_id": self.entry_id,
                        "exit_id": self.exit_id,
                        "symbol": self.symbol,
                        "quantity": self.quantity,
                        "exchange": self.exchange,
                        "tag": self.tag,
                        "exit_price": self.exit_price,
                        "target_price": self.target_price,
                    })
                    self.fn = "exit_trade"
            elif item and item.get("status", None) in ["REJECTED", "CANCELED"]:
                logging.info(f"Entry {item.get('status')}: {self.entry_id}, clearing")
                self.entry_id = ""
                self.fn = "create"
            elif item:
                logging.info(f"Entry status: {item.get('status')} for {self.entry_id}")
            else:
                logging.warning(f"Trade status unknown: {self.entry_id}")
        except Exception as e:
            logging.error(f"{e} while is_trade")

    def _is_stopped(self) -> bool:
        item = get_dict_from_list(self.exit_id)
        return bool(item and item["status"] in {"COMPLETE", "REJECTED", "CANCELED"})

    def _is_beyond_band(self) -> bool:
        ltp = self.ltps.get(self.symbol)
        return bool(ltp and (ltp > self.target_price or ltp < self.exit_price))

    def exit_trade(self) -> None:
        try:
            item = get_dict_from_list(self.exit_id)
            order_status = item.get("status", "NOT FOUND") if item else "NO ORDER"
            logging.info(f"EXIT CHECK: order_id={self.exit_id}, status={order_status}")
            if item and item.get("status", None) in ["COMPLETE", "REJECTED", "CANCELED"]:
                logging.info(f"Exit {item.get('status')}: {self.exit_id}, clearing")
                self.fn = "create"
                O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
                self.entry_id = ""
                self.exit_id = ""
            elif item and item.get("status", None) in ["OPEN", "TRIGGER_PENDING"]:
                ltp = self.ltps.get(self.symbol)
                ws_ltp_keys = list(self.ws.ltp.keys())
                logging.info(f"exit_trade: symbol={self.symbol} in tokens_nearest={self.symbol in self.tokens_nearest} in ltps={self.symbol in self.ltps}, ws_ltp_keys={ws_ltp_keys[:3]}..., ltp={ltp}")
                if ltp and (ltp > self.target_price or ltp < self.exit_price):
                    logging.info(f"Target reached for {self.exit_id}, modifying to LIMIT")
                    kwargs = dict(
                        symbol=self.symbol,
                        order_id=self.exit_id,
                        quantity=self.quantity,
                        exchange=self.exchange,
                    )
                    Helper.modify_order(kwargs)
                    self.fn = "create"
                    O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
                else:
                    logging.info(f"Exit OPEN at target:{self.target_price} stop:{self.exit_price}, ltp:{ltp}")
        except Exception as e:
            logging.error(f"{e} exit_trade")

    def run_state_machine(self) -> None:
        try:
            self.ltps = {}
            ws_ltp = self.ws.ltp
            ws_keys = list(ws_ltp.keys())
            for ws_token, trading_symbol in self.tokens_nearest.items():
                if ws_token in ws_ltp:
                    self.ltps[trading_symbol] = ws_ltp[ws_token]
            ltps_keys = list(self.ltps.keys())
            if self.entry_id and self.fn != "create":
                ltp_val = self.ltps.get(self.symbol, "NOT FOUND")
                logging.info(f"TRADE CHECK: fn={self.fn}, entry_id={self.entry_id}, symbol={self.symbol}")
                logging.info(f"TRADE CHECK: tokens_nearest={self.tokens_nearest}")
                logging.info(f"TRADE CHECK: ws_ltp keys={ws_keys}, ltps={ltps_keys}")
                logging.info(f"TRADE CHECK: target={self.target_price}, exit={self.exit_price}, ltp={ltp_val}")
            getattr(self, self.fn)()
        except Exception as e:
            logging.error(f"{e} run_state_machine")

    async def run(self):
        while True:
            try:
                self.run_state_machine()
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"TickRunner.run failed: {e}")
