import pytest
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
TRADE_JSON = PROJECT_ROOT / "data" / "trade.json"

sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture(autouse=True)
def setup_modules():
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]

    mock_api = ModuleType("src.api")
    mock_helper = MagicMock()
    mock_helper.orders.return_value = []
    mock_helper.one_side.return_value = ""
    mock_helper.modify_order.return_value = ""
    mock_api.Helper = mock_helper
    sys.modules["src.api"] = mock_api

    mock_const = ModuleType("src.constants")
    mock_const.O_FUTL = MagicMock()
    mock_const.O_FUTL.read_file.return_value = {}
    mock_const.O_FUTL.write_file.return_value = None
    mock_const.logging = MagicMock()
    mock_const.TRADE_JSON = str(TRADE_JSON)
    mock_const.S_LOG = ""
    sys.modules["src.constants"] = mock_const

    mock_wserver = ModuleType("src.wserver")
    mock_wserver.Wserver = MagicMock()
    sys.modules["src.wserver"] = mock_wserver

    yield

    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("src."):
            del sys.modules[mod_name]


@pytest.fixture(autouse=True)
def clean_trade():
    if TRADE_JSON.exists():
        TRADE_JSON.unlink()
    yield
    if TRADE_JSON.exists():
        TRADE_JSON.unlink()