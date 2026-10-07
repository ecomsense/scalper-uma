# HANDOVER — scalper-uma / clean-slate trixie redeploy

> For the next agent starting with no memory. No secrets in this file — only paths, env names, and commands.

## 0. What happened (timeline 2026-10-07)

1. `candlestick_interval` made dynamic: moved to top level of `factory/settings.yml:8`, new `get_candlestick_interval()` / `get_candlestick_timeframe_seconds()` in `src/main.py:48-54`, returned by `/api/chart/settings`. Commits `5151143`, `e102382`. Verified on server.
2. `data/log.txt` showed `ERROR:websocket: fin=1 opcode=8 data=b'\x03\xf0' - goodbye` x6 and `fastapi_app` showed `failed`. Analysis: close code `0x03f0 = 1008` (broker-initiated Policy Violation) from `websocket-client`, not an app crash by itself. User fixed it themselves; instructed to watch for return.
3. User asked about upgrading bullseye. Server at the time: Debian 11, kernel `5.10.262-1`, sys-python `3.9.2`, venv `3.10.20`, disk `23G/39%`, RAM `958Mi` + `2.3G` swap, service `active (running)` since 19:52 IST, `Linger=yes`, unit loaded as `linked` from factory file.
4. In-place `bullseye -> trixie` apt upgrade failed on `cloud-init`. User used Vultr panel instead → **clean slate**. This repo is the only important app on that instance.
5. `factory/setup.sh` rewritten for the current user-unit layout (commit `29ac601`), this handover created (`411aa72`). Next agent continues from here.

## 1. Orientation

- Local dev checkout: `/home/pannet1/programs/python/github.com/ecomsense/scalper-uma`, branch `main`.
- Server: `65.20.83.178`, user `uma`, app dir `/home/uma/no_env/uma_scalper`.
- Runtime: systemd **user** unit `fastapi_app.service` (`factory/fastapi_app.service`): uvicorn `src.main:app` on `127.0.0.1:8000`, `SKIP_PID_LOCK=1`, `ExecStartPre` kills `:8000` via `fuser` + `sleep 1`, stdout/stderr appended to `data/log.txt`, `Restart=on-failure`.
- Proxy: nginx (`factory/nginx.conf`) → `127.0.0.1:8000`, basic-auth file `data/.htpasswd` (path referenced in `src/constants.py:13`, enforced by nginx, not FastAPI). Direct-app auth via `HTTP_AUTH` env (`src/main.py:104`).
- Python: `pyproject.toml` requires `>=3.10`, `.python-version` pins `3.10`. Trixie system python is newer — **rebuild `.venv` with `uv sync`**, never copy the bullseye venv.
- Config resolution (`src/constants.py:17-36`, no values here): broker credential file sits **outside** the repo at parent dir (`scalper-uma` → `uma_scalper.yml`, i.e. `/home/uma/no_env/uma_scalper.yml`); runtime settings at `data/settings.yml`, seeded from `factory/settings.yml` on first run. `load_env_settings()` reloads both without restarting FastAPI.
- Session TTL: `Helper` in `src/api.py:35` expires broker session after 7h and reconnects.

## 2. Architecture (from AGENTS.md)

Controller `src/main.py` (APScheduler watchdog 60s, PID lock, basic auth, serves `sleeping.html` vs `logic.html`) → logic app `src/logic_app.py` (session start/stop, `TickRunner`, `Strategy`, `Wserver`) → state singleton `src/state.py` (`_logic_state`).

Key routes: `/` and `/logic` (page by schedule+running), `/api/schedule`, `/api/logic/start|stop|status`, `/api/summary`, `/api/orders`, `/api/symbols`, `/api/historical/{symbol}`, `/api/chart/settings`, `/api/admin/logs|settings|status|restart|start|stop|reset`, `/api/trade/buy`, `/api/trade/sell`, `/api/position/add|square`, `/api/order/cancel`, `/sse/candlesticks/{symbol}`, `/sse/orders`.

Key files: `src/main.py` (controller+SSE), `src/logic_app.py` (start/stop), `src/state.py`, `src/api.py` (`Helper`), `src/tickrunner.py`, `src/strategy.py`, `src/wserver.py`, `src/constants.py`, `src/static/*`, `templates/sleeping.html`, `templates/logic.html`, `factory/*`.

Schedule flag: AGENTS.md says `09:15–15:31 Mon–Fri`, but code at `src/main.py:135-143` is `09:15–23:55` due to commit `d799ece` ("maximum time to test"). Confirm with user which one production should use.

## 3. Do-not-repeat gotchas

- `Wserver.ltp` / `order_updates` / `socket_opened` must be **instance** vars (`src/wserver.py:14-16`); class vars leak across restarts.
- Stop order: cancel `runner_task` (2s timeout) → `ws.close_websocket()` (broker's method, not raw socket close) → `_logic_state.reset()` → `Helper.reset()` (`src/logic_app.py:165-195`).
- SSE generators must break on `not _logic_state.is_running()` and re-read `_logic_state.ws` each loop; never cache the old ws.
- Never start uvicorn directly on server — only `systemctl --user restart fastapi_app.service`.
- Never run `factory/setup.sh` pre-`29ac601` steps (old `uma-scalper.service` system unit, stale token filename) — that history is the reason `29ac601` exists.
- Browser caching: static assets and redirects use cache-busting query params; keep them when editing templates.
- `O_SETG` import gotcha: always read via `get_settings()`/`load_env_settings()`, never a stale module-level copy.

## 4. Instructions for the next agent

1. Verify checkout: `git pull && git log --oneline -5` (expect `411aa72` or later), `git status --short` clean.
2. Read `factory/setup.sh`, `factory/fastapi_app.service`, `factory/nginx.conf`, `src/constants.py:1-60` before giving server commands.
3. Ask the user for, in order: (a) trixie `cat /etc/os-release`, (b) whether `uma` user + backup files exist yet — file paths only: `../uma_scalper.yml`, `data/settings.yml`, `data/.htpasswd`. If no backup exists, stop and have them recreate `data/settings.yml` from `factory/settings.yml` plus broker credential file by hand. Never ask for secret values.
4. Redeploy per `factory/setup.sh` (or section 5 below if the script needs trixie tweaks).
5. Verify with section 6 commands. Success = `active (running)` + `/api/schedule` returns `within_schedule` correctly + `/api/chart/settings` returns `candlestick_interval` + no `1008` storm in `data/log.txt`.
6. Confirm open items with user: schedule window (15:31 vs 23:55), nginx vs direct auth, snapshot once green.
7. Keep responses short, cite `file:line`, verify by execution, never print secrets.

## 5. Fresh-trixie deploy (mirror of setup.sh)

```bash
sudo apt update && sudo apt install -y git nginx apache2-utils psmisc python3-venv curl
# install uv, then:
mkdir -p ~/no_env && cd ~/no_env && git clone <repo-url> uma_scalper && cd uma_scalper && git pull
# restore (from backup, never commit): ../uma_scalper.yml, data/settings.yml, data/.htpasswd
# else: cp factory/settings.yml data/settings.yml and recreate the rest by hand
uv sync && .venv/bin/python --version
sudo cp factory/nginx.conf /etc/nginx/sites-available/uma-scalper
sudo ln -sf /etc/nginx/sites-available/uma-scalper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default && sudo nginx -t && sudo systemctl enable --now nginx
[ -f data/.htpasswd ] || htpasswd -c data/.htpasswd trader
mkdir -p ~/.config/systemd/user
ln -sf ~/no_env/uma_scalper/factory/fastapi_app.service ~/.config/systemd/user/fastapi_app.service
systemctl --user daemon-reload && sudo loginctl enable-linger uma
systemctl --user enable --now fastapi_app.service
```

## 6. Verify

```bash
systemctl --user status fastapi_app.service --no-pager -l
journalctl --user -u fastapi_app.service --no-pager -n 50
curl -s http://127.0.0.1:8000/api/schedule; echo
curl -s http://127.0.0.1:8000/api/logic/status; echo
curl -s http://127.0.0.1:8000/api/chart/settings; echo
tail -50 ~/no_env/uma_scalper/data/log.txt
```

## 7. Watch items

1. `1008` goodbye storm returning (duplicate WS sessions / expired broker token — check `Helper` TTL, not code first).
2. `candlestick_interval` UI save → `/api/chart/settings` reflection.
3. Schedule window decision (15:31 vs 23:55).
4. Vultr snapshot once green.
