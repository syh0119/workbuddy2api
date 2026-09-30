# -*- coding: utf-8 -*-
"""控制面板 API（挂在 FastAPI 上，路径前缀 /admin）。"""
from __future__ import annotations

import os
import secrets
import threading
import time

from fastapi import APIRouter, Body, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse

import billing
import store

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SESSION_TTL = float(os.environ.get("ADMIN_SESSION_TTL", str(12 * 3600)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

router = APIRouter()

_sessions: dict[str, float] = {}
_attempts: list[float] = []
_lock = threading.RLock()

_client_getter = lambda: None  # noqa: E731
_master_api_key = ""


def init(client_getter, master_api_key: str) -> None:
    global _client_getter, _master_api_key
    _client_getter = client_getter
    _master_api_key = master_api_key or ""
    if not ADMIN_PASSWORD:
        print("[!] 未设置 ADMIN_PASSWORD，控制面板无法登录", flush=True)
    store.init(master_api_key)


# ── 鉴权 ──────────────────────────────────────────────────────────────────
def _cleanup_sessions() -> None:
    now = time.time()
    for t in [k for k, exp in _sessions.items() if exp < now]:
        _sessions.pop(t, None)


def _is_admin(token: str) -> bool:
    if not token:
        return False
    if _master_api_key and secrets.compare_digest(token, _master_api_key):
        return True
    with _lock:
        _cleanup_sessions()
        exp = _sessions.get(token)
        if exp and exp > time.time():
            return True
    return False


def require_admin(authorization: str | None, x_admin_token: str | None) -> None:
    token = ""
    if x_admin_token:
        token = x_admin_token.strip()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    if not _is_admin(token):
        raise HTTPException(status_code=401, detail="未登录或会话已过期")


# ── 页面 ──────────────────────────────────────────────────────────────────
@router.get("/")
async def root():
    """根路径刻意返回 404。

    以前这里会 302 跳到 /admin，导致任何人（含扫描器）打开域名根路径都能看到
    一个登录页 —— 容易被判定为"未备案网站"。现在根路径什么都不给，
    面板请直接访问 /admin。
    """
    return Response(status_code=404)


@router.get("/admin")
async def admin_page():
    path = os.path.join(STATIC_DIR, "admin.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="admin.html not found")
    return FileResponse(path, media_type="text/html; charset=utf-8",
                        headers={"Cache-Control": "no-store"})


# ── 登录 ──────────────────────────────────────────────────────────────────
@router.post("/admin/api/login")
async def login(payload: dict = Body(...)):
    pwd = str(payload.get("password") or "")
    now = time.time()
    with _lock:
        _attempts[:] = [t for t in _attempts if now - t < 300]
        if len(_attempts) >= 10:
            raise HTTPException(status_code=429, detail="尝试过于频繁，请 5 分钟后再试")
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="服务端未设置 ADMIN_PASSWORD")
    if not secrets.compare_digest(pwd, ADMIN_PASSWORD):
        with _lock:
            _attempts.append(now)
        raise HTTPException(status_code=403, detail="密码错误")
    token = secrets.token_hex(24)
    with _lock:
        _sessions[token] = time.time() + SESSION_TTL
    return {"token": token, "expires_in": SESSION_TTL}


@router.post("/admin/api/logout")
async def logout(x_admin_token: str | None = Header(default=None)):
    with _lock:
        _sessions.pop(x_admin_token or "", None)
    return {"ok": True}


@router.get("/admin/api/me")
async def me(authorization: str | None = Header(default=None),
             x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {"ok": True, "upstream": _upstream_view()}


def _upstream_view() -> dict:
    try:
        from codebuddy_direct_api import ALL_SUPPORTED_MODELS, KNOWN_IMAGE_MODELS
        models = sorted(ALL_SUPPORTED_MODELS)
        images = sorted(KNOWN_IMAGE_MODELS)
    except Exception:
        models, images = [], []
    return {
        "api_base": os.environ.get("CODEBUDDY_API_BASE") or "https://copilot.tencent.com",
        "billing_base": billing.BILLING_BASE,
        "default_model": os.environ.get("DEFAULT_MODEL", "deepseek-v3"),
        "models": models,
        "image_models": images,
        "db": store.DB_PATH,
        "credit_refresh_sec": billing.REFRESH_SEC,
    }


# ── 概览 ──────────────────────────────────────────────────────────────────
def _token_getter():
    c = _client_getter()
    if c is None:
        raise RuntimeError("上游客户端未初始化")
    return c.token_info["access_token"]


@router.get("/admin/api/overview")
async def overview(force: int = 0, authorization: str | None = Header(default=None),
                   x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    data, err = billing.get_summary(_token_getter, force=bool(force))
    if data:
        store.add_credit_snapshot(data["total"], data["remain"], data["used"], data)
    snap = store.latest_credit()
    today_used = 0.0
    if snap:
        vs = store.usage_by_day(1)
        today_used = vs[-1]["credits"] if vs else 0.0
    return {
        "credits": data,
        "credits_error": err,
        "snapshot": snap and {"ts": snap["ts"], "remain": snap["remain"], "used": snap["used"]},
        "today": {"credits_from_log": round(today_used, 4)},
        "stats": store.stats(),
        "upstream": _upstream_view(),
        "server_time": time.time(),
    }


@router.get("/admin/api/credits/history")
async def credits_history(days: int = 7, authorization: str | None = Header(default=None),
                          x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {"days": days, "history": store.credit_history(days)}


# ── 密钥管理 ──────────────────────────────────────────────────────────────
@router.get("/admin/api/keys")
async def keys_list(authorization: str | None = Header(default=None),
                    x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {"keys": store.list_keys(include_secret=True)}


@router.post("/admin/api/keys")
async def keys_create(payload: dict = Body(...), authorization: str | None = Header(default=None),
                      x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    name = str(payload.get("name") or "").strip() or "未命名"
    qt = str(payload.get("quota_type") or "none")
    if qt not in ("none", "requests", "credits", "tokens"):
        raise HTTPException(status_code=400, detail="quota_type 仅支持 none/requests/credits/tokens")
    try:
        limit = float(payload.get("quota_limit") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="quota_limit 必须是数字")
    if qt != "none" and limit <= 0:
        raise HTTPException(status_code=400, detail="选择额度类型后必须填写大于 0 的额度")
    exp_in = payload.get("expires_in_days")
    expires_at = 0.0
    if exp_in:
        try:
            expires_at = time.time() + float(exp_in) * 86400
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="expires_in_days 必须是数字")
    elif payload.get("expires_at"):
        try:
            expires_at = float(payload["expires_at"])
        except (TypeError, ValueError):
            pass
    k = store.create_key(name, qt, limit, expires_at, str(payload.get("note") or ""))
    return {"key": k}


@router.patch("/admin/api/keys/{kid}")
async def keys_update(kid: int, payload: dict = Body(...),
                      authorization: str | None = Header(default=None),
                      x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    cur = store.get_key(kid)
    if not cur:
        raise HTTPException(status_code=404, detail="密钥不存在")
    fields = {k: v for k, v in payload.items() if k not in ("id", "key")}
    if cur["is_master"] and not (set(fields) <= {"quota_type", "quota_limit"}):
        fields = {k: v for k, v in fields.items() if k in ("quota_type", "quota_limit")}
    return {"key": store.update_key(kid, **fields)}


@router.delete("/admin/api/keys/{kid}")
async def keys_delete(kid: int, authorization: str | None = Header(default=None),
                      x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    if not store.delete_key(kid):
        raise HTTPException(status_code=400, detail="主密钥不可删除或密钥不存在")
    return {"ok": True}


@router.post("/admin/api/keys/{kid}/regenerate")
async def keys_regenerate(kid: int, authorization: str | None = Header(default=None),
                          x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    k = store.regenerate_key(kid)
    if not k:
        raise HTTPException(status_code=400, detail="主密钥不可重置或密钥不存在")
    return {"key": k}


@router.post("/admin/api/keys/{kid}/reset_usage")
async def keys_reset_usage(kid: int, payload: dict = Body(default={}),
                           authorization: str | None = Header(default=None),
                           x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    if not store.get_key(kid):
        raise HTTPException(status_code=404, detail="密钥不存在")
    store.reset_usage(kid, float((payload or {}).get("value") or 0))
    return {"key": store.get_key(kid)}


# ── 用量 ──────────────────────────────────────────────────────────────────
@router.get("/admin/api/usage")
async def usage(days: int = 7, key_id: int | None = None,
                authorization: str | None = Header(default=None),
                x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {
        "days": days,
        "by_day": store.usage_by_day(days),
        "by_key": store.usage_by_key(days),
        "by_model": store.usage_by_model(days),
    }


@router.get("/admin/api/logs")
async def logs(limit: int = 100, key_id: int | None = None,
               authorization: str | None = Header(default=None),
               x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {"logs": store.recent_logs(min(max(limit, 1), 1000), key_id)}


@router.post("/admin/api/logs/cleanup")
async def logs_cleanup(payload: dict = Body(default={}),
                       authorization: str | None = Header(default=None),
                       x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    n = store.cleanup_logs(int((payload or {}).get("keep_days") or 90))
    return {"deleted": n}


@router.get("/admin/api/settings")
async def settings_get(authorization: str | None = Header(default=None),
                       x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    return {"upstream": _upstream_view()}


@router.post("/admin/api/credits/refresh")
async def credits_refresh(authorization: str | None = Header(default=None),
                          x_admin_token: str | None = Header(default=None)):
    require_admin(authorization, x_admin_token)
    data, err = billing.get_summary(_token_getter, force=True)
    if data:
        store.add_credit_snapshot(data["total"], data["remain"], data["used"], data)
    return {"credits": data, "error": err}


@router.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True})
