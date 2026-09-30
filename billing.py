# -*- coding: utf-8 -*-
"""上游计费接口：查询账号积分总额 / 剩余 / 已用。

接口：POST {base}/billing/meter/get-user-resource-summary（body {}，返回 Packages 数组）
注意：这个路径**不带 /v2 前缀**（带 /v2 会 404）。
"""
from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request

BILLING_BASE = (os.environ.get("CODEBUDDY_BILLING_BASE") or "https://www.workbuddy.cn").rstrip("/")
SUMMARY_PATH = "/billing/meter/get-user-resource-summary"
REFRESH_SEC = float(os.environ.get("ADMIN_CREDIT_REFRESH_SEC", "60"))

_lock = threading.RLock()
_cache: dict = {"ts": 0.0, "data": None, "error": ""}


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fetch_summary(access_token: str, base: str | None = None, timeout: int = 15) -> dict:
    """拉取积分摘要。返回 {total, remain, used, packages, plan, paid, ts}。"""
    url = (base or BILLING_BASE) + SUMMARY_PATH
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "zh-CN",
        "User-Agent": "WorkBuddy2API-Admin/1.0",
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        body = json.loads(resp.read().decode("utf-8", "replace"))

    if body.get("code") not in (0, None) and not body.get("data"):
        raise RuntimeError("计费接口返回异常: %s" % body.get("msg"))

    data = body.get("data") or {}
    packages = []
    total = remain = used = 0.0
    for p in data.get("Packages") or []:
        t = _num(p.get("CycleTotalCapacity"))
        r = _num(p.get("CycleRemainCapacity"))
        u = _num(p.get("CycleUsedCapacity"))
        total += t
        remain += r
        used += u
        packages.append({
            "code": p.get("PackageCode", ""),
            "total": round(t, 2),
            "remain": round(r, 2),
            "used": round(u, 2),
            "unit": p.get("CapacityUnit") or "credits",
        })
    return {
        "total": round(total, 4),
        "remain": round(remain, 4),
        "used": round(used, 4),
        "packages": packages,
        "plan": data.get("SubscriptionPackageName") or "",
        "paid": bool(data.get("IsPaidUser")),
        "ts": time.time(),
    }


def get_summary(token_getter, force: bool = False) -> tuple[dict | None, str]:
    """带缓存的读取。token_getter() 返回当前 access_token。返回 (data, error)。"""
    with _lock:
        fresh = _cache["data"] and (time.time() - _cache["ts"] < REFRESH_SEC)
        if fresh and not force:
            return _cache["data"], ""
        try:
            data = fetch_summary(token_getter())
            _cache.update(ts=time.time(), data=data, error="")
            return data, ""
        except Exception as e:  # 网络/鉴权问题都不该让面板崩掉
            _cache["error"] = str(e)
            if _cache["data"]:
                return _cache["data"], str(e)
            return None, str(e)


def cached() -> dict | None:
    with _lock:
        return _cache["data"]
