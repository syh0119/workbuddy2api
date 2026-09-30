# Changelog

本项目基于 [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API)。
下面是本仓库在它之上做的改动，倒序排列。

---

## v2.0 — 控制面板与密钥分发

### 新增

- **可视化控制台 `/admin`**（单文件、无外部依赖）
  - 积分概览：剩余 / 总量 / 已用，按资源包拆分，进度条
  - 用量统计：近 7/14/30/90 天，按日 / 按密钥 / 按模型 + 柱状图
  - 请求日志：时间、密钥、模型、状态码、耗时、tokens、消耗积分、来源 IP
- **API 密钥分发**：任意新建密钥，支持「不限 / 按次数 / 按积分 / 按 tokens」额度与有效期，服务端强校验
- `store.py`：SQLite 存储层（密钥、日志、积分快照、设置），WAL + 线程安全
- `billing.py`：上游积分查询，带缓存
- `admin_routes.py`：控制面板 API（登录会话、密钥 CRUD、用量、日志、积分刷新）
- `update.py` / `update.cmd` / `update_casaos.sh`：一键打包 + 推送 + 验证
- `tools/get_token.py`：跨平台 token 提取助手（自动识别明文 / 加密存储）
- `tools/probe_models.py`：批量探测模型 id 可用性
- 完整文档：`docs/` 下的 8 篇教程 + `SECURITY.md`

### 改动

- **修复 `python server.py` 不读 `.env`**：原来只有 `start.sh` / Docker 才注入环境变量，
  照文档 `cp .env.example .env` 之后直接 `python server.py` 会带着空 token 启动（无鉴权、调不通）。
  现在 `server.py` 启动时自动加载同目录 `.env`，已存在的环境变量优先，不会被覆盖
- **修复默认数据库路径**：无 `ADMIN_DB` 时原来硬编码 `/data/admin.db`，
  非容器环境会写到系统根目录（Windows 上创建 `D:\data\`、Linux 上可能权限不足）。
  改为默认落在项目目录，容器部署仍由 Dockerfile / compose 指定 `/data/admin.db`
- **修复本地/局域网被系统代理拦死**：`update.py` 与 `casaos/deploy_casaos.py` 现在默认绕过
  `http_proxy`（用 `ProxyHandler({})`），否则 `verify` 检查本地地址、连内网 CasaOS 都会 502；
  需要走代理时设 `WB_USE_SYSTEM_PROXY=1`
- **修复 Dockerfile**：原来只 `COPY` 了 `server.py` 和 `codebuddy_direct_api.py`，
  漏掉 `store.py` / `admin_routes.py` / `billing.py` / `static/`，构建出的镜像一启动就 ImportError；
  同时补上 `/data` 卷与 `ADMIN_DB` / `CODEBUDDY_TOKEN_CACHE` 默认值
- `_parse_sse_stream` 现在会返回上游 `usage`（含 `credit` 真实消耗），用于精确记账
- 新增 `CODEBUDDY_VERBOSE_STREAM`（默认关）：不再把模型输出刷进容器日志
- **修复并发串包**：`ApiClient` 原来共用一条 HTTP 长连接，uvicorn 线程池并发调用时会互相干扰
  （`CannotSendRequest` / `'NoneType' object has no attribute 'read'`），现改为 `threading.local()` 按线程隔离
- `find_and_load_token` 支持从环境变量读取 token，并新增刷新后落盘（容器重启不失效）
- `server.py` 的 base_url 可配（`CODEBUDDY_API_BASE`）
- 模型白名单补充：`glm-5.3`、`glm-5.3-flash`、`kimi-k3-2`（共 35 个）

### 文档

- README 重写为完整的开源说明 + 教程索引
- 新增 CasaOS 应用管理 API 的逆向笔记

---

## v1.x — 上游版本

接口层（`codebuddy_direct_api.py` 的上游协议、模型清单、反封号策略、`server.py` 的 OpenAI 兼容端点）
来自 [Tom6814/WorkBuddy2API](https://github.com/Tom6814/WorkBuddy2API)，详见上游仓库。
