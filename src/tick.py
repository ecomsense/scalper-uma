# tick.py
import time
from datetime import datetime
from src.symbols import Symbols, dct_sym
from traceback import print_exc
from src.constants import O_SETG, logging, O_FUTL, TRADE_JSON
from src.api import Helper
from src.wserver import Wserver
from src.sse_order_client import get_orders
from os import path

# Define the path to your ticks.csv file
TICK_CSV_PATH = "./data/ticks.csv"


def main():
    try:
        Helper.api()
        # initialize
        tokens_of_all_trading_symbols = {}

        # settings
        base = O_SETG["trade"]["base"]
        values = O_SETG[base] | dct_sym[base]

        # initialize symbol object and get tokens
        sym = Symbols(
            option_exchange=values["option_exchange"],
            base=base,
            expiry=values["expiry"],
        )
        sym.get_exchange_token_map_finvasia()

        # get ltp and find atm
        exchange = values["exchange"]
        token = values["token"]
        ltp_for_underlying = Helper.ltp(exchange, token)
        values["atm"] = sym.get_atm(ltp_for_underlying)

        # return tokens and symbol
        tokens_of_all_trading_symbols.update(sym.get_tokens(values["atm"]))
        return tokens_of_all_trading_symbols
    except Exception as e:
        logging.error(f"{e} in main")
        print_exc()


def new(res, token_ltp):
    try:
        buffer = []
        ltps = {}
        for token, quote in token_ltp.items():
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ltp = round(float(quote), 2)
            line = f"{timestamp},{res[token]},{ltp},0\n"
            ltps = {res[token]: ltp}
            buffer.append(line)

        with open(TICK_CSV_PATH, "a") as f:
            f.writelines(buffer)
            buffer.clear()

        return ltps

    except Exception as e:
        logging.error(f"{e} in new")


class Manager:

    def __init__(self):
        self.ltps = {}
        self.fn = "create"
        self.symbol = ""
        self.quantity = 0
        self.exchange = ""
        self.tag = ""
        self.entry_id = ""
        self.exit_price = None
        self.target_price = None

    def create(self):
        """
        {
            "symbol": "NIFTY10JUL25P27850",
            "quantity": 75,
            "exchange": "NFO",
            "tag": "uma_scalper",
            "entry_id": "25070500003440",
            "exit_price": 2370.75,
            "target_price": 2372.75
        }
        """
        if path.exists(TRADE_JSON):
            dict_fm_file = O_FUTL.read_file(TRADE_JSON)
            if dict_fm_file["entry_id"] != self.entry_id:
                for key, value in dict_fm_file.items():
                    setattr(self, key, value)
                self.fn = "exit_trade"

    def _is_target(self):
        return False

    def _is_stopped(self):
        return False

    def exit_trade(self):
        if self._is_stopped():
            self.fn = "create"
        elif self._is_target():
            self.fn = "create"

    def run(self, ltps):
        self.ltps = ltps
        # get sse orders
        orders = get_orders()
        if orders:
            self.orders = orders
        getattr(self, self.fn)()


if __name__ == "__main__":
    try:
        O_FUTL.nuke_file(TICK_CSV_PATH)
        res = main()
        tokens = list(res.keys())
        ws = Wserver(Helper.api(), tokens)
        print(res)
        mgr = Manager()
        while True:
            ltps = new(res, ws.ltp)
            time.sleep(0.5)
            mgr.run(ltps)
    except KeyboardInterrupt:
        print("\nTick generator stopped.")
    except Exception as e:
        print(f"Error in main: {e}")
