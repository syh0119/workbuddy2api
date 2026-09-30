# 05 · The Admin Dashboard

English | [中文](../05-控制面板.md)

URL: `http://<your-host>:8000/admin` (the root path redirects there)
Password: `ADMIN_PASSWORD` from `.env`

---

## Overview

| Card | Meaning |
|---|---|
| Credits remaining | Currently available credits (from the upstream billing API) |
| Total credits | Sum of all resource packs |
| Spent today | Credits consumed today (accounted by this service) |
| Requests / tokens today | Today's call count and token volume |
| Keys | Enabled / total |
| Log entries | Total rows in the request log |

The progress bar below shows remaining / total; it turns amber below 20%.
Further down, each resource pack is broken out with its own total, used, remaining and utilisation.

Credit data is cached (60 s by default, `ADMIN_CREDIT_REFRESH_SEC`); the **Refresh credits** button forces a fetch.

> The header also shows the upstream base URL and your plan name.

---

## API keys

### Creating a distributed key

Four fields:

| Field | Notes |
|---|---|
| Name | Who it is for, e.g. "Alice's Cherry Studio" |
| Quota type | Unlimited / requests / credits / tokens |
| Quota value | The limit for that type; ignored when "unlimited" |
| Valid for (days) | Empty = never expires |

A new key is **shown in full exactly once** — copy it right away. Afterwards the list only shows a mask like
`sk-wb-1234…abcd`.

### Quota semantics

| Type | How it is counted | Good for |
|---|---|---|
| `none` | No limit | Your own clients |
| `requests` | +1 per call | Simple "here are 100 calls" |
| `credits` | Adds the real credit cost reported by the upstream | The most accurate; equals "I give you N credits" |
| `tokens` | Adds prompt + completion tokens | Usage-based billing |

When a quota is exhausted the request fails immediately with:

```
403 {"detail":"额度已用完（10.02/10 积分）"}
```

This is enforced **server-side** — a client cannot bypass it.

### Row actions

| Action | Effect |
|---|---|
| Enable / disable | Takes effect immediately; disabled keys get `403 该 API Key 已被禁用` |
| Reset usage | Zeroes the used amount (the limit is unchanged) — handy for periodic allowances |
| Regenerate key | Issues a new secret; the old one stops working instantly, the new one is shown once |
| Delete | Permanent and irreversible |

### The main key

The `API_KEY` from `.env` appears in the list as the **main key** and is marked protected: it cannot be
deleted or regenerated and has no quota. That way your already-configured clients never need reconfiguring.

---

## Usage statistics

Ranges: 7 / 14 / 30 / 90 days.

- **Daily usage** — bar chart (requests) plus a table (requests, failures, tokens, credits)
- **By key** — who uses it most, who is producing errors
- **By model** — which model burns the most credits

> This is **this service's own accounting** and only covers requests that pass through it. Usage from the
> upstream client itself (or anywhere else) will not appear here.

---

## Request log

The most recent 200 rows (the API supports up to 1000). Fields:

| Field | Meaning |
|---|---|
| Time | Local time |
| Key | Which key made the call (the main key shows as "主密钥（.env）") |
| Endpoint | `/v1/chat/completions`, `/v1/models`, `/v1/images/…` |
| Model | The `model` field of the request |
| Status | 200 in green, 4xx/5xx in red |
| Latency | End-to-end milliseconds |
| tokens / credits | The real usage reported by the upstream |
| IP | Source address |

**Purge older than 90 days** keeps the database from growing forever.

---

## Where the data lives

| Environment | Database location |
|---|---|
| Running locally | `admin.db` in the project directory (override with `ADMIN_DB`) |
| Docker / CasaOS | `/data/admin.db` inside the container, mapped to the host directory |

Back up or migrate by copying that single file. To reset everything, delete it and restart.

---

## Security advice

The dashboard is plain HTTP, so the password and every key travel in the clear. Therefore:

1. **Never expose port 8000 directly to the internet** — put it behind a reverse proxy with HTTPS
2. Do not use a weak `ADMIN_PASSWORD`
3. Always give distributed keys a quota (`credits` or `requests`) so you can cut them off instantly
4. If only you use it, restrict it to the LAN

---

## Management API (for scripting)

The dashboard is pure API-driven, and the main key doubles as an admin token:

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)
B=http://127.0.0.1:8000

# Overview (credits + stats)
curl -s $B/admin/api/overview -H "X-Admin-Token: $KEY"

# Create a key with 100 credits valid for 30 days
curl -s -X POST $B/admin/api/keys -H "X-Admin-Token: $KEY" -H 'Content-Type: application/json' \
  -d '{"name":"for Alice","quota_type":"credits","quota_limit":100,"expires_in_days":30}'

# Others
curl -s $B/admin/api/keys                     -H "X-Admin-Token: $KEY"   # list
curl -s -X PATCH $B/admin/api/keys/2          -H "X-Admin-Token: $KEY" -H 'Content-Type: application/json' -d '{"enabled":false}'
curl -s -X DELETE $B/admin/api/keys/2         -H "X-Admin-Token: $KEY"
curl -s $B/admin/api/usage?days=7             -H "X-Admin-Token: $KEY"
curl -s "$B/admin/api/logs?limit=100"         -H "X-Admin-Token: $KEY"
curl -s -X POST $B/admin/api/credits/refresh  -H "X-Admin-Token: $KEY"
```

You can also exchange the password for a temporary token (valid 12 hours by default):

```bash
TOKEN=$(curl -s -X POST $B/admin/api/login -H 'Content-Type: application/json' \
  -d '{"password":"your-ADMIN_PASSWORD"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
```
