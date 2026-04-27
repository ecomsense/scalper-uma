from __future__ import annotations

from os import path
from typing import Any

from toolkit.fileutils import Fileutils
from toolkit.logger import Logger

O_FUTL = Fileutils()
S_DATA = str(path.abspath("./data"))
S_LOG = str(path.abspath("./data/log.txt"))
HTPASSWD_FILE = str(path.abspath("./data/.htpasswd"))
TRADE_JSON = str(path.abspath("./data/trade.json"))


def yml_to_obj(arg: str | None = None) -> dict[str, Any]:
    if arg:
        file = S_DATA + "/" + arg
    else:
        parent = path.dirname(path.abspath(__file__))
        grand_parent_path = path.dirname(parent)
        folder = path.basename(grand_parent_path)
        lst = folder.split("-")
        file = "_".join(reversed(lst))
        file = "./../" + file + ".yml"

    flag = O_FUTL.is_file_exists(file)

    if not flag and arg:
        O_FUTL.copy_file("./factory/", "./data/", "settings.yml")
    elif not flag and arg is None:
        import sys
        sys.exit()

    return O_FUTL.get_lst_fm_yml(file)


def read_yml() -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        O_CNFG = yml_to_obj()
        O_SETG = yml_to_obj("settings.yml")
    except Exception:
        from traceback import print_exc
        print_exc()
        import sys
        sys.exit(1)
    else:
        return O_CNFG, O_SETG


# Lazy loader - only load when first accessed
_loaded = False
_O_CNFG: dict[str, Any] = {}
_O_SETG: dict[str, Any] = {}


def _ensure_loaded():
    global _loaded, _O_CNFG, _O_SETG
    if not _loaded:
        _O_CNFG, _O_SETG = read_yml()
        _loaded = True


# These work as module vars but load lazily
def __getattr__(name: str):
    if name in ("O_CNFG", "O_SETG"):
        _ensure_loaded()
        return _O_CNFG if name == "O_CNFG" else _O_SETG
    raise AttributeError(f"module has no attribute '{name}'")


def get_settings() -> tuple[dict[str, Any], dict[str, Any]]:
    """Lazy load settings - only reads config when first accessed."""
    _ensure_loaded()
    return _O_CNFG, _O_SETG


def access_cnfg() -> dict[str, Any]:
    """Access O_CNFG. Use this for tests."""
    _ensure_loaded()
    return _O_CNFG


def access_setg() -> dict[str, Any]:
    """Access O_SETG. Use this for tests."""
    _ensure_loaded()
    return _O_SETG


def load_env_settings():
    """Reload settings from settings.yml."""
    global _loaded, _O_CNFG, _O_SETG
    _loaded = False
    _ensure_loaded()


# Eagerly load on import
_O_CNFG, _O_SETG = read_yml()

# Module-level exports
O_CNFG = _O_CNFG
O_SETG = _O_SETG

# Configure logging from settings
_log_level = 20  # default INFO
if O_SETG.get("log"):
    _log_level = O_SETG["log"].get("level", 20)
    if O_SETG["log"].get("show"):
        logging: Logger = Logger(_log_level, S_LOG)
    else:
        logging: Logger = Logger(_log_level)
else:
    logging: Logger = Logger(20)


dct_sym: dict[str, dict[str, Any]] = {
    "NIFTY": {"diff": 50, "index": "Nifty 50", "exchange": "NSE", "token": "26000", "depth": 9},
    "BANKNIFTY": {"diff": 100, "index": "Nifty Bank", "exchange": "NSE", "token": "26009", "depth": 25},
}
