import asyncio
from datetime import datetime
from os import path

from src.api import Helper
from src.constants import O_SETG, logging, O_FUTL, TRADE_JSON, TICK_CSV_PATH
from src.symbols import Symbols, dct_sym


def get_tokens():
    Helper.api()  # ensure API initialized
    tokens_of_all_trading_symbols = {}

    base = O_SETG["trade"]["base"]
    values = O_SETG[base] | dct_sym[base]

    sym = Symbols(
        option_exchange=values["option_exchange"],
        base=base,
        expiry=values["expiry"],
    )
    sym.get_exchange_token_map_finvasia()

    ltp_for_underlying = Helper.ltp(values["exchange"], values["token"])
    values["atm"] = sym.get_atm(ltp_for_underlying)

    tokens_of_all_trading_symbols.update(sym.get_tokens(values["atm"]))
    return tokens_of_all_trading_symbols


def new_ticks_csv_line(res, token_ltp):
    buffer = []
    ltps = {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for token, quote in token_ltp.items():
        symbol = res[token]
        ltp = round(float(quote), 2)
        ltps[symbol] = ltp
        buffer.append(f"{timestamp},{symbol},{ltp},0\n")

    with open(TICK_CSV_PATH, "a") as f:
        f.writelines(buffer)

    return ltps


def get_dict_from_list(order_id: str):
    try:
        orders = Helper.get_orders()
        if orders:
            for item in orders:
                if item["order_id"] == order_id:
                    return item
        return {}
    except Exception as e:
        print(f"{e} in get dict from list")


class TickRunner:
    def __init__(self, tokens_map, ws):
        self.ws = ws
        self.res = tokens_map  # token => symbol
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
                    print(dict_fm_file["entry_id"], "!=", self.entry_id) 
                    for key, value in dict_fm_file.items():
                        setattr(self, key, value)
                    self.fn = "is_trade"
        except Exception as e:
            logging.error(f"{e} while create")

    def is_trade(self):
        try:
            item = get_dict_from_list(self.entry_id)
            if item and item.get("status", None) == "COMPLETE":
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
                O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
                self.fn = "create"
            elif item:
                logging.info(f"trade status is {item['status']}")
            else:
                logging.warning("trade status unknown")
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
                O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
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
                O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})
                self.fn = "create"
        except Exception as e:
            logging.error(f"{e} exit_trade")

    def run_state_machine(self, ltps):
        try:
            self.ltps = ltps
            getattr(self, self.fn)()
        except Exception as e:
            logging.error(f"{e} run_state_machine")

    async def run(self):
        while True:
            try:
                ltps = new_ticks_csv_line(self.res, self.ws.ltp)
                self.run_state_machine(ltps)
                await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"TickRunner.run failed: {e}")
