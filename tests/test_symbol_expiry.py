"""Tests for Symbol.get_next_expiry() with real calendar dates.

Hermetic by design:
- `toolkit.fileutils` is stubbed so Symbol.__init__ never hits the network
  (is_file_not_2day -> False, the fixture CSV is treated as fresh).
- `src.constants` is stubbed so importing src.symbol needs no broker
  credential files (real src.constants eagerly reads ../uma_scalper.yml).
- Each test runs in a tmp dir; Symbol resolves ./data/NFO_symbols.csv there.

Expiries are generated relative to datetime.now() (real dates) in the
broker's "%d-%b-%Y" format, e.g. 12-Oct-2026.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _install_stubs():
    """Stub toolkit + src.constants, saving any real modules for restore."""
    saved = {}
    for name in ("toolkit", "toolkit.fileutils", "src.constants"):
        if name in sys.modules:
            saved[name] = sys.modules[name]

    toolkit = ModuleType("toolkit")
    fileutils_mod = ModuleType("toolkit.fileutils")

    class FakeFileutils:
        def is_file_not_2day(self, csvfile):
            return False  # fixture CSV is always fresh -> no download

    fileutils_mod.Fileutils = FakeFileutils
    toolkit.fileutils = fileutils_mod
    sys.modules["toolkit"] = toolkit
    sys.modules["toolkit.fileutils"] = fileutils_mod

    mock_const = ModuleType("src.constants")
    mock_const.dct_sym = {
        "NIFTY": {"diff": 50, "index": "Nifty 50", "exchange": "NSE", "token": "26000", "depth": 9},
        "BANKNIFTY": {"diff": 100, "index": "Nifty Bank", "exchange": "NSE", "token": "26009", "depth": 25},
    }
    mock_const.logging = MagicMock()
    sys.modules["src.constants"] = mock_const
    return saved


_saved_modules = _install_stubs()

from src.symbol import Symbol  # noqa: E402  (after stubs)

# Restore so sibling test modules (e.g. test_tickrunner) get pristine imports.
# Symbol keeps working: it holds the stubs in its own module globals.
for _name in ("src.symbol", "src.constants", "toolkit.fileutils", "toolkit"):
    if _name in _saved_modules:
        sys.modules[_name] = _saved_modules[_name]
    else:
        sys.modules.pop(_name, None)
del _saved_modules


EXP_FMT = "%d-%b-%Y"


def _datestr(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime(EXP_FMT)


@pytest.fixture
def symbols_csv(tmp_path, monkeypatch):
    """Write ./data/NFO_symbols.csv in an isolated cwd, return a writer."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    def write(rows: list[tuple[str, str]]) -> Path:
        csvfile = data_dir / "NFO_symbols.csv"
        with open(csvfile, "w") as f:
            f.write("Symbol,Expiry\n")
            for symbol, expiry in rows:
                f.write(f"{symbol},{expiry}\n")
        return csvfile

    return write


def _nifty(exchange="NFO", symbol="NIFTY") -> Symbol:
    return Symbol(exchange=exchange, base=symbol, symbol=symbol)


class TestGetNextExpiry:
    def test_today_expiry_is_selected(self, symbols_csv):
        today = _datestr(0)
        symbols_csv(
            [
                ("NIFTY", _datestr(-3)),
                ("NIFTY", today),
                ("NIFTY", _datestr(7)),
            ]
        )
        assert _nifty().get_next_expiry() == today

    def test_next_future_selected_when_no_today(self, symbols_csv):
        symbols_csv(
            [
                ("NIFTY", _datestr(-10)),
                ("NIFTY", _datestr(9)),
                ("NIFTY", _datestr(2)),
            ]
        )
        assert _nifty().get_next_expiry() == _datestr(2)

    def test_other_symbols_ignored(self, symbols_csv):
        # BANKNIFTY expires today, but NIFTY must not pick it up
        symbols_csv(
            [
                ("NIFTY", _datestr(-5)),
                ("NIFTY", _datestr(5)),
                ("BANKNIFTY", _datestr(0)),
            ]
        )
        assert _nifty().get_next_expiry() == _datestr(5)

    def test_malformed_expiry_skipped(self, symbols_csv):
        today = _datestr(0)
        symbols_csv(
            [
                ("NIFTY", "not-a-date"),
                ("NIFTY", today),
            ]
        )
        assert _nifty().get_next_expiry() == today

    def test_all_malformed_returns_none(self, symbols_csv):
        symbols_csv([("NIFTY", "garbage")])
        assert _nifty().get_next_expiry() is None
