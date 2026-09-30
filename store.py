# -*- coding: utf-8 -*-
"""SQLite 存储层：API 密钥、用量日志、积分快照、设置。

所有表都放在同一个 db 文件里（容器内 /data/admin.db，挂载到宿主 /DATA/AppData/workbuddy2api）。
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time

# 默认落在项目目录（与工作目录无关）；容器部署时通过 ADMIN_DB=/data/admin.db 覆盖
DB_PATH = os.environ.get("ADMIN_DB") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "admin.db"
)

_KEY_PREFIX = "sk-wb-"

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    key           TEXT    NOT NULL UNIQUE,
    enabled       INTEGER NOT NULL DEFAULT 1,
    quota_type    TEXT    NOT NULL DEFAULT 'none',   -- none | requests | credits | tokens
    quota_limit   REAL    NOT NULL DEFAULT 0,
    quota_used    REAL    NOT NULL DEFAULT 0,
    expires_at    REAL    NOT NULL DEFAULT 0,        -- 0 = 永不过期
    note          TEXT    NOT NULL DEFAULT '',
    created_at    REAL    NOT NULL,
    last_used_at  REAL    NOT NULL DEFAULT 0,
    is_master     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS request_log(
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                REAL    NOT NULL,
    key_id            INTEGER,
    key_name          TEXT    NOT NULL DEFAULT '',
    endpoint          TEXT    NOT NULL DEFAULT '',
    model             TEXT    NOT NULL DEFAULT '',
    status            INTEGER NOT NULL DEFAULT 0,
    latency_ms        INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    credit            REAL    NOT NULL DEFAULT 0,
    ip                TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_log_ts  ON request_log(ts);
CREATE INDEX IF NOT EXISTS idx_log_key ON request_log(key_id, ts);

CREATE TABLE IF NOT EXISTS credit_snapshots(
    ts     REAL NOT NULL,
    total  REAL NOT NULL DEFAULT 0,
    remain REAL NOT NULL DEFAULT 0,
    used   REAL NOT NULL DEFAULT 0,
    raw    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_snap_ts ON credit_snapshots(ts);

CREATE TABLE IF NOT EXISTS settings(
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL DEFAULT ''
);
"""


def _get() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            d = os.path.dirname(DB_PATH)
            if d:
                os.makedirs(d, exist_ok=True)
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
        return _conn


def init(master_key: str = "") -> None:
    """建表 + 把 .env 里的 API_KEY 同步成主密钥行。"""
    with _lock:
        c = _get()
        c.executescript(SCHEMA)
        c.commit()
        if master_key:
            row = c.execute("SELECT id FROM api_keys WHERE is_master=1").fetchone()
            now = time.time()
            if row is None:
                c.execute(
                    "INSERT INTO api_keys(name,key,enabled,quota_type,quota_limit,quota_used,"
                    "expires_at,note,created_at,last_used_at,is_master) VALUES(?,?,1,'none',0,0,0,?,?,0,1)",
                    ("主密钥（.env）", master_key, "来自环境变量 API_KEY，不可删除，无额度限制", now),
                )
            else:
                c.execute("UPDATE api_keys SET key=? WHERE id=?", (master_key, row["id"]))
            c.commit()


# ── 序列化 ────────────────────────────────────────────────────────────────
def _key_row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["enabled"] = bool(d["enabled"])
    d["is_master"] = bool(d["is_master"])
    d["key_masked"] = d["key"][:11] + "…" + d["key"][-4:]
    return d


def _public_key_row(r: sqlite3.Row) -> dict:
    d = _key_row(r)
    if not d["is_master"]:
        d.pop("key", None)
    return d


# ── 密钥 CRUD ─────────────────────────────────────────────────────────────
def list_keys(include_secret: bool = True) -> list[dict]:
    with _lock:
        rows = _get().execute("SELECT * FROM api_keys ORDER BY is_master DESC, id ASC").fetchall()
    f = _key_row if include_secret else _public_key_row
    return [f(r) for r in rows]


def get_key_by_value(key: str) -> dict | None:
    if not key:
        return None
    with _lock:
        r = _get().execute("SELECT * FROM api_keys WHERE key=?", (key,)).fetchone()
    return _key_row(r) if r else None


def get_key(kid: int) -> dict | None:
    with _lock:
        r = _get().execute("SELECT * FROM api_keys WHERE id=?", (kid,)).fetchone()
    return _key_row(r) if r else None


def create_key(name: str, quota_type: str = "none", quota_limit: float = 0,
               expires_at: float = 0, note: str = "") -> dict:
    key = _KEY_PREFIX + secrets.token_hex(20)
    now = time.time()
    with _lock:
        cur = _get().execute(
            "INSERT INTO api_keys(name,key,enabled,quota_type,quota_limit,quota_used,expires_at,"
            "note,created_at,last_used_at,is_master) VALUES(?,?,1,?,?,0,?,?,?,0,0)",
            (name or "未命名", key, quota_type, float(quota_limit or 0), float(expires_at or 0), note or "", now),
        )
        _get().commit()
        kid = cur.lastrowid
    return get_key(kid)


def update_key(kid: int, **fields) -> dict | None:
    allowed = {"name", "enabled", "quota_type", "quota_limit", "quota_used", "expires_at", "note"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        if k == "enabled":
            v = 1 if v else 0
        sets.append("%s=?" % k)
        vals.append(v)
    if not sets:
        return get_key(kid)
    vals.append(kid)
    with _lock:
        _get().execute("UPDATE api_keys SET %s WHERE id=?" % ",".join(sets), vals)
        _get().commit()
    return get_key(kid)


def delete_key(kid: int) -> bool:
    with _lock:
        k = _get().execute("SELECT is_master FROM api_keys WHERE id=?", (kid,)).fetchone()
        if not k or k["is_master"]:
            return False
        _get().execute("DELETE FROM api_keys WHERE id=?", (kid,))
        _get().commit()
    return True


def regenerate_key(kid: int) -> dict | None:
    key = _KEY_PREFIX + secrets.token_hex(20)
    with _lock:
        k = _get().execute("SELECT is_master FROM api_keys WHERE id=?", (kid,)).fetchone()
        if not k or k["is_master"]:
            return None
        _get().execute("UPDATE api_keys SET key=? WHERE id=?", (key, kid))
        _get().commit()
    return get_key(kid)


def add_usage(kid: int, quota_type: str, credit: float = 0.0, tokens: int = 0, requests: int = 1) -> None:
    """按额度的计量方式累加：requests 记次数，credits 记积分，tokens 记 token 数。"""
    if quota_type == "credits":
        delta = float(credit or 0)
    elif quota_type == "tokens":
        delta = float(tokens or 0)
    elif quota_type == "requests":
        delta = float(requests or 0)
    else:
        delta = 0.0
    with _lock:
        if delta:
            _get().execute(
                "UPDATE api_keys SET last_used_at=?, quota_used=quota_used+? WHERE id=?",
                (time.time(), delta, kid))
        else:
            _get().execute("UPDATE api_keys SET last_used_at=? WHERE id=?", (time.time(), kid))
        _get().commit()


def reset_usage(kid: int, value: float = 0.0) -> None:
    with _lock:
        _get().execute("UPDATE api_keys SET quota_used=? WHERE id=?", (float(value), kid))
        _get().commit()


def check_quota(k: dict) -> tuple[bool, str]:
    """返回 (是否放行, 拒绝原因)。"""
    if not k.get("enabled"):
        return False, "该 API Key 已被禁用"
    exp = float(k.get("expires_at") or 0)
    if exp and time.time() > exp:
        return False, "该 API Key 已过期"
    qt = k.get("quota_type") or "none"
    limit = float(k.get("quota_limit") or 0)
    used = float(k.get("quota_used") or 0)
    if qt == "none" or limit <= 0:
        return True, ""
    if used >= limit:
        unit = {"requests": "次", "credits": "积分", "tokens": "tokens"}.get(qt, "")
        return False, "额度已用完（%s/%s %s）" % (round(used, 4), limit, unit)
    return True, ""


# ── 请求日志 ──────────────────────────────────────────────────────────────
def log_request(ts: float, key_id, key_name: str, endpoint: str, model: str, status: int,
                latency_ms: int = 0, prompt_tokens: int = 0, completion_tokens: int = 0,
                total_tokens: int = 0, credit: float = 0.0, ip: str = "") -> None:
    with _lock:
        _get().execute(
            "INSERT INTO request_log(ts,key_id,key_name,endpoint,model,status,latency_ms,"
            "prompt_tokens,completion_tokens,total_tokens,credit,ip) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (ts, key_id, key_name, endpoint, model, status, latency_ms,
             prompt_tokens, completion_tokens, total_tokens, credit, ip),
        )
        _get().commit()


def recent_logs(limit: int = 100, key_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM request_log"
    args: list = []
    if key_id:
        sql += " WHERE key_id=?"
        args.append(key_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    with _lock:
        rows = _get().execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def usage_by_day(days: int = 7, key_id: int | None = None) -> list[dict]:
    """按本地日期聚合。"""
    since = time.time() - days * 86400
    sql = ("SELECT date(ts,'unixepoch','localtime') AS day, COUNT(*) AS requests, "
           "SUM(total_tokens) AS tokens, SUM(credit) AS credits, "
           "SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors "
           "FROM request_log WHERE ts>=?")
    args: list = [since]
    if key_id:
        sql += " AND key_id=?"
        args.append(key_id)
    sql += " GROUP BY day ORDER BY day ASC"
    with _lock:
        rows = _get().execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def usage_by_key(days: int = 7) -> list[dict]:
    since = time.time() - days * 86400
    with _lock:
        rows = _get().execute(
            "SELECT key_id, key_name, COUNT(*) AS requests, SUM(total_tokens) AS tokens, "
            "SUM(credit) AS credits, SUM(CASE WHEN status>=400 THEN 1 ELSE 0 END) AS errors "
            "FROM request_log WHERE ts>=? GROUP BY key_id, key_name ORDER BY credits DESC",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def usage_by_model(days: int = 7) -> list[dict]:
    since = time.time() - days * 86400
    with _lock:
        rows = _get().execute(
            "SELECT model, COUNT(*) AS requests, SUM(total_tokens) AS tokens, SUM(credit) AS credits "
            "FROM request_log WHERE ts>=? AND model<>'' GROUP BY model ORDER BY requests DESC LIMIT 50",
            (since,),
        ).fetchall()
    return [dict(r) for r in rows]


def cleanup_logs(keep_days: int = 90) -> int:
    cutoff = time.time() - keep_days * 86400
    with _lock:
        cur = _get().execute("DELETE FROM request_log WHERE ts<?", (cutoff,))
        _get().commit()
        return cur.rowcount


# ── 积分快照 ──────────────────────────────────────────────────────────────
def add_credit_snapshot(total: float, remain: float, used: float, raw: dict | None = None) -> None:
    with _lock:
        _get().execute(
            "INSERT INTO credit_snapshots(ts,total,remain,used,raw) VALUES(?,?,?,?,?)",
            (time.time(), total, remain, used, json.dumps(raw or {}, ensure_ascii=False)[:4000]),
        )
        _get().commit()


def latest_credit() -> dict | None:
    with _lock:
        r = _get().execute("SELECT * FROM credit_snapshots ORDER BY ts DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def credit_history(days: int = 7) -> list[dict]:
    since = time.time() - days * 86400
    with _lock:
        rows = _get().execute(
            "SELECT date(ts,'unixepoch','localtime') AS day, "
            "MIN(ts) AS ts_first, MAX(ts) AS ts_last, MIN(remain) AS remain_min, "
            "MAX(remain) AS remain_max, MIN(used) AS used_min, MAX(used) AS used_max "
            "FROM credit_snapshots WHERE ts>=? GROUP BY day ORDER BY day ASC",
            (since,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["used"] = round((d["used_max"] or 0) - (d["used_min"] or 0), 4)
        d["remain"] = d["remain_max"]
        out.append(d)
    return out


# ── 设置 ──────────────────────────────────────────────────────────────────
def get_setting(k: str, default: str = "") -> str:
    with _lock:
        r = _get().execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    return r["v"] if r else default


def set_setting(k: str, v: str) -> None:
    with _lock:
        _get().execute(
            "INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
        _get().commit()


def stats() -> dict:
    with _lock:
        c = _get()
        keys = c.execute("SELECT COUNT(*) n FROM api_keys").fetchone()["n"]
        active = c.execute("SELECT COUNT(*) n FROM api_keys WHERE enabled=1").fetchone()["n"]
        logs = c.execute("SELECT COUNT(*) n FROM request_log").fetchone()["n"]
        since = time.time() - 86400
        today = c.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(credit),0) cr, COALESCE(SUM(total_tokens),0) tk "
            "FROM request_log WHERE ts>=?", (since,)).fetchone()
    return {
        "keys": keys, "keys_active": active, "logs": logs,
        "today_requests": today["n"], "today_credits": round(today["cr"], 4), "today_tokens": today["tk"],
    }
