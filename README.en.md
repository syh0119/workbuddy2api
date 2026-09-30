# WorkBuddy2API · OpenAI-compatible gateway with an admin dashboard

[![CI](https://github.com/syh0119/workbuddy2api/actions/workflows/ci.yml/badge.svg)](https://github.com/syh0119/workbuddy2api/actions/workflows/ci.yml)

Turn the models built into the **WorkBuddy desktop client** (DeepSeek / Kimi / GLM / Hunyuan / MiniMax …) into a
standard **OpenAI-compatible API**, with a **web console** for credit balances, usage stats, API-key
distribution and per-key quotas.

> 中文文档: [README.md](README.md) — this project is a derivative of [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API)

```
┌──────────────┐  OpenAI protocol   ┌─────────────────────┐  WorkBuddy protocol  ┌──────────────────┐
│ any client   │ ─────────────────▶ │ this project        │ ───────────────────▶ │ copilot.tencent  │
│ Cherry/Cursor│ ◀───────────────── │ (FastAPI)           │ ◀─────────────────── │  .com (upstream) │
│ SDK / scripts│   SSE streaming    │ auth·quota·billing  │                      └──────────────────┘
└──────────────┘                    └─────────┬───────────┘
                                              │ credit query
                                              ▼
                                    /billing/meter/get-user-resource-summary
```

---

## Features

**API layer**

- Fully OpenAI-compatible: `/v1/chat/completions`, `/v1/models`, `/v1/images/generations`, `/v1/images/edits`
- `reasoning_content` pass-through, `reasoning_effort` (`low` / `medium` / `high` / `max`)
- tools / tool_calls pass-through
- SSE streaming
- Automatic token refresh (rotated refresh tokens are persisted, so container restarts survive)
- Thread-isolated connections, safe under concurrent requests
- Reverse-proxy friendly: `X-Accel-Buffering: no`, permissive CORS

**Admin dashboard (`/admin`)**

| Module | Capability |
|---|---|
| Credits | Remaining / total / used, broken down per resource pack, manual refresh |
| Usage | Last 7/14/30/90 days, by day / key / model, with a bar chart |
| Request log | Time, key, model, status, latency, tokens, credits, source IP |
| Key distribution | One-click key creation, the secret is shown once |
| Quotas | Unlimited / requests / credits / tokens, optional expiry, **enforced server-side** |
| Key management | Enable, disable, reset usage, regenerate, delete |

**Deployment**

- Three commands to run it locally; Dockerfile and docker-compose work out of the box
- A script that deploys to **CasaOS** through its own API (no web UI, no SSH)
- One-command updater: `python update.py` packs, pushes and verifies

**Quality**

- `tools/ci_checks.py` — one script covering syntax, structure, secrets, Dockerfile references, YAML and doc links
- GitHub Actions runs the same checks on Python 3.10–3.13, boots the server, and builds + smoke-tests the Docker image

---

## Quick start

```bash
git clone https://github.com/syh0119/workbuddy2api.git
cd workbuddy2api

cp .env.example .env
python tools/get_token.py --write     # reads local login state; prints capture steps if encrypted
# edit .env: set API_KEY and ADMIN_PASSWORD

pip install fastapi uvicorn
python server.py
```

Then open:

- Dashboard: `http://127.0.0.1:8000/admin`
- API: `http://127.0.0.1:8000/v1`

Full steps: **[docs/en/01-quickstart.md](docs/en/01-quickstart.md)**.

---

## Documentation

| Doc | Contents |
|---|---|
| [docs/en/01-quickstart.md](docs/en/01-quickstart.md) | Running in five minutes |
| [docs/en/02-getting-token.md](docs/en/02-getting-token.md) | How to obtain the token (incl. encrypted storage) |
| [docs/en/03-docker.md](docs/en/03-docker.md) | Docker / compose / cloud / reverse proxy |
| [docs/en/04-casaos.md](docs/en/04-casaos.md) | Deploying to CasaOS (incl. API automation) |
| [docs/en/05-dashboard.md](docs/en/05-dashboard.md) | Dashboard guide and quota semantics |
| [docs/en/06-models.md](docs/en/06-models.md) | Model list and how to probe new ids |
| [docs/en/07-troubleshooting.md](docs/en/07-troubleshooting.md) | Error reference, streaming, concurrency |
| [docs/en/clients.md](docs/en/clients.md) | Client setup (Cherry / Cursor / Dify / SDKs) |
| [docs/en/casaos-api-notes.md](docs/en/casaos-api-notes.md) | Reverse-engineering notes on the CasaOS API |
| [SECURITY.md](SECURITY.md) | **Read before exposing it to the internet** |
| [CHANGELOG.md](CHANGELOG.md) | What this fork changes |

Chinese documentation lives in [`docs/`](docs/) and is the more detailed of the two.

---

## Configuration

Everything is injected through `.env`; the full list is in [.env.example](.env.example). The ones you will
actually touch:

| Variable | Purpose |
|---|---|
| `CODEBUDDY_AUTH_TOKEN` | **Required** — the WorkBuddy access token |
| `CODEBUDDY_REFRESH_TOKEN` | Strongly recommended, otherwise you re-capture the token by hand when it expires |
| `API_KEY` | The main key clients authenticate with; no quota |
| `ADMIN_PASSWORD` | Dashboard password |
| `DEFAULT_MODEL` | Model used when a request omits `model` |
| `CODEBUDDY_API_BASE` | Upstream base URL, default `https://copilot.tencent.com` |
| `CODEBUDDY_BILLING_BASE` | Credit query base, default `https://www.workbuddy.cn` (**no `/v2` prefix**) |

`.env` is loaded automatically on startup, and **real environment variables take precedence** over the file.

---

## Data and persistence

| Location | Contents |
|---|---|
| `.env` | Credentials and configuration (**excluded by `.gitignore`**) |
| `admin.db` (`/data/admin.db` in containers) | Keys, request log, credit snapshots |
| `/data/token.json` (containers) | Token cache after a refresh |

Upgrading the code never clears this data.

---

## Updating

```bash
python update.py          # repack + push + verify
python update.py env      # only .env changed
python update.py verify   # just check the live service
python update.py logs     # show container logs
```

On Windows you can double-click `update.cmd`; from Git Bash use `bash update_casaos.sh`.

Run the self-check before committing:

```bash
python tools/ci_checks.py --import-smoke
```

---

## Models

35 models ship in the whitelist (32 chat + 3 image); see [docs/en/06-models.md](docs/en/06-models.md).

The upstream exposes **no model listing endpoint**, and the `model` field is passed through verbatim — so to
test whether a new model works, just fire one request:

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"hi"}]}'
```

`Upstream API returned empty response` means that id is not available.

---

## Security (please read)

- `CODEBUDDY_AUTH_TOKEN` in `.env` **is your WorkBuddy account session**. Leaking it means someone else can
  spend your credits. Do not commit it, screenshot it or share it.
- The API and dashboard are **plain HTTP by default**. Before exposing them publicly, at minimum change
  `ADMIN_PASSWORD` and terminate TLS in a reverse proxy (Nginx / Caddy / Lucky).
- Give every distributed key a quota so you can revoke access immediately.
- Details: [SECURITY.md](SECURITY.md).

---

## Disclaimer

This project is for **personal, educational use** — connecting models you are already licensed to use into
your own tools.

- Respect the upstream service's terms of service. Do not resell access, mass-scrape, or otherwise abuse it.
- Do not share your token, and do not deploy this as a service open to the general public.
- You are responsible for any consequences to your account arising from using this project.

---

## Acknowledgements

- [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API) — upstream project (MIT). The API layer
  (upstream protocol handling in `codebuddy_direct_api.py`, the model list, anti-ban strategy) comes from it;
  the storage layer, billing query, dashboard API and deployment tooling are new in this repository.

## License

[MIT](LICENSE)
