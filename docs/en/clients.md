# Client Setup Guide

English | [中文](../使用指南.md)

This assumes the service is running at `http://your-host:8000` (locally that is `http://127.0.0.1:8000`).

## The three things you need

| Item | Value |
|---|---|
| **Base URL** | `http://your-host:8000/v1` |
| **API Key** | `API_KEY` from `.env`, or a distributed key created in the dashboard |
| **Model** | `deepseek-v3` and friends — full list in [06-models.md](06-models.md) |

Authentication is the standard header `Authorization: Bearer <API_KEY>`.

> **Should the URL end with `/v1`?** It depends on the client: if the field is labelled "API Host" and the
> client appends `/v1` itself, use `http://your-host:8000`; otherwise use `http://your-host:8000/v1`.
> Sanity check: after filling it in, click "fetch model list" — you should get 35 models.

---

## GUI clients

**Cherry Studio / ChatBox / LobeChat / NextChat / Open WebUI / One API**

1. Add a provider → choose "OpenAI" or "Custom OpenAI"
2. API address: `http://your-host:8000/v1`
3. API key: your key
4. Models: click "fetch models" or type `deepseek-v3` manually

These clients issue requests from a browser or Electron context; the server sends `CORS: *`, so they work directly.

**Translation / selection-popup extensions**

- Custom API domain: `http://your-host:8000`
- Prefer a fast model: `glm-5.0-turbo`, `kimi-k2.7`

**Cursor / Continue / Cline (VS Code)**

- Provider: `OpenAI Compatible`
- Base URL: `http://your-host:8000/v1`
- Model name (plugins that cannot auto-fetch): `deepseek-v3`
- Cursor's Verify button calls `/v1/models`; if it passes, you are set

**Dify / FastGPT / n8n**

- Add an "OpenAI-API-compatible" model provider
- API endpoint: `http://your-host:8000/v1`
- Add each model name from the list individually

**SillyTavern**

- API: `OpenAI Compatible`
- Reverse proxy URL: `http://your-host:8000/v1`
- Custom model name: `deepseek-v3`

---

## Calling it from code

**Python (openai >= 1.0)**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-host:8000/v1",
    api_key="<API_KEY>",
)

resp = client.chat.completions.create(
    model="deepseek-v3",
    messages=[{"role": "user", "content": "hello"}],
    extra_body={"reasoning_effort": "low"},   # optional: low/medium/high/max
)
print(resp.choices[0].message.content)
```

Streaming:

```python
stream = client.chat.completions.create(
    model="deepseek-v3",
    messages=[{"role": "user", "content": "write a poem about autumn"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

**Node.js**

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://your-host:8000/v1",
  apiKey: "<API_KEY>",
});

const r = await client.chat.completions.create({
  model: "deepseek-v3",
  messages: [{ role: "user", content: "hello" }],
});
console.log(r.choices[0].message.content);
```

**LangChain**

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="deepseek-v3",
    base_url="http://your-host:8000/v1",
    api_key="<API_KEY>",
)
print(llm.invoke("hello").content)
```

---

## curl cheat sheet

```bash
KEY=<API_KEY>
B=http://your-host:8000

# health check (no key required)
curl $B/health

# model list
curl $B/v1/models -H "Authorization: Bearer $KEY"

# chat, non-streaming
curl $B/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"hello"}],"stream":false}'

# chat, streaming
curl -N $B/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"hello"}],"stream":true}'

# text to image
curl $B/v1/images/generations \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"hunyuan-image-v3.0","prompt":"an orange cat on a windowsill","size":"1024x1024"}'

# image editing (image accepts an http URL / data URL / raw base64)
curl $B/v1/images/edits \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"prompt":"change the background to snow","image":"https://example.com/a.png"}'
```

> If your machine has a system proxy configured, add `--noproxy '*'` to local curl tests, otherwise the proxy
> may intercept them and answer 502.

---

## Response format

**Reasoning chain** — reasoning-capable models return a `reasoning_content` field (not part of the OpenAI
standard; it follows the DeepSeek convention):

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "final answer",
      "reasoning_content": "the chain of thought…"
    }
  }]
}
```

**Usage** — besides the standard fields, `usage` carries `credit`, the credit cost of that request. The
dashboard accounting reads exactly this value.
