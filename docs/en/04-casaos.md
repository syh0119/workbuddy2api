# 04 · Deploying to CasaOS

English | [中文](../04-CasaOS部署.md)

CasaOS's "install a custom app" dialog only accepts ready-made images — it **cannot `build:` from source**.
So there are two ways:

- **A. Paste a compose file into the CasaOS UI** (universal, ~3 minutes)
- **B. Drive CasaOS's own API from a script** (no web UI, no SSH, repeatable)

---

## Preparation

```bash
cp .env.example .env
python tools/get_token.py --write     # fill in the token
# then edit .env for API_KEY / ADMIN_PASSWORD
```

Create a data directory on the CasaOS host (CasaOS uses `/DATA` as its root; it maps to `/data` inside containers):

```
/DATA/AppData/workbuddy2api
```

---

## Option A — paste compose into the CasaOS UI

In CasaOS: `+` (top left) → **Install a custom app** → switch to the YAML/paste mode, then paste:

```yaml
name: workbuddy2api

services:
  workbuddy2api:
    image: python:3.11-slim
    container_name: workbuddy2api
    restart: unless-stopped
    working_dir: /app
    command:
      - sh
      - -c
      - |
        set -e
        pip install --no-cache-dir -q -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn
        python - <<'PY'
        import base64, io, os, tarfile
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(os.environ["WB_PAYLOAD"])), mode="r:gz") as t:
            t.extractall("/app")
        PY
        exec python -m uvicorn server:app --host 0.0.0.0 --port 8080
    environment:
      WB_PAYLOAD: "<paste the contents of .build/wb_payload.b64 here>"
      TZ: "Asia/Shanghai"
      ADMIN_DB: "/data/admin.db"
      ADMIN_PASSWORD: "<dashboard password>"
      CODEBUDDY_TOKEN_CACHE: "/data/token.json"
      CODEBUDDY_AUTH_TOKEN: "<access token>"
      CODEBUDDY_REFRESH_TOKEN: "<refresh token>"
      CODEBUDDY_API_BASE: "https://copilot.tencent.com"
      CODEBUDDY_BILLING_BASE: "https://www.workbuddy.cn"
      API_KEY: "<main key>"
      DEFAULT_MODEL: "deepseek-v3"
    ports:
      - "8000:8080"
    volumes:
      - /DATA/AppData/workbuddy2api:/data

x-casaos:
  main: workbuddy2api
  port_map: "8000"
  scheme: http
  is_uncontrolled: true
  title:
    en_us: WorkBuddy2API
    zh_cn: WorkBuddy2API
```

`WB_PAYLOAD` is the **whole application packed into base64 inside an environment variable**, so the container
does not depend on any external download:

```bash
python update.py rebuild      # pack only, no push; writes .build/wb_payload.b64
```

Paste that (one long line) after `WB_PAYLOAD:`.

> Why not just `curl` the code inside the container? Because `python:*-slim` images ship **neither `curl` nor `wget`**.

---

## Option B — deploy through the CasaOS API (recommended)

No web UI login, just a direct call to CasaOS's app management endpoints.

### 1. Credentials

```bash
cp casaos/casaos.env.example casaos/casaos.env
```

Edit `casaos/casaos.env`:

```ini
CASAOS_BASE=http://192.168.1.10:80     # your CasaOS address (default port 80)
CASAOS_USER=your-casaos-username
CASAOS_PWD=your-casaos-password
```

### 2. Deploy

```bash
python update.py            # pack + push + verify
```

Or drive the lower-level script directly:

```bash
cd casaos
python deploy_casaos.py dry       8000   # validate the compose YAML only
python deploy_casaos.py real      8000   # first install
python deploy_casaos.py update    8000   # hot-update an existing app
python deploy_casaos.py logs      8000   # show logs
python deploy_casaos.py uninstall 8000   # remove it
```

---

## The CasaOS app management API (field notes)

This is the calling convention we reverse-engineered; `casaos/deploy_casaos.py` already implements it:

```
POST /v2/app_management/compose?check_port_conflict=false&uncontrolled=true
Authorization: <raw access_token>          ← note: no "Bearer " prefix
Content-Type: application/yaml

<raw YAML body>
```

Common traps:

| Symptom | Cause |
|---|---|
| `500 main service not been specified` | body is not valid YAML (e.g. sent as JSON) |
| `400 there are ports in use` | port conflict; `dry_run` performs this check too |
| `409 is already being installed` | the previous async install has not finished; wait 1–3 minutes |
| App never shows up | a custom app **must** pass `uncontrolled=true` |
| `yaml: line N: mapping values are not allowed` | used `curl -d` (which url-encodes); use `--data-binary` |

Login and queries:

```
POST /v1/users/login                      → data.token.access_token
GET  /v2/app_management/compose            → app list
GET  /v2/app_management/compose/{id}/logs  → container logs
```

More detail: [casaos-api-notes.md](casaos-api-notes.md).

---

## Public access with HTTPS

CasaOS boxes usually also run **Lucky** (reverse proxy + certificates). One rule gets you HTTPS:

1. SSL certificate: ACME for `api.example.com` (use DNS validation if 80/443 are closed)
2. Web service: listen on 443, frontend domain + certificate, backend `127.0.0.1:8000`
3. Open 443 in the server firewall / cloud security group

> When Lucky runs with `network_mode: host`, a loopback address reaches the host port directly.

---

## Updating and troubleshooting

```bash
python update.py            # after code changes
python update.py env        # after changing .env only
python update.py verify     # just check the live service
python update.py logs       # show container logs
```

On Windows you can double-click `update.cmd`.

Data lives in `/DATA/AppData/workbuddy2api/` (`admin.db` holds keys and logs, `token.json` holds the refreshed
token), so upgrading the code never loses it.
