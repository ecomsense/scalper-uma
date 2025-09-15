from src.constants import logging
import time


class Wserver:
    # flag to tell us if the websocket is open
    socket_opened = False
    ltp = {}
    order_update = {}

    def __init__(self, session, tokens):
        self.api = session
        self.tokens = tokens
        ret = self.api.broker.start_websocket(
            order_update_callback=self.event_handler_order_update,
            subscribe_callback=self.event_handler_quote_update,
            socket_open_callback=self.open_callback,
        )
        if ret:
            logging.info(f"{ret} ws started")

    def open_callback(self):
        self.socket_opened = True
        self.api.broker.subscribe(self.tokens, feed_type="d")
        # api.subscribe(['NSE|22', 'BSE|522032'])

    def event_handler_order_update(self, message):
        """
        {norenordno': '25091500411068', 'tsym': 'NIFTY16SEP25P25100', 'trantype': 'B', 'qty': '75', 'prc': '45.00', 'pcode': 'I', 'rejreason': "RED:'MIS' Orders are disallowed after system square off", 'status': 'REJECTED', 'reporttype': 'Rejected', 'prctyp': 'SL-LMT', 'ret': 'DAY', 'exchordid': '', 'dscqty': '0', 'trgprc': '44.95'}
        """
        self.order_update["message"] = message

    def event_handler_quote_update(self, message):
        val = message.get("lp", False)
        if val:
            self.ltp[message["e"] + "|" + message["tk"]] = float(val)


if __name__ == "__main__":
    from helper import Helper

    token = ["NSE|22", "NSE|34"]
    wserver = Wserver(Helper.api, token)
    while True:
        print(wserver.ltp)
        time.sleep(1)
        # wserver.tokens = ["NSE:25"]
