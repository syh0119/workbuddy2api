# WorkBuddy2API · OpenAI-compatible gateway with an admin dashboard

Expose the models built into the **WorkBuddy desktop client** (DeepSeek / Kimi / GLM / Hunyuan / MiniMax …)
as a standard **OpenAI-compatible API**, with a **web dashboard** for credits, usage, API-key distribution and per-key quotas.

> 中文文档: [README.md](README.md)｜Based on [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API)

Features, quick start and full documentation live in the Chinese docs.
This page is a short English summary.

---

## What it does

```
┌──────────────┐  OpenAI protocol  ┌────────────────────┐  WorkBuddy protocol  ┌──────────────────┐
│ any client   │ ────────────────▶ │ this project       │ ───────────────────▶ │ copilot.tencent  │
│ Cherry/Cursor│ ◀──────────────── │ (FastAPI)          │ ◀─────────────────── │  .com (upstream) │
│ SDK / scripts│   SSE streaming   │ auth·quota·logging │                      └──────────────────┘
└──────────────┘                   └────────┬───────────┘
                                            │ credits query
                                            ▼
                                 /billing/meter/get-user-resource-summary
```

- **API layer**: `/v1/chat/completions`, `/v1/models`, `/v1/images/generations`, `/v1/images/edits`
- `reasoning_content` pass-through, `reasoning_effort` (low/medium/high/max), tool calls, SSE streaming
- Automatic token refresh; thread-local HTTP connections for concurrency
- **Dashboard** at `/admin`: credit balance, per-day / per-key / per-model usage, request logs,
  API key issuance with quotas (unlimited / requests / credits / tokens) enforced server-side
- Deploy locally, with Docker, or on **CasaOS** (one-command script that talks to CasaOS's own API)

## Quick start

```bash
git clone https://github.com/<you>/workbuddy2api.git
cd workbuddy2api

cp .env.example .env
python tools/get_token.py --write     # reads local login state; prints capture steps if encrypted
# fill API_KEY and ADMIN_PASSWORD in .env

pip install fastapi uvicorn
python server.py
```

- Dashboard: `http://127.0.0.1:8000/admin`
- API base URL: `http://127.0.0.1:8000/v1`

## Docs

All documentation is in Chinese. Start here:

| Doc | Content |
|---|---|
| [docs/01-快速开始.md](docs/01-快速开始.md) | Get running in 5 minutes |
| [docs/02-获取Token.md](docs/02-获取Token.md) | How to obtain the token |
| [docs/03-Docker部署.md](docs/03-Docker部署.md) | Docker / compose / cloud |
| [docs/04-CasaOS部署.md](docs/04-CasaOS部署.md) | Deploy to CasaOS (incl. API automation) |
| [docs/05-控制面板.md](docs/05-控制面板.md) | Dashboard guide |
| [docs/06-模型与探测.md](docs/06-模型与探测.md) | Model list & how to probe new ids |
| [docs/07-常见问题.md](docs/07-常见问题.md) | Troubleshooting |
| [docs/使用指南.md](docs/使用指南.md) | Client setup (Cherry / Cursor / Dify / SDKs) |
| [SECURITY.md](SECURITY.md) | Security notes — **read before exposing to the internet** |

## Security

- `CODEBUDDY_AUTH_TOKEN` in `.env` **is your WorkBuddy account session**. Never commit or share it.
- The service and dashboard are plain HTTP by default. Put it behind an HTTPS reverse proxy before public use.
- Give every distributed key a quota so you can revoke access easily.

## Disclaimer

For personal, educational use only — connecting models you are already licensed to use into your own tools.
Please respect the upstream service's terms of service. You are responsible for any consequences of use.

## License

[MIT](LICENSE)
