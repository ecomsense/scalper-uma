# tick_generator.py
import time
from datetime import datetime
from src.symbols import Symbols, dct_sym
from traceback import print_exc
from src.constants import O_SETG, logging
from src.api import Helper
from src.wserver import Wserver

# Define the path to your ticks.csv file
TICK_CSV_PATH = "./data/ticks.csv"


def main():
    try:
        Helper.api()
        tokens_of_all_trading_symbols = {}
        base = O_SETG["trade"]["base"]
        values = O_SETG[base] | dct_sym[base]
        sym = Symbols(
            option_exchange=values["option_exchange"],
            base=base,
            expiry=values["expiry"],
        )
        sym.get_exchange_token_map_finvasia()
        exchange = values["exchange"]
        token = values["token"]
        ltp_for_underlying = Helper.ltp(exchange, token)
        values["atm"] = sym.get_atm(ltp_for_underlying)
        tokens_of_all_trading_symbols.update(sym.get_tokens(values["atm"]))
        return tokens_of_all_trading_symbols
    except Exception as e:
        logging.error(f"{e} in main")
        print_exc()


def new(res, token_ltp):
    buffer = []
    for token, quote in token_ltp.items():
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp},{res[token]},{float(quote):.2f},0\n"
        buffer.append(line)

    with open(TICK_CSV_PATH, "a") as f:
        f.writelines(buffer)
        buffer.clear()
        # print(f"Wrote tick: {line.strip()}") # Uncomment to see every tick in console


if __name__ == "__main__":
    try:
        res = main()
        tokens = list(res.keys())
        ws = Wserver(Helper.api(), tokens)
        while True:
            new(res, ws.ltp)
            time.sleep(0.5)  # Write a new tick every 0.5 seconds
    except KeyboardInterrupt:
        print("\nTick generator stopped.")
    except Exception as e:
        print(f"Error in main: {e}")
