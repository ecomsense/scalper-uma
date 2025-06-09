from traceback import print_exc
from importlib import import_module
from constants import O_CNFG, logging


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
    broker_object = BrokerClass(**O_CNFG)
    if broker_object.authenticate():
        logging.info("api connected")
        return broker_object
    else:
        __import__("sys").exit(1)


class Helper:
    _api = None

    @classmethod
    def api(cls):
        if cls._api is None:
            cls._api = login()
        return cls._api

    @classmethod
    def orders(cls):
        return cls._api.orders

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
    def one_side(cls, symbol, ltp, quantity, stop):
        try:
            bargs = dict(
                symbol=symbol,
                quantity=int(quantity / 2),
                product="M",
                side="B",
                price=0,
                trigger_price=ltp + stop,
                order_type="SLM",
                exchange="NFO",
                tag="stop",
            )
            logging.error(str(bargs))
            sl1 = cls._api.order_place(**bargs)
            logging.debug(f"api responded with {sl1}")

            if sl1:
                sl2 = cls._api.order_place(**bargs)
                logging.debug(f"api responded with {sl2}")
                if sl2:
                    sargs = dict(
                        symbol=symbol,
                        quantity=quantity,
                        product="M",
                        side="S",
                        price=0,
                        trigger_price=0,
                        order_type="MKT",
                        exchange="NFO",
                        tag="enter",
                    )
                    logging.debug(str(sargs))
                    resp = cls._api.order_place(**sargs)
                    logging.debug(f"api responded with {resp}")
                    return [sl1, sl2], bargs
        except Exception as e:
            message = f"helper error {e} while placing order"
            logging.error(message)
            print_exc()

    @classmethod
    def close_positions(cls, half=False):
        for pos in cls._api.positions:
            if pos["quantity"] == 0:
                continue
            else:
                quantity = abs(pos["quantity"])
                quantity = int(quantity / 2) if half else quantity

            logging.debug(f"trying to close {pos['symbol']}")
            if pos["quantity"] < 0:
                args = dict(
                    symbol=pos["symbol"],
                    quantity=quantity,
                    disclosed_quantity=quantity,
                    product="M",
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
                    product="M",
                    side="S",
                    order_type="MKT",
                    exchange="NFO",
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
    Helper.api()
    resp = Helper._api.finvasia.get_order_book()
    print(resp)
