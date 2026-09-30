# 02 · Getting the Token

English | [中文](../02-获取Token.md)

The service needs two things: an **access token** (required) and a **refresh token** (strongly recommended).

| Token | Purpose | Typical lifetime |
|---|---|---|
| `CODEBUDDY_AUTH_TOKEN` | Identity for calling the API | ~30 days |
| `CODEBUDDY_REFRESH_TOKEN` | Obtains a new access token when it expires | ~60 days |

With a refresh token the service renews itself automatically — **you never touch it again**.

---

## Method 1 — read the local login state (fastest)

After you sign in, the WorkBuddy desktop client writes its auth info into the user data directory.

```bash
python tools/get_token.py
```

The script tries these paths, in order:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| Windows | `%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| macOS | `~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info` |
| Linux | `~/.config/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info` |

If it finds plain-text values, add `--write` to save them straight into `.env`:

```bash
python tools/get_token.py --write
```

### If it says the token is "encrypted"

Starting with WorkBuddy 5.6.2 the `accessToken` / `refreshToken` fields in that file are wrapped in an envelope:

```json
{
  "accessToken": {
    "$wbEncrypted": 1,
    "envelope": "eyJzdWl0ZSI6MSwia2V5SWQiOiI..."
  }
}
```

The key that decrypts it (`atRestSecretKey`) lives **only in the memory of the running client process** and is
never written to disk. So reading the file cannot give you plain text — use Method 2.

> This repository deliberately ships **no** decryption implementation. Method 2 works on every version and
> does not require you to run third-party code with access to your credentials.

---

## Method 2 — capture it with DevTools (universal, recommended)

Works on every version, as long as the client runs.

1. Open the WorkBuddy desktop client and make sure you are signed in
2. Press `F12` → **Network** tab
3. Keep the panel open and **send any message** in the client (e.g. "hello")
4. Find the request to `copilot.tencent.com` (usually `v2/chat/completions`)
5. Open it → **Headers** → find:

   ```
   Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6...
   ```

   Everything after `Bearer ` is your **access token**.

6. For the **refresh token**: search the Network panel for `refresh`, then look at the **response** of
   `v2/plugin/auth/token/refresh` — it contains a `refreshToken` field.
   Don't worry if you can't find it; you will just have to repeat this step when the access token expires.

7. Store them:

   ```bash
   python tools/get_token.py --access <access> --refresh <refresh> --write
   ```

   Or edit `.env` by hand:

   ```ini
   CODEBUDDY_AUTH_TOKEN=eyJhbGciOi...
   CODEBUDDY_REFRESH_TOKEN=eyJhbGciOi...
   CODEBUDDY_DOMAIN=www.workbuddy.cn
   ```

> Some builds disable DevTools. If `F12` does nothing, try `Ctrl+Shift+I`, or capture the same request with a
> system proxy tool such as Charles, Fiddler or mitmproxy.

---

## Method 3 — plain-text auth file on older versions

If your client is older and stores the auth file as plain text, one command is enough.

**macOS / Linux**

```bash
python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info')));print(d['auth']['accessToken'])"
```

**Windows PowerShell**

```powershell
((Get-Content "$env:LOCALAPPDATA\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info" -Raw | ConvertFrom-Json).auth.accessToken)
```

---

## Verify the token actually works

```bash
TOKEN=$(grep '^CODEBUDDY_AUTH_TOKEN=' .env | cut -d= -f2-)

curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST https://copilot.tencent.com/v2/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'X-Product: SaaS' \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

`200` means it is valid.

---

## Security notes

- This token **is your account session**. Never commit it (`.env` is excluded by `.gitignore`), never paste it
  into a chat, never screenshot it.
- If you think it leaked: sign out and back in inside the WorkBuddy client — old tokens become invalid
  immediately — then update `.env`.
- Confirm it is not staged for commit with `git status`.
