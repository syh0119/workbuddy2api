# WorkBuddy2API · 带控制面板的 OpenAI 兼容网关

[![CI](https://github.com/syh0119/workbuddy2api/actions/workflows/ci.yml/badge.svg)](https://github.com/syh0119/workbuddy2api/actions/workflows/ci.yml)

把 **WorkBuddy 桌面端内置的模型**（DeepSeek / Kimi / GLM / 混元 / MiniMax …）包装成标准 **OpenAI 兼容 API**，
并附带一个**可视化控制台**：查看积分余额与消耗、创建分发密钥、给每个密钥单独设额度。

> [English](README.en.md)｜本项目基于 [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API) 二次开发

```
┌──────────────┐   OpenAI 协议   ┌─────────────────────┐   WorkBuddy 私有协议   ┌──────────────────┐
│  任意客户端   │ ──────────────▶ │  本项目 (FastAPI)    │ ────────────────────▶ │ copilot.tencent  │
│ Cherry/Cursor │ ◀────────────── │ 鉴权·额度·记账·面板   │ ◀──────────────────── │  .com （上游）    │
│  SDK / 脚本   │   SSE 流式      │ SQLite / admin.html │                       └──────────────────┘
└──────────────┘                 └─────────┬───────────┘
                                           │ 积分查询
                                           ▼
                                 /billing/meter/get-user-resource-summary
```

---

## 特性

**接口层**

- OpenAI 完全兼容：`/v1/chat/completions`、`/v1/models`、`/v1/images/generations`、`/v1/images/edits`
- `reasoning_content` 思考链透传，支持 `reasoning_effort`（low / medium / high / max）
- tools / tool_calls 透传
- SSE 流式
- Token 过期自动刷新（refresh token 轮换会落盘，容器重启不失效）
- 连接按线程隔离，支持并发请求
- 反向代理友好：`X-Accel-Buffering: no`、CORS 全开

**控制面板（`/admin`）**

| 模块 | 能力 |
|---|---|
| 积分概览 | 剩余 / 总量 / 已用 credits，按资源包拆分，可手动刷新 |
| 用量统计 | 近 7/14/30/90 天，按日 / 按密钥 / 按模型，柱状图 |
| 请求日志 | 时间、密钥、模型、状态码、耗时、tokens、消耗积分、来源 IP |
| 密钥分发 | 一键生成新 Key，只完整显示一次 |
| 额度控制 | 不限 / 按次数 / 按积分 / 按 tokens，可设有效期，**服务端强校验** |
| 密钥管理 | 启用、禁用、重置用量、重置 Key、删除 |

**部署**

- 本地三行命令起服务；Dockerfile / docker-compose 开箱可用
- 针对 **CasaOS** 提供 API 自动化部署脚本（不用登 Web UI、不用 SSH）
- 一键更新脚本：改完代码 `python update.py` 打包 + 推送 + 自动验证

**质量保障**

- `tools/ci_checks.py` —— 一个脚本覆盖语法、结构、敏感信息、Dockerfile 引用、YAML、文档链接
- GitHub Actions 在 Python 3.10~3.13 上跑同一套检查，并真实启动服务、构建并冒烟测试 Docker 镜像

---

## 快速开始

```bash
git clone https://github.com/<you>/workbuddy2api.git
cd workbuddy2api

cp .env.example .env
python tools/get_token.py --write     # 自动读本地登录态；失败会给出抓包步骤
# 编辑 .env：填 API_KEY 和 ADMIN_PASSWORD

pip install fastapi uvicorn
python server.py
```

然后打开：

- 控制台 `http://127.0.0.1:8000/admin`
- API 接口 `http://127.0.0.1:8000/v1`

详细步骤见 **[docs/01-快速开始.md](docs/01-快速开始.md)**。

---

## 文档

| 文档 | 内容 |
|---|---|
| [docs/01-快速开始.md](docs/01-快速开始.md) | 5 分钟跑起来 |
| [docs/02-获取Token.md](docs/02-获取Token.md) | 登录态怎么拿（含新版加密存储的应对） |
| [docs/03-Docker部署.md](docs/03-Docker部署.md) | Docker / docker-compose / 云平台 |
| [docs/04-CasaOS部署.md](docs/04-CasaOS部署.md) | 部署到自己的 CasaOS（含 API 自动化） |
| [docs/05-控制面板.md](docs/05-控制面板.md) | 面板各项功能与额度语义 |
| [docs/06-模型与探测.md](docs/06-模型与探测.md) | 模型清单、新模型 id 怎么试出来 |
| [docs/07-常见问题.md](docs/07-常见问题.md) | 报错对照、并发、流式、限速 |
| [docs/使用指南.md](docs/使用指南.md) | 各个客户端怎么填（Cherry / Cursor / Dify / SDK…） |
| [docs/CasaOS部署笔记.md](docs/CasaOS部署笔记.md) | CasaOS 应用管理 API 的逆向笔记 |
| [SECURITY.md](SECURITY.md) | **放公网前必读** |
| [CHANGELOG.md](CHANGELOG.md) | 本仓库相对上游改了什么 |

🌐 **英文文档**（完整镜像）：[`docs/en/`](docs/en/) —— 从 [docs/en/01-quickstart.md](docs/en/01-quickstart.md) 开始。

---

## 配置项

全部通过 `.env` 注入，完整列表见 [.env.example](.env.example)。最常改的几个：

| 变量 | 说明 |
|---|---|
| `CODEBUDDY_AUTH_TOKEN` | **必填**，WorkBuddy 的 access token |
| `CODEBUDDY_REFRESH_TOKEN` | 强烈建议填，否则 token 过期要手动换 |
| `API_KEY` | 主密钥，客户端用它鉴权；无额度限制 |
| `ADMIN_PASSWORD` | 控制面板登录密码 |
| `DEFAULT_MODEL` | 客户端不传 model 时的默认值 |
| `CODEBUDDY_API_BASE` | 上游地址，默认 `https://copilot.tencent.com` |
| `CODEBUDDY_BILLING_BASE` | 积分查询地址，默认 `https://www.workbuddy.cn`（**注意不带 `/v2`**） |

---

## 数据与持久化

| 位置 | 内容 |
|---|---|
| `.env` | 凭证与配置（**已被 .gitignore 排除**） |
| `admin.db`（容器内 `/data/admin.db`） | 密钥、请求日志、积分快照 |
| `/data/token.json`（容器内） | 刷新后的 token 缓存 |

升级代码不会清空这些数据。

---

## 更新

```bash
python update.py          # 重新打包 + 推送 + 验证
python update.py env      # 只改了 .env
python update.py verify   # 只检查线上状态
python update.py logs     # 看容器日志
```

Windows 可双击 `update.cmd`，Git Bash 用 `bash update_casaos.sh`。

---

## 模型

内置白名单共 35 个（32 个对话 + 3 个图片），清单见 [docs/06-模型与探测.md](docs/06-模型与探测.md)。

上游**不提供模型列表接口**，所以 `model` 字段是原样透传的 —— 想试某个新模型能不能用，直接拿 id 打一发即可：

```bash
curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"hi"}]}'
```

返回 `Upstream API returned empty response` 就是该 id 不可用。

---

## 安全须知（务必读）

- `.env` 里的 `CODEBUDDY_AUTH_TOKEN` **等同于你 WorkBuddy 账号的登录态**，泄露 = 账号被白嫖。不要提交、不要截图、不要发给别人。
- 控制面板和 API 默认是**明文 HTTP**。放公网前请至少：改掉 `ADMIN_PASSWORD`、在反向代理（Nginx / Lucky / Caddy）上挂 HTTPS。
- 分发密钥时优先用「按积分 / 按次数」额度，方便随时掐断。
- 详见 [SECURITY.md](SECURITY.md)。

---

## 免责声明

本项目仅供**个人学习与自用**，用于把自己账号已授权的模型接入自己常用的工具。

- 请遵守 WorkBuddy / CodeBuddy 的服务条款，不要用于商业转售、批量刷量或任何滥用行为。
- 不要公开分享自己的 token，也不要把它部署成对公众开放的服务。
- 因使用本项目导致的账号风险、封禁、数据丢失等后果，由使用者自行承担。

---

## 致谢

- [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API) —— 上游项目（MIT）。
  本仓库的接口层实现（`codebuddy_direct_api.py` 的上游协议、模型清单、反封号策略）来自它，
  控制台的存储层、计费查询、面板 API 与部署工具为本仓库新增。

## License

[MIT](LICENSE)
