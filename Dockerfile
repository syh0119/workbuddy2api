FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PORT=8080 \
    ADMIN_DB=/data/admin.db \
    CODEBUDDY_TOKEN_CACHE=/data/token.json

# 国内源优先，失败回退官方源
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn \
    || pip install --no-cache-dir fastapi uvicorn

# 应用代码（.dockerignore 已排除 .env / .git / *.md / __pycache__）
COPY codebuddy_direct_api.py server.py store.py billing.py admin_routes.py ./
COPY static/ ./static/

# 密钥库、请求日志、token 缓存都放这里；务必挂载卷，否则容器重建会丢
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port ${PORT} --log-level info"]
