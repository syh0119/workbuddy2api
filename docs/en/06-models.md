# 06 · Models and Probing New Ones

English | [中文](../06-模型与探测.md)

`GET /v1/models` returns a **built-in whitelist** defined in `codebuddy_direct_api.py`
(`KNOWN_CHAT_MODELS` / `KNOWN_IMAGE_MODELS`).

---

## Why a hard-coded whitelist

The upstream service exposes **no model listing endpoint**:

```
/v2/models              → 404 Route Not Found
/v2/plugin/models       → 404 Route Not Found
/v2/model/list          → 404 Route Not Found
/v1/models              → 404 Route Not Found
```

So the list has to be maintained by hand. The upside: the `model` field in a request is **passed through
verbatim**, so a correct id works even if it is not in the whitelist — the whitelist only affects what
`/v1/models` reports.

---

## Chat models (32)

**DeepSeek**

| id | Notes |
|---|---|
| `deepseek-v3` | default model |
| `deepseek-v3-0324` / `deepseek-v3-1` | version snapshots |
| `deepseek-v3-2-volc` | Volcengine channel |
| `deepseek-v3-0324-lkeap` / `deepseek-v3-1-lkeap` | without the reasoning chain |
| `deepseek-v4-flash` / `deepseek-v4-pro` | V4 family |
| `deepseek-r1` / `deepseek-r1-0528` | reasoning models |
| `deepseek-r1-0528-lkeap` | R1 without the reasoning chain |

**Zhipu GLM**

`glm-4.7`, `glm-5.0`, `glm-5.0-turbo`, `glm-5.1`, `glm-5.2`, `glm-5.3`, `glm-5.3-flash`, `glm-5v-turbo` (multimodal)

**Kimi**

`kimi-k2.5`, `kimi-k2.6`, `kimi-k2.7`, `kimi-k3-1`, `kimi-k3-2`

**Hunyuan / Tencent**

`hunyuan-chat`, `hunyuan-2.0-instruct`, `hunyuan-2.0-thinking`, `hy3`, `hy3-preview`, `hy3-preview-agent`, `hy4-preview`

**MiniMax**

`minimax-m2.7`

---

## Image models (3)

| id | Purpose |
|---|---|
| `hunyuan-image-v3.0` | text-to-image (default) |
| `hunyuan-image-v3.0-art` | text-to-image, artistic style |
| `hunyuan-image-v2.0-general-edit` | image-to-image / editing (default for `/v1/images/edits`) |

---

## How to test whether a model id works

Because `model` is passed through verbatim, just fire one request at it:

```bash
KEY=$(grep '^API_KEY=' .env | cut -d= -f2-)

curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"hi"}],"stream":false}' \
  | head -c 300
```

- A normal reply → the id works
- `{"detail":"Upstream API returned empty response"}` → the id does not work

### Batch probing

```bash
# edit the candidate list
vim tools/probe_models.py     # change CANDIDATES

# run it (defaults to http://127.0.0.1:8000, override with WB_BASE)
python tools/probe_models.py
```

It tries each candidate with 2-way concurrency (about 40 seconds for 30 candidates), prints the working and
non-working lists, and writes the result to `.build/probe_result.json`.

### Where candidate ids come from

The client (an Electron app) ships a model registry inside its resource bundle — just grep it:

```bash
# macOS
grep -a -o -E '[A-Za-z0-9._-]{0,12}glm-[0-9][A-Za-z0-9._-]{0,20}' \
  "/Applications/WorkBuddy.app/Contents/Resources/app.asar" | sort -u

# Windows
grep -a -o -E '[A-Za-z0-9._-]{0,12}glm-[0-9][A-Za-z0-9._-]{0,20}' \
  "C:/path/to/WorkBuddy/resources/app.asar" | sort -u
```

> That registry contains names from **all** providers (including OpenRouter and Cloudflare entries), so it is
> not proof that WorkBuddy supports them — always confirm with the probe script.

Naming is easy to get wrong. Real examples from our testing:

| Looks plausible, does not work | Actual id |
|---|---|
| `glm-5.3-fast`, `glm-5.3-highspeed`, `glm-5p3-flash`, `zai-glm-5.3-flash` | `glm-5.3-flash` |
| `glm-5`, `glm-5-turbo` | `glm-5.0` |
| `glm-4.5*`, `glm-4.6*`, `glm-4.7-flash*` | not available |

---

## Adding a new model to the whitelist

Edit `codebuddy_direct_api.py`:

```python
KNOWN_CHAT_MODELS = {
    ...
    "glm-5.3", "glm-5.3-flash",   # ← add here
}

# models that accept reasoning_effort must also be listed here
THINKING_CAPABLE_MODELS = {
    ...
    "glm-5.3", "glm-5.3-flash",
}
```

Then restart the service (locally) or run `python update.py` (containers).

---

## Free and billed models

`FREE_MODELS` marks models that consume no credits (`hy3-preview`, `hy4-preview`); `/v1/models` reports them
with `"free": true`.

To see what a specific request actually cost, look at the credits column in the dashboard request log — it
reads the real value returned by the upstream, so you never have to estimate.

---

## Request parameters

| Parameter | Values | Notes |
|---|---|---|
| `model` | see above | falls back to `DEFAULT_MODEL` |
| `reasoning_effort` | `low` / `medium` / `high` / `max` | reasoning depth; alias `thinking_level`; only some models support it |
| `stream` | `true` / `false` | defaults to `true` |
| `temperature` | `0` – `2` | out-of-range values are clamped |
| `max_tokens` | default 8192, max 32768 | values above the cap are truncated |
| `tools` / `tool_choice` | standard OpenAI format | tool calling is supported upstream |
