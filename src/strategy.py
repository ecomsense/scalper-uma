from src.symbol import Symbol
from src.constants import logging


class Strategy:

    def __init__(self, user_settings, ltp_of_underlying):
        self.tokens_for_all_trading_symbols = {}
        self.sym = Symbol(
            exchange=user_settings["option_exchange"],
            base=user_settings["base"],
            symbol=user_settings["base"],
            expiry=user_settings["expiry"],
        )
        user_settings["atm"] = self.sym.get_atm(ltp_of_underlying)
        self.tokens_for_all_trading_symbols.update(
            self.sym.get_tokens(user_settings["atm"])
        )
        self.user_settings = user_settings

    def find_trading_symbol_by_atm(self, ce_or_pe, quotes):
        symbols_for_info = list(self.tokens_for_all_trading_symbols.values())
        logging.info(
            f"symbols for which premiums is going to checked: {symbols_for_info}"
        )
        logging.info(
            f"premium {self.user_settings['premium']} to be check against quotes {quotes} for closeness "
        )
        quotes = {self.tokens_for_all_trading_symbols[k]: v for k, v in quotes.items()}
        symbol_with_closest_premium = self.sym.find_closest_premium(
            quotes=quotes, premium=self.user_settings["premium"], contains=ce_or_pe
        )
        logging.info(f"found {symbol_with_closest_premium=}")
        return symbol_with_closest_premium
