from __future__ import annotations

from src.constants import logging
from src.symbol import Symbol


class Strategy:
    PREM_SEARCH_DEPTH = 50

    def __init__(self, user_settings: dict[str, any], ltp_of_underlying: float) -> None:
        self.tokens_for_all_trading_symbols: dict[str, str] = {}
        expiry = user_settings.get("expiry")
        if not expiry:
            sym_tmp = Symbol(
                exchange=user_settings["option_exchange"],
                base=user_settings["symbol"],
                symbol=user_settings["symbol"],
            )
            expiry = sym_tmp.get_next_expiry()
            user_settings["expiry"] = expiry

        self.sym = Symbol(
            exchange=user_settings["option_exchange"],
            base=user_settings["symbol"],
            symbol=user_settings["symbol"],
            expiry=expiry,
        )
        user_settings["atm"] = self.sym.get_atm(ltp_of_underlying)
        self.tokens_for_all_trading_symbols.update(
            self.sym.get_tokens(user_settings["atm"], depth=self.PREM_SEARCH_DEPTH)
        )
        self.user_settings = user_settings

    def find_trading_symbol_by_atm(
        self, ce_or_pe: str, quotes: dict[str, float]
    ) -> str | None:
        symbols_for_info = list(self.tokens_for_all_trading_symbols.values())
        logging.debug(
            f"symbols for which premiums is going to checked: {symbols_for_info}"
        )
        logging.debug(
            f"premium {self.user_settings['premium']} to be check against quotes {quotes} for closeness "
        )
        quotes = {
            self.tokens_for_all_trading_symbols[k]: v
            for k, v in quotes.items()
            if k in self.tokens_for_all_trading_symbols
        }
        symbol_with_closest_premium = self.sym.find_closest_premium(
            quotes=quotes, premium=self.user_settings["premium"], contains=ce_or_pe
        )
        logging.debug(f"found {symbol_with_closest_premium=}")
        return symbol_with_closest_premium
