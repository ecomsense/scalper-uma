import asyncio
from datetime import datetime
from os import path

from src.api import Helper
from src.constants import logging, O_FUTL, TRADE_JSON, TICK_CSV_PATH
from src.symbol import Symbol


"""
def new_ticks_csv_line(res, token_ltp):
    try:
        buffer = []
        ltps = {}

        for token, quote in token_ltp.items():
            symbol = res.get(token, None)
            if symbol:
                ltp = round(float(quote), 2)
                ltps[symbol] = ltp
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                buffer.append(f"{timestamp},{symbol},{ltp},0\n")

        with open(TICK_CSV_PATH, "a") as f:
            f.writelines(buffer)

        return ltps
    except Exception as e:
        logging.error(f"{e} in new ticks csv line")
"""

def get_dict_from_list(order_id: str):
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


class TickRunner:
    def __init__(self, ws, tokens_nearest: dict):
        self.ws = ws
        self.tokens_nearest = tokens_nearest
        self.fn = "create"
        self.ltps = {}
        self.symbol = ""
        self.quantity = 0
        self.exchange = ""
        self.tag = ""
        self.entry_id = ""
        self.exit_id = ""
        self.exit_price = None
        self.target_price = None
        O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})

    def create(self):
        try:
            if path.exists(TRADE_JSON):
                dict_fm_file = O_FUTL.read_file(TRADE_JSON)
                if dict_fm_file["entry_id"] != self.entry_id:
                    for key, value in dict_fm_file.items():
                        setattr(self, key, value)
                    self.fn = "is_trade"
        except Exception as e:
            logging.error(f"{e} while create")

    def is_trade(self):
        try:
            item = get_dict_from_list(self.entry_id)
            if item and item.get("status", None) == "COMPLETE":
                logging.info(f"attempting to exit trade {self.entry_id}")
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
                    self.fn = "exit_trade"
            elif item and item.get("status", None) in ["REJECTED", "CANCELED"]:
                self.entry_id = ""
                self.fn = "create"
            elif item:
                logging.info(f"trade status is {item['status']}")
            else:
                logging.warning(f"trade status unknown {self.entry_id}")
        except Exception as e:
            logging.error(f"{e} while is_trade")

    def _is_stopped(self):
        item = get_dict_from_list(self.exit_id)
        return (item and item["status"] in {"COMPLETE", "REJECTED", "CANCELED"})

    def _is_beyond_band(self):
        ltp = self.ltps.get(self.symbol)
        return ltp and (ltp > self.target_price or ltp < self.exit_price)

    def exit_trade(self):
        try:
            if self._is_stopped():
                logging.info(f"STOPPED: {self.exit_id}")
                self.fn = "create"
            elif self._is_beyond_band():
                kwargs = dict(
                    symbol=self.symbol,
                    order_id=self.exit_id,
                    quantity=self.quantity,
                    exchange=self.exchange,
                    order_type="MKT",
                    price=0,
                )
                Helper.modify_order(kwargs)
                logging.info(f"EXITED BEYOND BAND: {self.exit_id}")
                self.fn = "create"
        except Exception as e:
            logging.error(f"{e} exit_trade")

    def run_state_machine(self):
        try:
            ltps = self.ws.ltp
            ltps = {k: v for k, v in ltps.items() if k in self.tokens_nearest.keys()}
            self.ltps = {self.tokens_nearest[k]: v for k, v in ltps.items()}
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
