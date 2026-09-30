# 02 · 获取 Token

服务只需要两样东西：**access token**（必须）和 **refresh token**（强烈建议）。

| token | 作用 | 有效期（参考） |
|---|---|---|
| `CODEBUDDY_AUTH_TOKEN` | 调 API 时的身份凭证 | 约 30 天 |
| `CODEBUDDY_REFRESH_TOKEN` | 过期后自动换新 | 约 60 天 |

有了 refresh token，服务会在 access token 快过期时自动刷新，**不需要你干预**。

---

## 方法一：直接读本地登录态（最快）

WorkBuddy 桌面端登录后，会把认证信息写进本地用户数据目录。

```bash
python tools/get_token.py
```

脚本会按平台依次尝试这些路径：

| 平台 | 路径 |
|---|---|
| Windows | `%APPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| Windows | `%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info` |
| macOS | `~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info` |
| Linux | `~/.config/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info` |

读到明文就加 `--write` 直接写进 `.env`：

```bash
python tools/get_token.py --write
```

### 如果提示「token 已被加密存储」

WorkBuddy 5.6.2 起，auth 文件里的 `accessToken` / `refreshToken` 变成了这样的信封：

```json
{
  "accessToken": {
    "$wbEncrypted": 1,
    "envelope": "eyJzdWl0ZSI6MSwia2V5SWQiOiI..."
  }
}
```

解密用的密钥（`atRestSecretKey`）只存在于**运行中的客户端进程内存**里，不落盘。
所以直接读文件拿不到明文，请用下面的方法二。

> 本仓库**不提供**解密实现，避免引入来路不明的代码。方法二更通用也更安全。

---

## 方法二：开发者工具抓包（通用，推荐）

只要客户端能跑，这个方法在所有版本上都有效。

1. 打开 WorkBuddy 桌面端，确认已登录
2. 按 `F12` 打开开发者工具 → 切到 **Network（网络）** 面板
3. 保持面板打开，在客户端里**随便发一条消息**（比如"你好"）
4. 在请求列表里找到发往 `copilot.tencent.com` 的请求（通常是 `v2/chat/completions`）
5. 点开 → **Headers** → 找到：

   ```
   Authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6...
   ```

   `Bearer ` 后面那一整串就是 **access token**。

6. 找 **refresh token**：在同一个 Network 面板里搜索 `refresh`，
   找 `v2/plugin/auth/token/refresh` 的**响应**，里面有 `refreshToken` 字段。
   找不到也没关系 —— 只是 access token 过期后需要你手动再抓一次。

7. 写进 `.env`：

   ```bash
   python tools/get_token.py --access <access> --refresh <refresh> --write
   ```

   或者手动编辑 `.env`：

   ```ini
   CODEBUDDY_AUTH_TOKEN=eyJhbGciOi...
   CODEBUDDY_REFRESH_TOKEN=eyJhbGciOi...
   CODEBUDDY_DOMAIN=www.workbuddy.cn
   ```

> 部分客户端的开发者工具默认被禁用。Windows 上如果 F12 没反应，可以试试 `Ctrl+Shift+I`，
> 或者用系统的代理抓包工具（Charles / Fiddler / mitmproxy）抓同一个请求。

---

## 方法三：老版本的明文 auth 文件

如果你的客户端版本较老、auth 文件里是明文字符串，可以一行命令取出来。

**macOS / Linux**

```bash
python3 -c "import json,os;d=json.load(open(os.path.expanduser('~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info')));print(d['auth']['accessToken'])"
```

**Windows PowerShell**

```powershell
((Get-Content "$env:LOCALAPPDATA\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info" -Raw | ConvertFrom-Json).auth.accessToken)
```

---

## 校验 token 是否可用

```bash
TOKEN=$(grep '^CODEBUDDY_AUTH_TOKEN=' .env | cut -d= -f2-)

curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST https://copilot.tencent.com/v2/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'X-Product: SaaS' \
  -d '{"model":"deepseek-v3","messages":[{"role":"user","content":"hi"}],"stream":true}'
```

返回 `200` 就是有效。

---

## 安全提醒

- token **等同于你的账号登录态**。不要提交进 git（`.env` 默认已被 `.gitignore` 排除），不要发群里，不要截图带出来。
- 如果怀疑泄露：去 WorkBuddy 客户端退出登录并重新登录，旧 token 会失效，然后更新 `.env`。
- 用 `git status` 确认 `.env` 没有出现在待提交列表里。
