# 03 · Docker Deployment

English | [中文](../03-Docker部署.md)

Use this when you want other devices to reach the API — either on your LAN or over the internet.

## Option 1 — docker compose (recommended)

```bash
git clone https://github.com/syh0119/workbuddy2api.git
cd workbuddy2api

cp .env.example .env
# edit .env: CODEBUDDY_AUTH_TOKEN / API_KEY / ADMIN_PASSWORD
```

Make sure `docker-compose.yml` mounts a data volume, otherwise keys and logs disappear when the
container is recreated:

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
      - ./data:/data          # keys, request logs and the token cache live here
```

Start it:

```bash
docker compose up -d --build
docker compose logs -f
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

> The container listens on **8080**; the left-hand side of the port mapping is the host port.

---

## Option 2 — plain docker run

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

## Option 3 — cloud / PaaS

The Dockerfile is standard, so it drops into anything that builds Docker images (Zeabur, Railway, Fly.io,
Synology, TrueNAS, …). Two things to get right:

1. **Attach a persistent volume** to `/data`, otherwise every redeploy wipes your keys and logs.
2. **Inject environment variables** through the platform's secret manager — never bake them into the image.

---

## Exposing it to the internet, safely

`http://<public-ip>:8000` works, but it is unencrypted. Put a reverse proxy in front of it.

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

        # required for streaming
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

**Caddy** (automatic certificates, less config)

```
api.example.com {
    reverse_proxy 127.0.0.1:8000 {
        flush_interval -1
    }
}
```

**Lucky** (popular GUI reverse proxy in China)

1. SSL certificates: create an ACME certificate for `api.example.com`. If ports 80/443 are not reachable,
   use DNS validation (your DNS provider needs an API).
2. Web service: listen on 443, frontend domain + HTTPS certificate, backend `127.0.0.1:8000`
   (with `network_mode: host` a loopback address reaches the host directly).

### Prerequisites

- Cloud VM: open 443 in the security group
- Home broadband + IPv6: only the server's `ip6tables` matters (IPv6 has no NAT)
- Some ISPs block inbound 80/443 — then use a non-standard port plus DNS-01 validation

---

## LAN-only setup

1. Find your host IP: `ipconfig` (Windows) / `ip addr` (Linux), e.g. `192.168.1.10`
2. Allow the port (Windows): run `enable_lan.ps1` as administrator
3. Other devices use `http://192.168.1.10:8000/v1`

You can also set `PUBLIC_BASE=http://192.168.1.10:8000` in `.env` so that `update.py verify` checks that address.

---

## Upgrading

```bash
git pull
docker compose up -d --build
```

Your data lives in `./data` and is untouched.
