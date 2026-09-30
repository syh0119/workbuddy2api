# -*- coding: utf-8 -*-
"""探测上游实际支持的模型 id（走已部署的 OpenAI 兼容接口）。"""
import json, os, sys, time, urllib.request, urllib.error, threading
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 目标服务地址：本地或你自己部署的地址
BASE = os.environ.get("WB_BASE", "http://127.0.0.1:8000")
OPEN = os.environ.get("WB_OPEN", "1") == "1"

env = {}
for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
KEY = env["API_KEY"]

CANDIDATES = [
    # GLM 家族
    "glm-4.5", "glm-4.5-air", "glm-4.5v", "glm-4.6", "glm-4.6v",
    "glm-4.7-flash", "glm-4.7-flashx", "glm-4.7-ioa",
    "glm-5", "glm-5-turbo", "glm-5.1-ioa",
    "glm-5.2-fast", "glm-5.2-highspeed",
    "glm-5.3", "glm-5.3-flash", "glm-5.3-fast", "glm-5.3-highspeed", "glm-5.3-promo-50",
    "glm-5p2", "glm-5p2-fast", "glm-5p3", "glm-5p3-flash",
    "zai-glm-5-2", "zai.glm-5", "zai.glm-4.7", "zai.glm-4.7-flash",
    # 顺手探几个其他家族的新版本
    "kimi-k3-2", "minimax-m2.8", "deepseek-v4", "hy5-preview",
]

lock = threading.Lock()
results = {}


def probe(model):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ok"}],
        "stream": False,
        "max_tokens": 16,
    }).encode()
    req = urllib.request.Request(
        BASE + "/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read())
        c = d.get("choices", [{}])[0].get("message", {})
        ok = bool(c.get("content") or c.get("reasoning_content"))
        with lock:
            results[model] = ("OK", (c.get("content") or "")[:20])
    except urllib.error.HTTPError as e:
        with lock:
            results[model] = ("FAIL", e.read()[:80].decode("utf-8", "replace"))
    except Exception as e:
        with lock:
            results[model] = ("ERR", str(e)[:80])


t0 = time.time()
with ThreadPoolExecutor(max_workers=2) as ex:
    list(ex.map(probe, CANDIDATES))

print("耗时 %.0fs" % (time.time() - t0))
ok = [m for m, (s, _) in results.items() if s == "OK"]
print("\n=== 可用 (%d) ===" % len(ok))
for m in ok:
    print("  %-24s %s" % (m, results[m][1]))
print("\n=== 不可用 ===")
for m in CANDIDATES:
    if results.get(m, ("?",))[0] != "OK":
        print("  %-24s %s" % (m, results.get(m, ("?", ""))[0]))

open(os.path.join(ROOT, ".build", "probe_result.json"), "w", encoding="utf-8").write(
    json.dumps(results, ensure_ascii=False, indent=1))
