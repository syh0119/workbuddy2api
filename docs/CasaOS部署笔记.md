# CasaOS 应用管理 API 笔记

部署脚本 `casaos/deploy_casaos.py` 用的就是这套接口。适用于 CasaOS 0.4.x（实测 0.4.15）。

**不需要 SSH，只要 Web UI 的账号密码。**

---

## 登录

```http
POST {BASE}/v1/users/login
Content-Type: application/json

{"username":"<用户名>","password":"<密码>"}
```

从响应里取 `data.token.access_token`。

---

## 关键：Authorization 放裸 token

```http
Authorization: <access_token>
```

**不加 `Bearer ` 前缀**。加了会 401 —— 这点和绝大多数 API 不一样。

---

## 应用管理接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v2/app_management/compose` | 应用列表（`data` 是 map，key = 应用名） |
| GET | `/v2/app_management/compose/{id}` | 详情，含 `status`（running / restarting…） |
| GET | `/v2/app_management/compose/{id}/logs?lines=N` | 容器日志 |
| GET | `/v2/app_management/compose/{id}/containers` | 容器状态 |
| POST | `/v2/app_management/compose` | **安装** |
| PUT | `/v2/app_management/compose/{id}` | **热更新**（改 compose，无需卸载） |
| DELETE | `/v2/app_management/compose/{id}?delete_config_folder=true` | 卸载 |
| PUT | `/v2/app_management/compose/{id}/status` | body `{"status":"restart"}` |

### 安装 / 更新的请求体

```http
POST {BASE}/v2/app_management/compose?check_port_conflict=false&uncontrolled=true
Authorization: <裸 access_token>
Content-Type: application/yaml

<纯 YAML 文本，直接作为 body>
```

要点：

1. **body 是纯 YAML**，不是 JSON，也不是 `{"compose": ...}` 这种包装。
2. `Content-Type` 必须是 `application/yaml`。
3. 自定义应用**必须** `uncontrolled=true`，否则会被静默丢弃 / 卡在安装中。
4. `dry_run=true` 只校验不安装，但**仍会做端口冲突检查**（端口被占会返回 `there are ports in use`）。
5. 返回 `{"message":"compose app is being installed asynchronously"}` → **异步**，要轮询详情和日志，别立刻判定失败。
6. `curl` 用 `--data-binary @file`，不要用 `-d`（`-d` 会把 `Content-Type` 改成 urlencoded，导致 YAML 解析失败）。

### compose 的硬性要求

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
  main: myapp            # 必须与某个 service 名一致，否则报 main service not been specified
  port_map: "8000"
  scheme: http
  is_uncontrolled: true
  title: { en_us: MyApp, zh_cn: MyApp }
```

- **不支持 `build:`** —— CasaOS 只 pull 镜像，不能从源码构建。
- `x-casaos.main` + `port_map` 决定首页图标点开后跳到哪。

---

## 怎么逆向出来的

CasaOS 前端是 Vue + webpack 打包的，可以直接从前端产物里找线索：

```bash
# 1. 首页引用了哪些 js
curl -s http://<casaos>/ | grep -oE '/[^"]+\.js'

# 2. 主包里搜 API 定义
curl -s http://<casaos>/app.<hash>.js -o app.js
grep -o 'PREFIX2COMPOSE[^;]*' app.js
# → installV2(data, config) { api.post(PREFIX2COMPOSE, data, config) }

# 3. 懒加载 chunk 里有真实调用
curl -s http://<casaos>/src_views_Home_vue.<hash>.js | grep -o 'installComposeApp([^)]*)'

# 4. OpenAPI 客户端在 vendor chunk 里，能查到参数与 Content-Type
curl -s http://<casaos>/vendors-node_modules_pnpm_*.js -o vendor.js
grep -o "content-type[^']*" vendor.js
```

从 vendor chunk 里能直接读到 `BASE_PATH = "/v2/app_management"` 和
`localVarHeaderParameter['Content-Type'] = 'application/yaml'`，就不用猜了。

---

## 排错对照

| 现象 | 原因 |
|---|---|
| `500 main service not been specified` | body 不是合法 YAML（比如误用 JSON 传） |
| `400 there are ports in use` | 端口被占；`dry_run` 也会检查 |
| `409 is already being installed` | 上一次异步安装还没结束，等 1~3 分钟 |
| `yaml: line N: mapping values are not allowed` | body 被错误编码（`-d` 而不是 `--data-binary`），换行被吞 |
| 装完应用列表里没有 | 没加 `uncontrolled=true` |
| 容器一直 `restarting` | 看 `logs`：多为命令报错、缺依赖 |

---

## 顺便记一个坑

如果本地设了 `http_proxy`，`curl` 会走代理。代理连不上上游时会返回 **502 + 本机本地化的错误文本**
（Windows 上是 `由于目标计算机积极拒绝，无法连接。 (os error 10061)`），很容易误判成服务端故障。

判断方法：

```bash
curl -s -o /dev/null -w '%{remote_ip}\n' http://你的地址/health
```

显示 `127.0.0.1` 就说明走了本地代理。测试时加 `--noproxy '*'`。
