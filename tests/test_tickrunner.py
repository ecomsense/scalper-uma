import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from types import ModuleType

PROJECT_ROOT = Path(__file__).parent.parent
TRADE_JSON = str(PROJECT_ROOT / "data" / "trade.json")


@pytest.fixture(autouse=True)
def clean_trade_json():
    if os.path.exists(TRADE_JSON):
        os.remove(TRADE_JSON)
    yield
    if os.path.exists(TRADE_JSON):
        os.remove(TRADE_JSON)


@pytest.fixture(autouse=True)
def setup_modules():
    mock_api = ModuleType("src.api")
    mock_helper = MagicMock()
    mock_api.Helper = mock_helper

    mock_const = ModuleType("src.constants")
    mock_const.O_FUTL = {"broker": "finvasia", "api_key": "key", "api_secret": "secret", "lot_size": 75}
    mock_const.logging = MagicMock()
    mock_const.TRADE_JSON = TRADE_JSON

    mock_ws = ModuleType("src.wserver")
    mock_ws.Wserver = MagicMock()

    sys.modules["src.api"] = mock_api
    sys.modules["src.constants"] = mock_const
    sys.modules["src.wserver"] = mock_ws

    yield mock_helper

    for mod in ["src.api", "src.constants", "src.wserver"]:
        if mod in sys.modules:
            del sys.modules[mod]


@pytest.fixture
def mock_wserver():
    ws = Mock()
    ws.ltp = {}
    return ws


@pytest.fixture
def tokens_nearest():
    return {
        "NIFTY28APR26P23800": "NIFTY28APR26P23800",
        "NIFTY28APR26C25050": "NIFTY28APR26C25050",
    }


@pytest.fixture
def mock_helper(setup_modules):
    return setup_modules


class TestTickRunner:
    def test_loads_existing_trade_from_file(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)

        assert runner.entry_id == "26042100278879"
        assert runner.symbol == "NIFTY28APR26P23800"
        assert runner.quantity == 65
        assert runner.exit_price == 54.4
        assert runner.target_price == 56.4
        assert runner.fn == "is_trade"

    def test_is_trade_places_exit_when_entry_complete(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_helper.orders.return_value = [
            {"order_id": "26042100278879", "status": "COMPLETE"}
        ]
        mock_helper.one_side.return_value = "26042100278880"

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.run_state_machine()

        mock_helper.one_side.assert_called_once()
        call_args = mock_helper.one_side.call_args[0][0]
        assert call_args["side"] == "SELL"
        assert call_args["order_type"] == "SL"
        assert call_args["symbol"] == "NIFTY28APR26P23800"
        assert call_args["quantity"] == 65
        assert call_args["price"] == 54.4
        assert runner.fn == "exit_trade"

    def test_is_trade_clears_when_entry_rejected(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_helper.orders.return_value = [
            {"order_id": "26042100278879", "status": "REJECTED"}
        ]

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.run_state_machine()

        assert runner.entry_id == ""
        assert runner.fn == "create"

    def test_exit_trade_modifies_to_limit_when_target_reached(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "exit_id": "26042100278880",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_wserver.ltp = {"NIFTY28APR26P23800": 57.0}
        mock_helper.orders.return_value = [
            {"order_id": "26042100278880", "status": "OPEN"}
        ]

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.exit_id = "26042100278880"
        runner.symbol = "NIFTY28APR26P23800"
        runner.quantity = 65
        runner.exchange = "NFO"
        runner.target_price = 56.4
        runner.exit_price = 54.4
        runner.fn = "exit_trade"

        runner.run_state_machine()

        mock_helper.modify_order.assert_called_once()
        call_args = mock_helper.modify_order.call_args[0][0]
        assert call_args["order_type"] == "LMT"
        assert runner.fn == "create"

    def test_exit_trade_completes_when_exit_filled(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "exit_id": "26042100278880",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_helper.orders.return_value = [
            {"order_id": "26042100278880", "status": "COMPLETE"}
        ]

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.exit_id = "26042100278880"
        runner.fn = "exit_trade"

        runner.run_state_machine()

        assert runner.entry_id == ""
        assert runner.exit_id == ""
        assert runner.fn == "create"

    def test_create_clears_when_no_trade(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        assert runner.entry_id == ""
        assert runner.fn == "create"

        runner.run_state_machine()

        assert runner.entry_id == ""
        assert runner.fn == "create"

    def test_ltp_monitoring_for_target_hit(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "exit_id": "26042100278880",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_wserver.ltp = {"NIFTY28APR26P23800": 57.0}
        mock_helper.orders.return_value = [
            {"order_id": "26042100278880", "status": "OPEN"}
        ]

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.exit_id = "26042100278880"
        runner.symbol = "NIFTY28APR26P23800"
        runner.quantity = 65
        runner.exchange = "NFO"
        runner.target_price = 56.4
        runner.exit_price = 54.4
        runner.fn = "exit_trade"

        runner.run_state_machine()

        mock_helper.modify_order.assert_called_once()

    def test_ltp_monitoring_for_stop_loss_hit(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        trade_data = {
            "entry_id": "26042100278879",
            "exit_id": "26042100278880",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_wserver.ltp = {"NIFTY28APR26P23800": 54.0}
        mock_helper.orders.return_value = [
            {"order_id": "26042100278880", "status": "OPEN"}
        ]

        from tickrunner import TickRunner

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.exit_id = "26042100278880"
        runner.symbol = "NIFTY28APR26P23800"
        runner.quantity = 65
        runner.exchange = "NFO"
        runner.target_price = 56.4
        runner.exit_price = 54.4
        runner.fn = "exit_trade"

        runner.run_state_machine()

        mock_helper.modify_order.assert_called_once()


class TestTradeJsonPersistence:
    def test_trade_json_saved_after_entry(
        self, mock_helper, mock_wserver, tokens_nearest
    ):
        from tickrunner import TickRunner

        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        with open(TRADE_JSON, "w") as f:
            json.dump(trade_data, f)

        mock_helper.orders.return_value = [
            {"order_id": "26042100278879", "status": "COMPLETE"}
        ]
        mock_helper.one_side.return_value = "26042100278880"

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.run_state_machine()

        with open(TRADE_JSON, "r") as f:
            saved = json.load(f)

        assert saved["exit_id"] == "26042100278880"
        assert saved["entry_id"] == "26042100278879"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])