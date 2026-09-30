# 04 · 部署到 CasaOS

[CasaOS](https://casaos.io/) 的「安装自定义应用」只接受现成镜像、**不支持 `build:`**。
所以这里有两种做法：

- **A. 手工粘贴 compose**（通用，3 分钟）
- **B. 用脚本走 CasaOS API 自动部署**（不用登 Web UI、不用 SSH，可脚本化）

---

## 准备

```bash
cp .env.example ../../.env                   # 项目根目录的 .env
python tools/get_token.py --write             # 填 token
# 再编辑 .env 补上 API_KEY / ADMIN_PASSWORD
```

CasaOS 上创建一个数据目录（CasaOS 默认根是 `/DATA`，容器里映射成 `/data`）：

```
/DATA/AppData/workbuddy2api
```

---

## 方式 A：在 CasaOS 里粘贴 compose

CasaOS → 左上角 `+` → **安装自定义应用** → 切到 YAML/粘贴模式，把下面这段贴进去：

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
      WB_PAYLOAD: "<把 .build/wb_payload.b64 的内容粘这里>"
      TZ: "Asia/Shanghai"
      ADMIN_DB: "/data/admin.db"
      ADMIN_PASSWORD: "<面板密码>"
      CODEBUDDY_TOKEN_CACHE: "/data/token.json"
      CODEBUDDY_AUTH_TOKEN: "<access token>"
      CODEBUDDY_REFRESH_TOKEN: "<refresh token>"
      CODEBUDDY_API_BASE: "https://copilot.tencent.com"
      CODEBUDDY_BILLING_BASE: "https://www.workbuddy.cn"
      API_KEY: "<主密钥>"
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

`WB_PAYLOAD` 是**把整个业务代码打包成 base64 塞进环境变量**，这样容器不依赖外部下载：

```bash
python update.py rebuild      # 只打包不推送，会生成 .build/wb_payload.b64
```

把生成的内容粘到 `WB_PAYLOAD:` 后面（很长，一行就行）。

> 为什么不用 `curl` 在容器里拉代码？因为 `python:*-slim` 镜像里**没有 curl，也没有 wget**。

---

## 方式 B：走 CasaOS API 自动部署（推荐）

不用登录 Web UI，直接调 CasaOS 的应用管理接口。

### 1. 填凭据

```bash
cp casaos/casaos.env.example casaos/casaos.env
```

编辑 `casaos/casaos.env`：

```ini
CASAOS_BASE=http://192.168.1.10:80     # 你的 CasaOS 地址（默认 80 端口）
CASAOS_USER=你的CasaOS用户名
CASAOS_PWD=你的CasaOS密码
```

### 2. 部署

```bash
python update.py            # 打包 + 推送 + 验证
```

或者用底层脚本单独控制：

```bash
cd casaos
python deploy_casaos.py dry       8000   # 只校验 compose YAML
python deploy_casaos.py real      8000   # 首次安装
python deploy_casaos.py update    8000   # 已存在时热更新
python deploy_casaos.py logs      8000   # 看日志
python deploy_casaos.py uninstall 8000   # 卸载
```

---

## 关于 CasaOS 应用管理 API（踩坑记录）

这是逆向出来的调用约定，`casaos/deploy_casaos.py` 已实现：

```
POST /v2/app_management/compose?check_port_conflict=false&uncontrolled=true
Authorization: <裸 access_token>          ← 注意不加 "Bearer "
Content-Type: application/yaml

<纯 YAML 文本，直接当 body>
```

几个容易踩的点：

| 现象 | 原因 |
|---|---|
| `500 main service not been specified` | body 不是合法 YAML（比如误用 JSON 传） |
| `400 there are ports in use` | 端口被占；`dry_run` 也会做端口检查 |
| `409 is already being installed` | 上一次异步安装还没结束，等 1~3 分钟 |
| 装完应用不出现 | 自定义应用必须带 `uncontrolled=true` |
| `yaml: line N: mapping values are not allowed` | 用了 `curl -d`（会转成 urlencoded），要用 `--data-binary` |

登录与查询：

```
POST /v1/users/login                      → data.token.access_token
GET  /v2/app_management/compose            → 应用列表
GET  /v2/app_management/compose/{id}/logs  → 容器日志
```

更多细节见 [CasaOS部署笔记.md](CasaOS部署笔记.md)。

---

## 外网访问

CasaOS 上通常还装了 **Lucky**（反代 / 证书工具）。给它加一条规则就能上 HTTPS：

1. SSL 证书：ACME 签 `api.example.com`（80/443 不通时用 DNS 验证）
2. Web 服务：监听 443、前端域名 + 证书、后端 `127.0.0.1:8000`
3. 记得在服务器防火墙 / 云安全组放行 443

> Lucky 用 `network_mode: host` 时，回环地址就能直接打到宿主端口。

---

## 更新与排错

```bash
python update.py            # 改过代码
python update.py env        # 只改了 .env
python update.py verify     # 只检查线上状态
python update.py logs       # 看容器日志
```

Windows 双击 `update.cmd` 也行。

数据都在 `/DATA/AppData/workbuddy2api/`（`admin.db` 存密钥与日志、`token.json` 存刷新后的 token），
升级代码不会丢。
