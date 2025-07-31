from traceback import print_exc
from importlib import import_module
from src.constants import O_CNFG, logging


def login():
    broker_name = O_CNFG.get("broker", None)
    if not broker_name:
        raise ValueError("broker not specified in credential file")

    # Dynamically import the broker module
    module_path = f"stock_brokers.{broker_name}.{broker_name}"
    broker_module = import_module(module_path)

    logging.info(f"BrokerClass: {broker_module}")
    # Get the broker class (assuming class name matches the broker name)
    BrokerClass = getattr(broker_module, broker_name.capitalize())

    # Initialize API with config
    print(O_CNFG)
    broker_object = BrokerClass(**O_CNFG)
    if broker_object.authenticate():
        logging.info("api connected")
        print("connected")
        return broker_object
    else:
        print("failed to connect, exiting")
        __import__("sys").exit(1)


class Helper:
    _api = None
    _orders = []

    @classmethod
    def api(cls):
        if cls._api is None:
            cls._api = login()
        return cls._api
    
    @classmethod
    def one_side(self, bargs):
        try:
            resp = self._api.order_place(**bargs)
            return resp
        except Exception as e:
            message = f"helper error {e} while placing order {bargs}"
            logging.warning(message)
            print_exc()

    @classmethod
    def orders(cls):
        cls._orders = cls._api.orders
        return cls._orders
    
    @classmethod
    def get_orders(cls):
        return cls._orders

    @classmethod
    def ltp(cls, exchange, token):
        try:
            resp = cls._api.scriptinfo(exchange, token)
            if resp is not None:
                return float(resp["lp"])
            else:
                raise ValueError("ltp is none")
        except Exception as e:
            message = f"{e} while ltp"
            logging.error(message)
            print_exc()

    @classmethod
    def modify_order(cls, kwargs):
        try:
            if next((v for v in kwargs.values() if v is not None), None):
                resp = cls._api.order_modify(**kwargs)
                return resp
        except Exception as e:
            message = f"helper error {e} while modifying order"
            logging.warning(message)
            print_exc()

    @classmethod
    def close_positions(cls):
        for pos in cls._api.positions:
            if pos and pos["quantity"] == 0:
                continue
            elif pos:
                quantity = abs(pos["quantity"])

                if pos["quantity"] < 0:
                    args = dict(
                        symbol=pos["symbol"],
                        quantity=quantity,
                        disclosed_quantity=quantity,
                        product=pos["prd"],
                        side="B",
                        order_type="MKT",
                        exchange="NFO",
                        tag="close",
                    )
                    resp = cls._api.order_place(**args)
                    logging.debug(f"api responded with {resp}")
                elif quantity > 0:
                    args = dict(
                        symbol=pos["symbol"],
                        quantity=quantity,
                        disclosed_quantity=quantity,
                        product=pos["prd"],
                        side="S",
                        order_type="MKT",
                        exchange=pos["exchange"],
                        tag="close",
                    )
                    resp = cls._api.order_place(**args)
                    logging.debug(f"api responded with {resp}")

    @classmethod
    def mtm(cls):
        try:
            pnl = 0
            positions = [{}]
            positions = cls._api.positions
            """
            keys = [
                "symbol",
                "quantity",
                "last_price",
                "urmtom",
                "rpnl",
            ]
            """
            if any(positions):
                # calc value
                for pos in positions:
                    pnl += pos["urmtom"]
        except Exception as e:
            message = f"while calculating {e}"
            logging.error(f"api responded with {message}")
        finally:
            return pnl


if __name__ == "__main__":
    from pprint import pprint
    import pandas as pd
    from src.constants import S_DATA

    Helper.api()
    # resp = Helper._api.broker.get_order_book()
    resp = Helper.api().orders
    pprint(resp)
    if resp and any(resp):
        pd.DataFrame(resp).to_csv(S_DATA + "orders.csv", index=False)
        print(pd.DataFrame(resp))
    else:
        print("no response from orders")


    
    resp = Helper.api().positions
    pprint(resp)
    if resp and any(resp):
        pd.DataFrame(resp).to_csv(S_DATA + "positions.csv", index=False)
        print(pd.DataFrame(resp))
    else:
        print("no response from positions")