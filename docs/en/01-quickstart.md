# 01 · Quick Start

English | [中文](../01-快速开始.md)

Goal: get a working OpenAI-compatible endpoint plus the admin dashboard on your own machine in about five minutes.

## 0. Requirements

- Python 3.10+ (3.11 / 3.12 both fine)
- The **WorkBuddy desktop client** installed and signed in — that is where the token comes from

## 1. Clone

```bash
git clone https://github.com/syh0119/workbuddy2api.git
cd workbuddy2api
```

## 2. Configuration file

```bash
cp .env.example .env
```

Open `.env` and change at least these three lines:

```ini
CODEBUDDY_AUTH_TOKEN=<your access token>
API_KEY=<make one up, e.g. sk-wb-xxxxxxxx>
ADMIN_PASSWORD=<dashboard password>
```

Generate a random `API_KEY`:

```bash
python -c "import secrets;print('sk-wb-'+secrets.token_hex(20))"
```

## 3. Get the token

```bash
python tools/get_token.py
```

- If your client stores the token in **plain text**, the script reads it directly. Add `--write` to save it into `.env`:

  ```bash
  python tools/get_token.py --write
  ```

- If it says the token is **encrypted**, use the DevTools method (30 seconds):

  1. Open the WorkBuddy desktop client (already signed in)
  2. Press `F12` → **Network** tab
  3. Send any message in the client
  4. Find the request to `copilot.tencent.com` → copy the header
     `Authorization: Bearer eyJhbGciOi...` — everything after `Bearer ` is your access token
  5. Write it into `.env`:

     ```bash
     python tools/get_token.py --access <paste here> --write
     ```

  Full details: [02-getting-token.md](02-getting-token.md).

## 4. Install and run

```bash
pip install fastapi uvicorn

# Option A — plain run (automatically loads .env from this directory)
python server.py

# Option B — helper script (also probes for a Python that has fastapi installed)
bash start.sh
```

> `server.py` loads `.env` on startup. **Existing environment variables always win**, so you can either
> put values in `.env` or `export CODEBUDDY_AUTH_TOKEN=...` to override temporarily.

A successful start looks like this:

```
[*] 已从 .env 加载 15 项配置
[✓] CodeBuddy client 初始化成功
[✓] 控制面板就绪  db=<project dir>/admin.db  /admin
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 5. Verify

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)

curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models -H "Authorization: Bearer $KEY"
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"hello"}],"stream":false}'
```

Then open <http://127.0.0.1:8000/admin>, log in with `ADMIN_PASSWORD`, and you should see your credit
balance and the key management UI.

## 6. Point a client at it

Base URL: `http://127.0.0.1:8000/v1` — API key: the `API_KEY` from `.env`.

Per-client instructions: [clients.md](clients.md).

## Next steps

| I want to… | Read |
|---|---|
| Use it from other devices on my LAN or from the internet | [03-docker.md](03-docker.md) |
| Deploy it to my own CasaOS box | [04-casaos.md](04-casaos.md) |
| Hand out keys with quotas to other people | [05-dashboard.md](05-dashboard.md) |
| Switch models, or probe a new model id | [06-models.md](06-models.md) |
| Something is broken | [07-troubleshooting.md](07-troubleshooting.md) |

## Common local pitfalls

- **Port already in use** — set `PORT=` in `.env`.
- **Other devices on the LAN can't connect (Windows)** — the firewall is blocking it. Run
  `enable_lan.ps1` as administrator.
- **`pip install` succeeded but it still complains fastapi is missing** — you have multiple Pythons.
  Check with `python -c "import sys;print(sys.executable)"` and make sure you install and run with the same one.
- **You have a system proxy configured** — add `--noproxy '*'` to local curl tests, otherwise the proxy
  may intercept them and answer 502.
