# Trixie Handover — scalper-uma on Vultr (clean slate)

Date: 2026-10-07. Previous box: Debian 11 bullseye, kernel 5.10.262-1, sys-python 3.9.2, venv python 3.10.20.
New box: Debian 13 trixie via Vultr panel (clean slate). Only important app on the instance is this one.

## 1. Inventory

- Repo: `github.com:ecomsense/scalper-uma`, branch `main`, last pushed `29ac601` ("Fix setup.sh for fastapi_app user service").
- Server: `65.20.83.178`, user `uma`, app dir `/home/uma/no_env/uma_scalper`.
- Runtime: `fastapi_app.service` = systemd **user** unit (`factory/fastapi_app.service`), uvicorn `src.main:app` on `127.0.0.1:8000`, logs appended to `data/log.txt`.
- Reverse proxy: nginx (`factory/nginx.conf`), basic-auth file `data/.htpasswd`. Direct app auth via `HTTP_AUTH` env (`src/main.py:104`).
- Python: `pyproject.toml` needs `>=3.10`, `.python-version` pins `3.10`. Trixie ships 3.13 — rebuild `.venv` with `uv sync`, do not reuse bullseye venv.
- Credential file (broker login): NOT in repo. Resolved by `src/constants.py:17-36` — folder `scalper-uma` reversed to `uma_scalper.yml` at repo parent: `/home/uma/no_env/uma_scalper.yml`. MUST restore from backup.
- Runtime settings: `data/settings.yml` (seeded from `factory/settings.yml` on first run). MUST restore or re-create; contains `candlestick_interval`, `base`, `ma`, `NIFTY/BANKNIFTY` blocks.

## 2. Last known good state (bullseye, before wipe)

- `systemctl --user status fastapi_app.service`: `active (running)` since 2026-10-07 19:52:54 IST, `Linger=yes`.
- `ERROR:websocket: fin=1 opcode=8 data=b'\x03\xf0' - goodbye` x6 in `data/log.txt` = broker close code **1008 Policy Violation** from `websocket-client` (`src/constants.py:116` only throttles to WARNING). User fixed it themselves; watch for return.
- Likely trigger was watchdog (`src/main.py:220-224`, every 60s) creating a new `Wserver` while broker still held old session. If 1008 returns, check duplicate sessions / token expiry (`src/api.py:35`, 7h TTL) before touching code.

## 3. Recent changes (already on `main`)

- `candlestick_interval: 3` top-level in `factory/settings.yml:8`; dynamic via `get_candlestick_interval()` in `src/main.py:48-54`, consumed by `/api/chart/settings`, `/api/historical/{symbol}`, SSE candlesticks. Settings save calls `load_env_settings()` so no FastAPI restart needed.
- `factory/setup.sh` rewritten for user unit (psmisc/nginx/apache2-utils/python3-venv, nginx site, `.htpasswd` skip-if-exists, link user service, `loginctl enable-linger`, `--user daemon-reload/enable/restart`). Do NOT run old `uma-scalper.service` steps — that unit no longer exists.

## 4. Fresh-trixie deploy steps

```bash
# 1. user + login
adduser uma && usermod -aG sudo uma && su - uma
sudo apt update && sudo apt install -y git nginx apache2-utils psmisc python3-venv curl
curl -LsSf astral.sh/uv/install.sh | sh && export PATH="$HOME/.local/bin:$PATH"

# 2. code
mkdir -p ~/no_env && cd ~/no_env
git clone <repo-url> uma_scalper && cd uma_scalper
git pull  # ensure 29ac601 present

# 3. restore secrets (from backup, NEVER commit)
#   /home/uma/no_env/uma_scalper.yml  (broker credentials)
#   /home/uma/no_env/uma_scalper/data/settings.yml
#   /home/uma/no_env/uma_scalper/data/.htpasswd
# If no backup: cp factory/settings.yml data/settings.yml, then fill broker yml + settings by hand.

# 4. venv (trixie python)
uv sync && .venv/bin/python --version

# 5. setup (or run factory/setup.sh)
sudo cp factory/nginx.conf /etc/nginx/sites-available/uma-scalper
sudo ln -sf /etc/nginx/sites-available/uma-scalper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default && sudo nginx -t
sudo systemctl enable --now nginx
[ -f data/.htpasswd ] || htpasswd -c data/.htpasswd trader
mkdir -p ~/.config/systemd/user
ln -sf ~/no_env/uma_scalper/factory/fastapi_app.service ~/.config/systemd/user/fastapi_app.service
systemctl --user daemon-reload
sudo loginctl enable-linger uma
systemctl --user enable --now fastapi_app.service
```

Verify:

```bash
systemctl --user status fastapi_app.service --no-pager -l
curl -s http://127.0.0.1:8000/api/schedule; echo
curl -s http://127.0.0.1:8000/api/logic/status; echo
tail -50 ~/no_env/uma_scalper/data/log.txt
curl -s http://127.0.0.1:8000/api/chart/settings; echo
```

## 5. Known gotchas (do not repeat)

- `Wserver.ltp` / `order_updates` must stay **instance** vars (`src/wserver.py:14-16`); class vars leak across restarts.
- Stop must call `close_websocket()` (`src/logic_app.py:179-186`), then `_logic_state.reset()` + `Helper.reset()`.
- SSE endpoints must break when `not _logic_state.is_running()` or they pin dead sockets.
- `ScheduleConfig` currently `09:15–23:55 Mon–Fri` (`src/main.py:135-143`) — extended hours, confirm whether to revert to `15:31` close.
- `factory/setup.sh` previously deployed wrong unit name; fixed in `29ac601`.

## 6. Open / watch items

1. Confirm 1008 goodbye does not return after redeploy.
2. Confirm `candlestick_interval` change via UI saves + reflects in `/api/chart/settings`.
3. Confirm nginx basic-auth + `HTTP_AUTH` both work through trixie firewall.
4. Take a Vultr snapshot once green.
