from __future__ import annotations

from datetime import datetime
from traceback import print_exc
from typing import Any

import pandas as pd
from toolkit.fileutils import Fileutils

from src.constants import dct_sym, logging


def get_exchange_token_map_finvasia(csvfile: str, exchange: str) -> None:
    if Fileutils().is_file_not_2day(csvfile):
        url = f"https://api.shoonya.com/{exchange}_symbols.txt.zip"
        logging.debug(f"Downloading symbols from {url}")
        df = pd.read_csv(url)
        df.to_csv(csvfile, index=False)


def get_exchange_token_map_flattrade(csvfile: str, exchange: str) -> None:
    if Fileutils().is_file_not_2day(csvfile):
        if exchange.upper() == "NFO":
            url = "https://flattrade.s3.ap-south-1.amazonaws.com/scripmaster/Nfo_Index_Derivatives.csv"
        elif exchange.upper() == "BFO":
            url = "https://flattrade.s3.ap-south-1.amazonaws.com/scripmaster/Bfo_Index_Derivatives.csv"
        else:
            url = "https://flattrade.s3.ap-south-1.amazonaws.com/scririmaster/Commodity.csv"

        logging.debug(f"Downloading symbols from {url}")
        df = pd.read_csv(url)
        df.rename(
            columns={
                "Optiontype": "OptionType",
                "Strike": "StrikePrice",
                "Tradingsymbol": "TradingSymbol",
                "Lotsize": "LotSize",
            },
            inplace=True,
        )
        df.StrikePrice = df.StrikePrice.astype(int)
        df.to_csv(csvfile, index=False)


class Symbol:
    """
    Class to get symbols from flattrade

    Parameters
    ----------
    symbol : str
        Symbol
    expiry : str
        Expiry

    Returns
    -------
    None
    """

    def __init__(self, exchange: str, base: str | None = None, symbol: str | None = None, expiry: str | None = None) -> None:
        self._exchange = exchange
        self._base = base
        self._symbol = symbol
        self._expiry = expiry
        self.csvfile: str = f"./data/{self._exchange}_symbols.csv"
        get_exchange_token_map_flattrade(self.csvfile, exchange)

    def get_next_expiry(self) -> str:
        df = pd.read_csv(self.csvfile)
        df_sym = df[df["Symbol"] == self._symbol]
        expiries = df_sym["Expiry"].unique()

        today = datetime.now()
        parsed = []
        for e in expiries:
            try:
                dt = datetime.strptime(e, "%d-%b-%Y")
                parsed.append((e, dt))
            except:
                pass

        parsed.sort(key=lambda x: x[1])

        for exp_str, dt in parsed:
            if dt.date() > today.date():
                return exp_str

        return parsed[0][0] if parsed else None

    def get_lot_size(self, strike: int | None = None) -> int:
        df = pd.read_csv(self.csvfile)
        df_filtered = df[
            (df["Symbol"] == self._symbol) & (df["Expiry"] == self._expiry)
        ]
        if strike:
            df_filtered = df_filtered[df_filtered["StrikePrice"] == strike]
        if not df_filtered.empty:
            return int(df_filtered.iloc[0]["LotSize"])
        return 1

    def get_atm(self, ltp: float) -> int:
        try:
            current_strike = ltp - (ltp % dct_sym[self._base]["diff"])
            next_higher_strike = current_strike + dct_sym[self._base]["diff"]
            if ltp - current_strike < next_higher_strike - ltp:
                return int(current_strike)
            return int(next_higher_strike)
        except Exception as e:
            logging.error(f"{e} Symbol: in getting atm")
            print_exc()

    def get_tokens(self, strike: int, depth: int | None = None) -> dict[str, str]:
        try:
            if depth is None:
                depth = dct_sym[self._base]["depth"]
            df = pd.read_csv(self.csvfile)

            lst = [strike]
            for v in range(1, depth):
                lst.append(strike + v * dct_sym[self._base]["diff"])
                lst.append(strike - v * dct_sym[self._base]["diff"])

            filtered_df = df[
                (df["StrikePrice"].isin(lst))
                & (df["Symbol"] == self._symbol)
                & (df["Expiry"] == self._expiry)
            ]

            if "Exchange" not in filtered_df.columns:
                raise KeyError("CSV file is missing 'Exchange' column")

            tokens_found = filtered_df.assign(
                tknexc=lambda x: x["Exchange"] + "|" + x["Token"].astype(str)
            )[["tknexc", "TradingSymbol"]].set_index("tknexc")

            dct = tokens_found.to_dict()
            return dct["TradingSymbol"]
        except Exception as e:
            logging.error(f" {e} in Symbol while getting token")
            print_exc()

    def find_option_type(self, tradingsymbol: str) -> str | None:
        """
        Extracts option type from the CSV file if present.
        """
        df = pd.read_csv(self.csvfile)
        row = df[df["TradingSymbol"] == tradingsymbol]
        if not row.empty:
            return row.iloc[0]["OptionType"]
        return None

    def find_closest_premium(
        self, quotes: dict[str, float], premium: float, contains: str
    ) -> str | None:
        try:
            df = pd.read_csv(self.csvfile)

            # filter
            df = df[(df["Symbol"] == self._symbol) & (df["OptionType"] == contains)]

            # convert the matches to list
            lst_of_tradingsymbols = df["TradingSymbol"].to_list()

            # filter quotes with generated list
            call_or_put_begins_with = {
                k: v for k, v in quotes.items() if k in lst_of_tradingsymbols
            }

            # Create a dictionary to store symbol to absolute difference mapping
            symbol_differences: dict[str, float] = {}

            for symbol, ltp in call_or_put_begins_with.items():
                logging.info(f"Symbol:{symbol} difference {ltp} - {premium}")
                difference = abs(float(ltp) - premium)
                symbol_differences[symbol] = difference

            logging.info(symbol_differences)
            # Find the symbol with the lowest difference
            return min(
                symbol_differences, key=symbol_differences.get, default=None
            )
        except Exception as e:
            logging.error(f"{e} Symbol: find closest premium")
            print_exc()

    def find_option_by_distance(
        self, atm: int, distance: int, c_or_p: str, dct_symbols: dict
    ) -> dict[str, Any] | None:
        try:
            find_strike = (
                atm + (distance * dct_sym[self._base]["diff"])
                if c_or_p == "CE"
                else atm - (distance * dct_sym[self._base]["diff"])
            )
            logging.info(f"Symbol: found strike price {find_strike}")
            df = pd.read_csv(self.csvfile)
            logging.info(f"Symbol:{self._symbol} {c_or_p=} {find_strike=}")
            row = df[
                (df["Symbol"] == self._symbol)
                & (df["OptionType"] == c_or_p)
                & (df["StrikePrice"] == find_strike)
                & (df["Expiry"] == self._expiry)
            ]
            if not row.empty:
                return row.iloc[0]
            raise Exception("Option not found")
        except Exception as e:
            logging.error(f"{e} Symbol: while find_option_by_distance")
            print_exc()

    def find_wstoken_from_tradingsymbol(self, tradingsymbols: list[str]) -> dict[str, str]:
        df = pd.read_csv(self.csvfile)
        filtered_df = df[(df["TradingSymbol"]).isin(tradingsymbols)]
        tokens_found = filtered_df.assign(
            tknexc=lambda x: x["Exchange"] + "|" + x["Token"].astype(str)
        )[["tknexc", "TradingSymbol"]].set_index("tknexc")
        dct = tokens_found.to_dict()
        return dct["TradingSymbol"]


if __name__ == "__main__":
    symbols = Symbol("NFO", "NIFTY")
    dct_tokens = symbols.get_tokens(21500)
    logging.info(f"Tokens: {dct_tokens}")
