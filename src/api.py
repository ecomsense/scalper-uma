from __future__ import annotations
from traceback import print_exc
from importlib import import_module
from typing import Dict, List, Optional, Any
import time
from src.constants import O_CNFG, logging
from stock_brokers.flattrade.api_helper import post_order_hook


def login() -> Any:
    broker_name = O_CNFG.get("broker", None)
    if not broker_name:
        raise ValueError("broker not specified in credential file")

    module_path = f"stock_brokers.{broker_name}.{broker_name}"
    broker_module = import_module(module_path)

    logging.info(f"BrokerClass: {broker_module}")
    BrokerClass = getattr(broker_module, broker_name.capitalize())

    logging.debug(f"Broker credentials: {O_CNFG}")
    broker_object = BrokerClass(**O_CNFG)
    if broker_object.authenticate():
        logging.info("api connected")
        return broker_object
    else:
        logging.critical("failed to connect, exiting")
        __import__("sys").exit(1)


class Helper:
    _api: Optional[Any] = None
    _orders: Optional[List[Dict[str, Any]]] = None
    _initialized: bool = False

    @classmethod
    def api(cls) -> Any:
        if cls._api is None:
            cls._api = login()
            cls._initialized = True
            logging.info("Singleton session created")
        return cls._api

    @classmethod
    def one_side(cls, bargs: Dict[str, Any]) -> Optional[str]:
        order_type = bargs.get("order_type", "LIMIT")
        symbol = bargs.get("symbol", "UNKNOWN")
        side = bargs.get("side", "UNKNOWN")
        price = bargs.get("price", 0)
        trigger_price = bargs.get("trigger_price", 0)
        logging.debug(f"[one_side] >>> ORDER REQUEST: symbol={symbol}, side={side}, order_type={order_type}, price={price}, trigger={trigger_price}")
        try:
            resp = cls._api.order_place(**bargs)
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
    def cancel_orders(cls, symbol: str, keep_order_id: str = None, side: str = None) -> None:
        try:
            orders = cls.orders()
            if not orders:
                return
            for o in orders:
                if o.get("symbol") == symbol and o.get("status") in ["OPEN", "trigger_pending", "PENDING"]:
                    if keep_order_id and o.get("order_id") == keep_order_id:
                        continue
                    if side and o.get("side") != side:
                        continue
                    cancel_args = {"order_id": o.get("order_id"), "quantity": o.get("quantity")}
                    cls._api.order_cancel(**cancel_args)
                    logging.info(f"Cancelled order {o.get('order_id')} for {symbol}")
        except Exception as e:
            logging.error(f"Error cancelling orders: {e}")

    @classmethod
    def orders(cls) -> Optional[List[Dict[str, Any]]]:
        order_book = cls.api().orders()
        if not order_book or len(order_book) == 0:
            return []
        return order_book

    @classmethod
    def historical(
        cls, exchange: str, token: str, interval: int = 1
    ) -> List[Dict[str, Any]]:
        try:
            # Force re-create broker to get fresh session
            logging.info(f"historical: refreshing API session")
            cls._api = None
            api = cls.api()
            logging.info(f"historical: calling broker.get_time_price_series({exchange}, {token})")
            resp = api.broker.get_time_price_series(exchange=exchange, token=token)
            if resp is None:
                logging.error(f"historical: broker returned None for {exchange}|{token}")
                return []
            logging.info(f"historical: broker returned {len(resp)} rows")
            return resp
        except Exception as e:
            logging.error(f"{e} in historical")
            print_exc()
            return []

    @classmethod
    def modify_order(cls, kwargs: Dict[str, Any]) -> Optional[Any]:
        try:
            if next((v for v in kwargs.values() if v is not None), None):
                resp = cls._api.order_modify(**kwargs)
                return resp
        except Exception as e:
            message = f"helper error {e} while modifying order"
            logging.warning(message)
            print_exc()
        return None

    @classmethod
    def close_all_for_symbol(cls, symbol: str, ltp: float, max_retries: int = 5) -> None:
        slippage = 0.50
        for loop in range(max_retries):
            try:
                current_slippage = slippage * (loop + 1)
                cls.cancel_orders(symbol)
                time.sleep(1)
                positions = cls.api().positions
                open_positions = [p for p in positions if p and p.get("symbol") == symbol and p.get("quantity", 0) != 0]
                if not open_positions:
                    logging.info(f"All positions closed for {symbol}")
                    return
                for pos in open_positions:
                    time.sleep(1)
                    quantity = abs(pos["quantity"])
                    sell_price = ltp - current_slippage
                    buy_price = ltp + current_slippage
                    if pos["quantity"] < 0:
                        args = dict(
                            symbol=symbol,
                            quantity=quantity,
                            disclosed_quantity=quantity,
                            product=pos.get("prd", "M"),
                            side="B",
                            order_type="LMT",
                            price=buy_price,
                            trigger_price=0,
                            exchange="NFO",
                            tag=f"close_loop_{loop}",
                        )
                        resp = cls._api.order_place(**args)
                        logging.info(f"Close BUY {symbol} qty={quantity} @ {buy_price} (slippage={current_slippage}): {resp}")
                    elif pos["quantity"] > 0:
                        args = dict(
                            symbol=symbol,
                            quantity=quantity,
                            disclosed_quantity=quantity,
                            product=pos.get("prd", "M"),
                            side="S",
                            order_type="LMT",
                            price=sell_price,
                            trigger_price=0,
                            exchange="NFO",
                            tag=f"close_loop_{loop}",
                        )
                        resp = cls._api.order_place(**args)
                        logging.info(f"Close SELL {symbol} qty={quantity} @ {sell_price} (slippage={current_slippage}): {resp}")
                time.sleep(2)
            except Exception as e:
                logging.error(f"Error in close_all_for_symbol loop {loop}: {e}")

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


if __name__ == "__main__":
    import json
    import pandas as pd
    from src.constants import S_DATA

    Helper.api()
    resp = Helper.orders()
    if resp and any(resp):
        logging.info(f"Orders count: {len(resp)}")
        pd.DataFrame(resp).to_csv(S_DATA + "orders.csv", index=False)
    else:
        logging.info("no response from orders")
    resp = Helper.api().positions
    if resp and any(resp):
        logging.info(f"Positions count: {len(resp)}")
        pd.DataFrame(resp).to_csv(S_DATA + "positions.csv", index=False)
    else:
        logging.info("no response from positions")

    logging.info(f"m2m: {Helper.mtm()}")
