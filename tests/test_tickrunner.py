import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
TRADE_JSON = PROJECT_ROOT / "data" / "trade.json"

sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture(autouse=True)
def clean_trade():
    if TRADE_JSON.exists():
        TRADE_JSON.unlink()
    yield
    if TRADE_JSON.exists():
        TRADE_JSON.unlink()


@pytest.fixture
def mock_wserver():
    ws = MagicMock()
    ws.ltp = {}
    return ws


@pytest.fixture
def tokens_nearest():
    return {
        "NIFTY28APR26P23800": "NIFTY28APR26P23800",
        "NIFTY28APR26C25050": "NIFTY28APR26C25050",
    }


@pytest.fixture
def mock_broker():
    broker = MagicMock()
    broker.order_place.return_value = "ORD_12345"
    return broker


@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch("api.Helper") as mock_helper, \
         patch("wserver.Wserver") as mock_ws, \
         patch("constants.O_FUTL") as mock_o_futl, \
         patch("constants.logging") as mock_logging:
        mock_helper.orders.return_value = []
        mock_helper.one_side.return_value = ""
        mock_helper.modify_order.return_value = ""
        mock_o_futl.read_file.return_value = {}
        mock_o_futl.write_file.return_value = None
        yield {
            "helper": mock_helper,
            "ws": mock_ws,
            "o_futl": mock_o_futl,
            "logging": mock_logging,
        }


class TestTickRunner:
    def test_create_clears_when_no_trade(self, mock_wserver, tokens_nearest):
        from tickrunner import TickRunner
        from constants import O_FUTL

        O_FUTL.read_file.return_value = {}

        runner = TickRunner(mock_wserver, tokens_nearest)
        assert runner.entry_id == ""
        assert runner.fn == "create"

    def test_is_trade_clears_when_entry_rejected(self, mock_wserver, tokens_nearest):
        from tickrunner import TickRunner
        from constants import O_FUTL
        from api import Helper

        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        O_FUTL.read_file.return_value = trade_data
        Helper.orders.return_value = [{"order_id": "26042100278879", "status": "REJECTED"}]

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.run_state_machine()

        assert runner.entry_id == ""
        assert runner.fn == "create"

    def test_exit_trade_completes_when_exit_filled(self, mock_wserver, tokens_nearest):
        from tickrunner import TickRunner
        from constants import O_FUTL
        from api import Helper

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
        O_FUTL.read_file.return_value = trade_data
        Helper.orders.return_value = [{"order_id": "26042100278880", "status": "COMPLETE"}]

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.exit_id = "26042100278880"
        runner.fn = "exit_trade"

        runner.run_state_machine()

        assert runner.entry_id == ""
        assert runner.exit_id == ""
        assert runner.fn == "create"


class TestTradeJsonPersistence:
    def test_trade_json_saved_after_entry(self, mock_wserver, tokens_nearest):
        from tickrunner import TickRunner
        from constants import O_FUTL
        from api import Helper

        trade_data = {
            "entry_id": "26042100278879",
            "symbol": "NIFTY28APR26P23800",
            "quantity": 65,
            "exchange": "NFO",
            "tag": "no_tag",
            "exit_price": 54.4,
            "target_price": 56.4,
        }
        O_FUTL.read_file.return_value = trade_data
        Helper.orders.return_value = [{"order_id": "26042100278879", "status": "COMPLETE"}]
        Helper.one_side.return_value = "26042100278880"

        runner = TickRunner(mock_wserver, tokens_nearest)
        runner.run_state_machine()

        O_FUTL.write_file.assert_called_once()
        call_args = O_FUTL.write_file.call_args[0]
        assert call_args[0] == str(TRADE_JSON)
        assert call_args[1]["exit_id"] == "26042100278880"
        assert call_args[1]["entry_id"] == "26042100278879"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])