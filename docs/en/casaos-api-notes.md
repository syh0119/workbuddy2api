# CasaOS App Management API — Field Notes

English | [中文](../CasaOS部署笔记.md)

This is the API that `casaos/deploy_casaos.py` uses. Applies to CasaOS 0.4.x (verified on 0.4.15).

**No SSH required — just the web UI username and password.**

---

## Login

```http
POST {BASE}/v1/users/login
Content-Type: application/json

{"username":"<user>","password":"<password>"}
```

Read `data.token.access_token` from the response.

---

## Key detail: send the raw token

```http
Authorization: <access_token>
```

**Do not add a `Bearer ` prefix.** Adding it returns 401 — which is the opposite of nearly every other API.

---

## App management endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/v2/app_management/compose` | app list (`data` is a map keyed by app name) |
| GET | `/v2/app_management/compose/{id}` | details, including `status` (running / restarting…) |
| GET | `/v2/app_management/compose/{id}/logs?lines=N` | container logs |
| GET | `/v2/app_management/compose/{id}/containers` | container state |
| POST | `/v2/app_management/compose` | **install** |
| PUT | `/v2/app_management/compose/{id}` | **hot update** (no uninstall needed) |
| DELETE | `/v2/app_management/compose/{id}?delete_config_folder=true` | uninstall |
| PUT | `/v2/app_management/compose/{id}/status` | body `{"status":"restart"}` |

### Install / update request

```http
POST {BASE}/v2/app_management/compose?check_port_conflict=false&uncontrolled=true
Authorization: <raw access_token>
Content-Type: application/yaml

<raw YAML body>
```

Points that matter:

1. **The body is raw YAML** — not JSON, and not a wrapper like `{"compose": ...}`.
2. `Content-Type` must be `application/yaml`.
3. Custom apps **must** pass `uncontrolled=true`, otherwise the install is silently dropped or hangs.
4. `dry_run=true` validates without installing, but it **still performs the port conflict check**
   (an occupied port returns `there are ports in use`).
5. A response of `{"message":"compose app is being installed asynchronously"}` means it is **async** —
   poll the details and logs instead of assuming failure.
6. With `curl`, use `--data-binary @file`, never `-d` (`-d` switches the content type to urlencoded, which
   breaks YAML parsing).

### Compose requirements

```yaml
name: myapp
services:
  myapp:
    image: python:3.11-slim
    container_name: myapp
    restart: unless-stopped
    ports:
      - "8000:8080"
x-casaos:
  main: myapp            # must match a service name, or you get "main service not been specified"
  port_map: "8000"
  scheme: http
  is_uncontrolled: true
  title: { en_us: MyApp, zh_cn: MyApp }
```

- **`build:` is not supported** — CasaOS only pulls images; it cannot build from source.
- `x-casaos.main` plus `port_map` decide where the home-screen icon links to.

---

## How this was reverse-engineered

The CasaOS frontend is a Vue app bundled with webpack, so you can read the answers straight out of its assets:

```bash
# 1. which JS files does the index reference
curl -s http://<casaos>/ | grep -oE '/[^"]+\.js'

# 2. search the main bundle for the API definitions
curl -s http://<casaos>/app.<hash>.js -o app.js
grep -o 'PREFIX2COMPOSE[^;]*' app.js
# → installV2(data, config) { api.post(PREFIX2COMPOSE, data, config) }

# 3. the lazy-loaded chunk contains the real call
curl -s http://<casaos>/src_views_Home_vue.<hash>.js | grep -o 'installComposeApp([^)]*)'

# 4. the OpenAPI client lives in the vendor chunk — parameters and content type included
curl -s http://<casaos>/vendors-node_modules_pnpm_*.js -o vendor.js
grep -o "content-type[^']*" vendor.js
```

The vendor chunk spells out `BASE_PATH = "/v2/app_management"` and
`localVarHeaderParameter['Content-Type'] = 'application/yaml'`, so nothing has to be guessed.

---

## Error reference

| Symptom | Cause |
|---|---|
| `500 main service not been specified` | body is not valid YAML (typically sent as JSON) |
| `400 there are ports in use` | port conflict; `dry_run` checks this too |
| `409 is already being installed` | previous async install still running; wait 1–3 minutes |
| `yaml: line N: mapping values are not allowed` | body was encoded incorrectly (`-d` instead of `--data-binary`), newlines swallowed |
| App never appears in the list | `uncontrolled=true` was not passed |
| Container keeps restarting | check `logs`: usually a bad command or a missing dependency |

---

## One more trap worth remembering

If a system proxy is configured locally, `curl` routes through it. When the proxy cannot reach the upstream it
returns **502 plus an error message localised on your machine** (on Windows:
`由于目标计算机积极拒绝，无法连接。 (os error 10061)`), which is very easy to misread as a server-side failure.

Tell them apart like this:

```bash
curl -s -o /dev/null -w '%{remote_ip}\n' http://your-host/health
```

If it prints `127.0.0.1`, the request went through a local proxy. Add `--noproxy '*'` when testing.
