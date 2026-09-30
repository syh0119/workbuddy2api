# 03 · Docker 部署

[English](en/03-docker.md) | 中文

适合让局域网内其他设备、或公网设备访问。

## 方式一：docker compose（推荐本机/自有服务器）

```bash
git clone https://github.com/<you>/workbuddy2api.git
cd workbuddy2api

cp .env.example .env
# 编辑 .env：填 CODEBUDDY_AUTH_TOKEN / API_KEY / ADMIN_PASSWORD
# 关键：把 ADMIN_DB 和 token 缓存指到卷里，容器重建也不丢数据
```

编辑 `docker-compose.yml`，确认挂载了数据卷：

```yaml
services:
  workbuddy2api:
    build: .
    image: workbuddy2api:latest
    container_name: workbuddy2api
    restart: unless-stopped
    env_file: [.env]
    environment:
      ADMIN_DB: /data/admin.db
      CODEBUDDY_TOKEN_CACHE: /data/token.json
    ports:
      - "8000:8080"
    volumes:
      - ./data:/data          # 密钥、日志、token 缓存都在这
```

启动：

```bash
docker compose up -d --build
docker compose logs -f
```

验证：

```bash
curl http://127.0.0.1:8000/health
```

> 容器里监听的是 **8080**，映射到宿主的 8000（改左侧数字换宿主端口）。

---

## 方式二：直接 docker run

```bash
docker build -t workbuddy2api .

docker run -d --name workbuddy2api \
  --restart unless-stopped \
  --env-file .env \
  -e ADMIN_DB=/data/admin.db \
  -e CODEBUDDY_TOKEN_CACHE=/data/token.json \
  -v "$PWD/data:/data" \
  -p 8000:8080 \
  workbuddy2api
```

---

## 方式三：云平台 / PaaS

Dockerfile 是标准写法，可以直接丢给支持 Docker 的平台（Zeabur、Railway、Fly.io、群晖、TrueNAS…）。

注意两点：

1. **必须配持久卷**挂到 `/data`，否则容器一重建，密钥和日志就没了。
2. **环境变量**不要写在 Dockerfile 里，用平台的环境变量面板注入（`.env` 别提交）。

---

## 让外网能访问，怎么安全一点

直接暴露 `http://公网IP:8000` 能跑，但不加密。建议加一层反向代理：

**Nginx**

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        # 流式输出必需
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

**Caddy**（自动申请证书，更省事）

```
api.example.com {
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1
    }
}
```

**Lucky**（国内常见的可视化反代工具）

1. SSL 证书：新增 ACME 证书，域名填 `api.example.com`。
   80/443 不通时用 DNS 方式验证（需要域名商支持 DNS API）。
2. Web 服务：监听 443、前端域名 + HTTPS 证书、后端填 `127.0.0.1:8000`（host 网络下回环直达）。

### 前置条件

- 云服务器：安全组放行 443
- 家宽 + IPv6：只需放行服务器 `ip6tables`（IPv6 没有 NAT）
- 有些地区宽带会封 80/443，那就换非标端口 + DNS-01 签证书

---

## 只想让局域网用

1. 服务器 IP：`ipconfig`（Windows）/ `ip addr`（Linux）拿到内网地址，比如 `192.168.1.10`
2. 放行端口（Windows）：管理员运行 `enable_lan.ps1`
3. 其他设备填 `http://192.168.1.10:8000/v1`

`.env` 里也可以设 `PUBLIC_BASE=http://192.168.1.10:8000`，这样 `update.py verify` 会检查这个地址。

---

## 升级

```bash
git pull
docker compose up -d --build
```

数据在 `./data`，不会丢。
