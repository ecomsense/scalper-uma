"""
description:
    contains all the constants
    creates yml files and necessary folders
    for project
"""

from os import path
from traceback import print_exc
from pprint import pprint
from typing import Dict, Any, Optional
from toolkit.logger import Logger
from toolkit.fileutils import Fileutils
import secrets
import hashlib
import base64

O_FUTL: Fileutils = Fileutils()
S_DATA: str = "./data/"

S_LOG: str = S_DATA + "log.txt"
TRADE_JSON: str = S_DATA + "trade.json"
JWT_TOKEN_FILE: str = S_DATA + "jwt_token.txt"
HTPASSWD_FILE: str = S_DATA + ".htpasswd"

SERVER: str = "localhost:8000"
HTPASSWD_USER: str = "trader"
HTPASSWD_PASS: str = "trader123"


def factory(file_in_data_dir: str) -> None:
    if not O_FUTL.is_file_exists(file_in_data_dir):
        logging.debug("creating data dir")
        O_FUTL.add_path(file_in_data_dir)
    else:
        O_FUTL.nuke_file(file_in_data_dir)


lst = [S_LOG]
for item in lst:
    factory(item)

if not O_FUTL.is_file_exists(TRADE_JSON):
    O_FUTL.write_file(TRADE_JSON, {"entry_id": ""})


def get_or_create_jwt_token() -> str:
    if O_FUTL.is_file_exists(JWT_TOKEN_FILE):
        with open(JWT_TOKEN_FILE, "r") as f:
            return f.read().strip()
    else:
        token = secrets.token_urlsafe(32)
        O_FUTL.write_file(JWT_TOKEN_FILE, token)
        return token


def create_htpasswd() -> None:
    if not O_FUTL.is_file_exists(HTPASSWD_FILE):
        password_hash = hashlib.sha1(HTPASSWD_PASS.encode()).hexdigest()
        htpasswd_line = f"{HTPASSWD_USER}:{{SHA}}{base64.b64encode(bytes.fromhex(password_hash)).decode()}"
        O_FUTL.write_file(HTPASSWD_FILE, htpasswd_line)


def yml_to_obj(arg: Optional[str] = None) -> Dict[str, Any]:
    if not arg:
        parent = path.dirname(path.abspath(__file__))
        grand_parent_path = path.dirname(parent)
        folder = path.basename(grand_parent_path)
        lst = folder.split("-")
        file = "_".join(reversed(lst))
        file = "./../" + file + ".yml"
    else:
        file = S_DATA + arg

    flag = O_FUTL.is_file_exists(file)

    if not flag and arg:
        O_FUTL.copy_file("./factory/", "./data/", "settings.yml")
    elif not flag and arg is None:
        __import__("sys").exit()

    return O_FUTL.get_lst_fm_yml(file)


def read_yml() -> tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        O_CNFG = yml_to_obj()
        O_SETG = yml_to_obj("settings.yml")
    except Exception as e:
        print_exc()
        __import__("sys").exit(1)
    else:
        return O_CNFG, O_SETG


O_CNFG: Dict[str, Any]
O_SETG: Dict[str, Any]
O_CNFG, O_SETG = read_yml()

def load_env_settings():
    """Reload settings from settings.yml (clears cache)."""
    global O_CNFG, O_SETG
    get_settings.cache_clear()
    O_CNFG, O_SETG = read_yml()

JWT_TOKEN: str = get_or_create_jwt_token()
create_htpasswd()


def set_logger() -> Logger:
    level = O_SETG["log"]["level"]
    if O_SETG["log"]["show"]:
        return Logger(level)
    return Logger(level, S_LOG)


logging: Logger = set_logger()


dct_sym: Dict[str, Dict[str, Any]] = {
    "NIFTY": {
        "diff": 50,
        "index": "Nifty 50",
        "exchange": "NSE",
        "token": "26000",
        "depth": 9,
    },
    "BANKNIFTY": {
        "diff": 100,
        "index": "Nifty Bank",
        "exchange": "NSE",
        "token": "26009",
        "depth": 25,
    },
}
