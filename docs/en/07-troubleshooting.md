# 07 · Troubleshooting

English | [中文](../07-常见问题.md)

## Startup and configuration

**`请安装依赖: pip install fastapi uvicorn`**

You have multiple Pythons and the one running the server is not the one you installed into:

```bash
python -c "import sys;print(sys.executable)"    # which one is this?
```

Install with that interpreter, or run `python -m uvicorn server:app --host 0.0.0.0 --port 8000` explicitly.

---

**`[!] 未设置 CODEBUDDY_AUTH_TOKEN`**

`.env` was not found or the token is empty. Check:

- `.env` actually exists in the current directory (`ls -la .env`)
- `CODEBUDDY_AUTH_TOKEN=` has a value, is not quoted, and has no stray spaces
- `bash start.sh` loads `.env` for you; when using `python server.py` the built-in loader reads the same file

---

**`初始化失败: 无法获取 token`**

No token in `.env` and no readable local auth file → follow [02-getting-token.md](02-getting-token.md).

---

**Port in use**

```
[Errno 98] Address already in use
```

Set `PORT=8001` in `.env`, or kill the process holding it.

---

## Request errors

| Response | Cause | Fix |
|---|---|---|
| `401 Missing or invalid Authorization header` | no `Authorization` header, or `Bearer ` prefix missing | send `Authorization: Bearer <key>` |
| `403 Invalid API key` | wrong key | copy it from `.env` or the dashboard |
| `403 该 API Key 已被禁用` | key disabled | re-enable it in the dashboard |
| `403 该 API Key 已过期` | past its validity | change the expiry or issue a new key |
| `403 额度已用完（x/y 积分）` | quota exhausted | reset usage or raise the quota |
| `503 CodeBuddy token not configured` | upstream token missing on the server | check `.env` and restart |
| `502 Upstream API error` | upstream connection problem | retry; if it persists, check the logs |
| `502 Upstream API returned empty response` | model id not available, or upstream flaked | try another model; double-check the id |
| `400 messages is required` | request body has no `messages` | use standard OpenAI format |
| `400 Invalid JSON body` | malformed JSON | check quotes/escaping |

---

## Streaming

**The client spins and then dumps everything at once**

The upstream only supports streaming, and this service collects the full answer before pushing chunks to the
client. So:

- clients still show a normal typewriter effect
- but **time-to-first-token equals the full generation time**, it is not real token-by-token streaming

This is a property of the upstream interface, not a bug.

**Streaming hangs behind a reverse proxy**

Disable proxy buffering:

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 300s;
```

With Caddy use `flush_interval -1`.

---

## Concurrency

**Fine with one client, random 502s once several devices call at once**

Older versions shared a single HTTP keep-alive connection across threads, which corrupts when requests
overlap (`CannotSendRequest`, `'NoneType' object has no attribute 'read'`). The current implementation
isolates connections per thread and handles concurrency correctly.

If your fork still has the old code, check that `_conn` in `codebuddy_direct_api.py` is backed by
`threading.local()`.

Note also that the upstream enforces a request interval (`RateLimiter`); heavy concurrency gets queued
automatically. That is anti-ban protection, not a failure.

---

## Docker and CasaOS

**The container keeps restarting**

Look at the logs:

```bash
python update.py logs
# or
docker logs workbuddy2api
```

The two most common causes:

1. the start command uses `curl` or `wget` — `python:*-slim` images have **neither**
2. environment variables were not injected, so `ADMIN_DB` points at a directory that does not exist

---

**CasaOS rejects the custom app**

| Error | Cause |
|---|---|
| `main service not been specified` | the pasted content is not valid YAML (often sent as JSON) |
| `there are ports in use` | port conflict |
| `is already being installed` | the previous async install is still running; wait |
| App never appears | custom apps **must** set `uncontrolled=true` |

---

**Keys and logs disappeared after an upgrade**

`admin.db` was not mounted to a volume. Mount `/data` to a host directory (e.g. `/DATA/AppData/workbuddy2api`)
and set `ADMIN_DB=/data/admin.db`.

---

**The token dies every day and I have to capture it again**

`CODEBUDDY_REFRESH_TOKEN` is missing, or the container has no data volume so the refreshed token is lost.
Add the refresh token and mount `/data` (`CODEBUDDY_TOKEN_CACHE=/data/token.json`).

---

## Networking and IPv6

**Other devices cannot connect**

- host firewall not open (Windows: run `enable_lan.ps1` as administrator)
- cloud security group not open
- the domain resolves to IPv6 only (AAAA record only) → **devices without IPv6 simply cannot reach it**.
  Check with `nslookup -type=A your.domain`

---

**Local curl returns 502 although the service is clearly fine**

A system proxy is configured and curl routes through it. Diagnose with:

```bash
curl -s -o /dev/null -w '%{remote_ip}\n' http://your-host:8000/health
```

If it prints `127.0.0.1`, the request went through a local proxy. Add `--noproxy '*'` when testing.

---

## Dashboard

**`/admin` returns 404**

`static/admin.html` is missing from the deployment. Check inside the container (`ls /app/static`) or re-run
`python update.py`.

**Login says the server has no `ADMIN_PASSWORD`**

`.env` has no `ADMIN_PASSWORD`, or the container did not read it. Set it and restart.

**"尝试过于频繁，请 5 分钟后再试"**

More than 10 failed logins within 5 minutes. Wait a moment.

**Credits show "—"**

The upstream billing query failed; the dashboard header shows the specific error. Common causes: expired
token, wrong `CODEBUDDY_BILLING_BASE` (**do not include a `/v2` prefix**), or the server cannot reach the internet.

---

## Still stuck?

Collect these three things before digging further:

```bash
# 1. service health
curl -s http://127.0.0.1:8000/health

# 2. container logs (container deployments)
python update.py logs

# 3. is the token still valid?
#    see the last section of docs/en/02-getting-token.md

# 4. run the built-in self-check
python tools/ci_checks.py --import-smoke
```
