from __future__ import annotations

import time
from importlib import import_module
from traceback import print_exc
from typing import Any

from src.constants import access_cnfg, logging


def login() -> Any:
    O_CNFG = access_cnfg()
    broker_name = O_CNFG.get("broker", None)
    if not broker_name:
        raise ValueError("broker not specified in credential file")

    module_path = f"stock_brokers.{broker_name}.{broker_name}"
    broker_module = import_module(module_path)

    logging.info(f"BrokerClass: {broker_module}")
    BrokerClass = getattr(broker_module, broker_name.capitalize())

    logging.debug(f"Broker credentials: {O_CNFG}")
    cnfg = access_cnfg()
    broker_object = BrokerClass(**cnfg)
    if broker_object.authenticate():
        logging.info("api connected")
        return broker_object
    logging.critical("failed to connect, exiting")


class Helper:
    _api: Any | None = None

    @classmethod
    def api(cls) -> Any:
        if cls._api is None:
            cls._api = login()
            logging.info("Singleton session created")
        else:
            logging.info("Using existing session")
        return cls._api

    @classmethod
    def one_side(cls, bargs: dict[str, Any]) -> str | None:
        order_type = bargs.get("order_type", "LIMIT")
        symbol = bargs.get("symbol", "UNKNOWN")
        side = bargs.get("side", "UNKNOWN")
        price = bargs.get("price", 0)
        trigger_price = bargs.get("trigger_price", 0)
        logging.debug(
            f"[one_side] >>> ORDER REQUEST: symbol={symbol}, side={side}, order_type={order_type}, price={price}, trigger={trigger_price}"
        )
        try:
            resp = cls.api().order_place(**bargs)
            logging.debug(f"[one_side] <<< ORDER RESPONSE: {resp}")
            if not resp:
                logging.error(f"[one_side] order_place returned None for {symbol}")
            return resp
        except Exception as e:
            message = f"helper error {e} while placing order {bargs}"
            logging.error(message)
            print_exc()
            return None

    @classmethod
    def cancel_orders(
        cls, symbol: str, keep_order_id: str | None = None, side: str | None = None
    ) -> None:
        print(f">>> cancel_orders: {symbol}")
        try:
            orders = cls.orders()
            if not orders:
                return
            for o in orders:
                if o.get("symbol") == symbol and o.get("status") in [
                    "OPEN",
                    "trigger_pending",
                    "PENDING",
                ]:
                    if keep_order_id and o.get("order_id") == keep_order_id:
                        continue
                    if side and o.get("side") != side:
                        continue
                    cancel_args = {
                        "order_id": o.get("order_id"),
                        "quantity": o.get("quantity"),
                    }
                    cls.api().order_cancel(**cancel_args)
                    logging.info(f"Cancelled order {o.get('order_id')} for {symbol}")
        except Exception as e:
            logging.error(f"Error cancelling orders: {e}")

    @classmethod
    def orders(cls) -> list[dict[str, Any]] | None:
        return cls.api().orders

    @classmethod
    def positions(cls) -> list[dict[str, Any]] | None:
        return cls.api().positions

    @classmethod
    def historical(
        cls, exchange: str, token: str, interval: int = 1
    ) -> list[dict[str, Any]]:
        try:
            logging.info(
                f"historical: calling broker.get_time_price_series({exchange}, {token})"
            )
            resp = cls.api().broker.get_time_price_series(
                exchange=exchange, token=token
            )
            if resp is None:
                logging.error(
                    f"historical: broker returned None for {exchange}|{token}"
                )
                return []
            logging.info(f"historical: broker returned {len(resp)} rows")
            return resp
        except Exception as e:
            logging.error(f"{e} in historical")
            print_exc()
            return []

    @classmethod
    def modify_order(cls, kwargs: dict[str, Any]) -> Any | None:
        try:
            if next((v for v in kwargs.values() if v is not None), None):
                return cls.api().order_modify(**kwargs)
        except Exception as e:
            message = f"helper error {e} while modifying order"
            logging.warning(message)
            print_exc()
        return None

    @classmethod
    def close_all_for_symbol(
        cls, symbol: str, ltp: float, max_retries: int = 5
    ) -> None:
        print(f">>> close_all_for_symbol: {symbol}, ltp={ltp}")
        logging.info(f"close_all_for_symbol START: {symbol}, ltp={ltp}")
        slippage = 0.50
        cls.cancel_orders(symbol)
        time.sleep(1)
        positions = cls.positions()
        open_positions = [
            p
            for p in positions
            if p and p.get("symbol") == symbol and p.get("quantity", 0) != 0
        ]
        logging.info(f"open_positions for {symbol}: {open_positions}")
        if not open_positions:
            logging.info(f"No open positions for {symbol}")
            return
        for pos in open_positions:
            time.sleep(1)
            quantity = abs(pos["quantity"])
            sell_price = ltp - slippage
            buy_price = ltp + slippage
            if pos["quantity"] < 0:
                args = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "disclosed_quantity": quantity,
                    "product": pos.get("prd", "M"),
                    "side": "B",
                    "order_type": "LMT",
                    "price": buy_price,
                    "trigger_price": 0,
                    "exchange": "NFO",
                    "tag": "closebuy",
                }
                resp = cls.api().order_place(**args)
                logging.info(f"Close BUY {symbol} qty={quantity} @ {buy_price}: {resp}")
            elif pos["quantity"] > 0:
                args = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "disclosed_quantity": quantity,
                    "product": pos.get("prd", "M"),
                    "side": "S",
                    "order_type": "LMT",
                    "price": sell_price,
                    "trigger_price": 0,
                    "exchange": "NFO",
                    "tag": "closesell",
                }
                resp = cls.api().order_place(**args)
                logging.info(f"Close SELL {symbol} qty={quantity} @ {sell_price}: {resp}")

    @classmethod
    def mtm(cls) -> float:
        pnl: float = 0.0
        try:
            positions = cls.api().positions
            if any(positions):
                for pos in positions:
                    logging.debug(f"M2M: urmtom={pos['urmtom']}, rpnl={pos['rpnl']}")
                    pnl += pos["urmtom"] + pos["rpnl"]
        except Exception as e:
            message = f"while calculating {e}"
            logging.error(f"api responded with {message}")
        finally:
            return pnl

    @classmethod
    def order_summary(cls):
        orders = cls.orders()

        active_orders_count = 0
        valid_orders = [o for o in orders if o and o.get("order_id")]
        total_orders = len(valid_orders)

        if total_orders > 0:
            active_orders_count = 0
            for o in valid_orders:
                status = o.get("status", "")
                if status in ["OPEN", "PENDING", "TRIGGER_PENDING"]:
                    active_orders_count += 1
        return active_orders_count, total_orders

    @classmethod
    def position_summary(cls):
        positions = cls.positions()
        display_positions = [p for p in positions if p and p.get("quantity", 0) != 0]

        m2m = 0.0
        realized = 0.0
        for pos in positions:
            qty = pos.get("quantity", 0)
            if qty != 0:
                m2m += pos.get("urmtom", 0)
            realized += pos.get("rpnl", 0)

        return positions, len(display_positions), round(m2m, 2), round(realized, 2)

    @classmethod
    def summary(cls):
        # Always get fresh data
        orders = cls.orders()
        positions = cls.positions()

        valid_orders = [o for o in orders if o and o.get("order_id")]
        total_orders = len(valid_orders)

        active_orders_count = 0
        for o in valid_orders:
            status = o.get("status", "")
            if status in ["OPEN", "PENDING", "TRIGGER_PENDING"]:
                active_orders_count += 1

        display_positions = [p for p in positions if p and p.get("quantity", 0) != 0]

        m2m = 0.0
        realized = 0.0
        for pos in positions:
            qty = pos.get("quantity", 0)
            if qty != 0:
                m2m += pos.get("urmtom", 0)
            realized += pos.get("rpnl", 0)

        cls._summary = {
            "orders": valid_orders,
            "active_orders": active_orders_count,
            "order_count": total_orders,
            "positions": positions,
            "position_count": len(display_positions),
            "m2m": round(m2m, 2),
            "realized_pnl": round(realized, 2),
        }
        return cls._summary


if __name__ == "__main__":
    import pandas as pd

    from src.constants import S_DATA

    Helper.api()
    resp = Helper.orders()
    if resp and any(resp):
        logging.info(f"Orders count: {len(resp)}")
        pd.DataFrame(resp).to_csv(S_DATA + "orders.csv", index=False)
    else:
        logging.info("no response from orders")
    resp = Helper.positions()
    if resp and any(resp):
        logging.info(f"Positions count: {len(resp)}")
        pd.DataFrame(resp).to_csv(S_DATA + "positions.csv", index=False)
    else:
        logging.info("no response from positions")

    logging.info(f"m2m: {Helper.mtm()}")
