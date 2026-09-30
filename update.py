# -*- coding: utf-8 -*-
"""一键更新 CasaOS 上的 workbuddy2api。

用法（在本目录下执行）：
    python update.py            # 重新打包代码 + 推送 + 验证
    python update.py env        # 只推送（改了 .env，比如换 token / 换面板密码）
    python update.py verify     # 只检查线上状态
    python update.py logs       # 看容器日志
"""
from __future__ import annotations

import base64
import io
import os
import sys
import tarfile
import time
import urllib.request

# 默认绕过系统代理（http_proxy），否则本地/局域网地址会被代理拦成 502
# 需要走代理时设 WB_USE_SYSTEM_PROXY=1
if os.environ.get("WB_USE_SYSTEM_PROXY") != "1":
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
    )

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, ".build")
PAYLOAD = os.path.join(BUILD, "wb_payload.b64")

# 需要打进容器镜像的业务文件（相对项目根）
RUNTIME_FILES = [
    "server.py",
    "codebuddy_direct_api.py",
    "store.py",
    "admin_routes.py",
    "billing.py",
    "static/admin.html",
]

# 线上地址：优先环境变量 WB_PUBLIC_BASE，其次 .env 里的 PUBLIC_BASE
PUBLIC_BASE = os.environ.get("WB_PUBLIC_BASE", "")


def load_env() -> dict:
    env = {}
    for line in open(os.path.join(HERE, ".env"), encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def build_payload() -> None:
    os.makedirs(BUILD, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for rel in RUNTIME_FILES:
            path = os.path.join(HERE, rel.replace("/", os.sep))
            if not os.path.isfile(path):
                raise SystemExit("缺少文件: %s" % rel)
            t.add(path, arcname=rel)
    raw = buf.getvalue()
    with open(PAYLOAD, "w", encoding="utf-8") as f:
        f.write(base64.b64encode(raw).decode())
    print("[1/3] 代码包已生成  %.1f KB -> %s" % (len(raw) / 1024, os.path.relpath(PAYLOAD, HERE)))


def push() -> None:
    sys.path.insert(0, os.path.join(HERE, "casaos"))
    argv = sys.argv
    sys.argv = ["deploy_casaos.py", "update", os.environ.get("WB_PORT", "8000")]
    try:
        import deploy_casaos
        deploy_casaos.main()
    finally:
        sys.argv = argv


def http(url: str, timeout: int = 15, headers: dict | None = None) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def verify(env: dict) -> int:
    key = env.get("API_KEY", "")
    bad = 0
    for name, url, hdr in [
        ("健康检查", PUBLIC_BASE + "/health", None),
        ("模型列表", PUBLIC_BASE + "/v1/models", {"Authorization": "Bearer " + key}),
        ("控制面板", PUBLIC_BASE + "/admin", None),
    ]:
        st, body = http(url, headers=hdr)
        ok = st == 200
        extra = ""
        if name == "模型列表" and ok:
            import json
            try:
                extra = "  （%d 个模型）" % len(json.loads(body)["data"])
            except Exception:
                pass
        print("  %s %-8s %s%s" % ("✓" if ok else "✗", name, st or "连接失败", extra))
        bad += 0 if ok else 1
    return bad


def main() -> None:
    global PUBLIC_BASE
    mode = (sys.argv[1] if len(sys.argv) > 1 else "full").lower()
    env = load_env()
    PUBLIC_BASE = (PUBLIC_BASE or env.get("PUBLIC_BASE") or "http://127.0.0.1:8000").rstrip("/")

    if mode in ("full", "rebuild"):
        build_payload()
    elif mode not in ("env", "verify", "logs"):
        print(__doc__)
        return

    if mode in ("full", "rebuild", "env"):
        print("[2/3] 推送到 CasaOS …")
        push()
        wait = int(os.environ.get("WB_WAIT", "70"))
        print("[3/3] 等待 %ds 让容器重建 …" % wait)
        time.sleep(wait)
    elif mode == "logs":
        push_logs = False
        sys.path.insert(0, os.path.join(HERE, "casaos"))
        argv, sys.argv = sys.argv, ["deploy_casaos.py", "logs", "8000"]
        try:
            import deploy_casaos
            deploy_casaos.main()
        finally:
            sys.argv = argv
        return

    print("\n线上验证：")
    bad = verify(env)
    if bad:
        print("\n⚠ 有 %d 项不通过。先看日志： python update.py logs" % bad)
    else:
        print("\n完成。控制面板： %s/admin" % PUBLIC_BASE.rstrip("/"))


if __name__ == "__main__":
    main()
