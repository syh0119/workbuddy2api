# -*- coding: utf-8 -*-
"""Deploy workbuddy2api to CasaOS via /v2/app_management/compose (content-type: application/yaml)."""
import json, os, sys, urllib.request, urllib.error, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, ".build")
APP = "workbuddy2api"


def _read_kv(path):
    d = {}
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    return d


# 凭据优先级：环境变量 > casaos/casaos.env
# 请复制 casaos.env.example 为 casaos.env 后填写，该文件已被 .gitignore 排除
_cfg = _read_kv(os.path.join(HERE, "casaos.env"))
BASE = (os.environ.get("CASAOS_BASE") or _cfg.get("CASAOS_BASE") or "").rstrip("/")
USER = os.environ.get("CASAOS_USER") or _cfg.get("CASAOS_USER") or ""
PWD = os.environ.get("CASAOS_PWD") or _cfg.get("CASAOS_PWD") or ""

if not BASE or not USER or not PWD:
    raise SystemExit(
        "缺少 CasaOS 凭据。请复制 casaos/casaos.env.example 为 casaos/casaos.env 并填写：\n"
        "  CASAOS_BASE=http://<你的CasaOS地址>:<端口>\n"
        "  CASAOS_USER=<用户名>\n"
        "  CASAOS_PWD=<密码>\n"
        "或用环境变量 CASAOS_BASE / CASAOS_USER / CASAOS_PWD 传入。"
    )

# 默认绕过系统代理：CasaOS 多为内网地址，走代理会连不上
# 需要走代理时设 WB_USE_SYSTEM_PROXY=1
if os.environ.get("WB_USE_SYSTEM_PROXY") != "1":
    urllib.request.install_opener(
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
    )

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_env():
    env = {}
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def req(method, path, body=None, headers=None, timeout=60):
    url = BASE + path
    data = body if isinstance(body, (bytes, bytearray)) else (json.dumps(body).encode() if body is not None else None)
    h = {"Accept": "application/json"}
    if body is not None and not isinstance(body, (bytes, bytearray)):
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    r = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def login():
    st, raw = req("POST", "/v1/users/login", {"username": USER, "password": PWD})
    if st != 200:
        raise SystemExit("login failed %s %s" % (st, raw[:300]))
    return json.loads(raw)["data"]["token"]["access_token"]


def build_yaml(env, port="8000"):
    tpl = open(os.path.join(HERE, "compose.tpl.yml"), encoding="utf-8").read()
    payload = open(os.path.join(BUILD, "wb_payload.b64"), encoding="utf-8").read().strip()
    rep = {
        "__PORT__": port,
        "__PAYLOAD__": payload,
        "__AUTH_TOKEN__": env["CODEBUDDY_AUTH_TOKEN"],
        "__REFRESH_TOKEN__": env["CODEBUDDY_REFRESH_TOKEN"],
        "__USER_ID__": env["CODEBUDDY_USER_ID"],
        "__DOMAIN__": env["CODEBUDDY_DOMAIN"],
        "__API_BASE__": env["CODEBUDDY_API_BASE"],
        "__EXPIRES_AT__": env.get("CODEBUDDY_EXPIRES_AT", "0"),
        "__REFRESH_EXPIRES_AT__": env.get("CODEBUDDY_REFRESH_EXPIRES_AT", "0"),
        "__API_KEY__": env["API_KEY"],
        "__ADMIN_PASSWORD__": env.get("ADMIN_PASSWORD", ""),
        "__ADMIN_CREDIT_REFRESH_SEC__": env.get("ADMIN_CREDIT_REFRESH_SEC", "60"),
        "__BILLING_BASE__": env.get("CODEBUDDY_BILLING_BASE", "https://www.workbuddy.cn"),
        "__DEFAULT_MODEL__": env.get("DEFAULT_MODEL", "deepseek-v3"),
        "__DEFAULT_THINKING__": env.get("DEFAULT_THINKING", "high"),
    }
    for k, v in rep.items():
        tpl = tpl.replace(k, v)
    return tpl


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dry"
    port = sys.argv[2] if len(sys.argv) > 2 else "8000"
    y = build_yaml(load_env(), port)
    os.makedirs(BUILD, exist_ok=True)
    open(os.path.join(BUILD, "rendered.yml"), "w", encoding="utf-8").write(y)
    tok = login()
    # print existing apps
    st, raw = req("GET", "/v2/app_management/compose", headers={"Authorization": tok})
    try:
        d = json.loads(raw).get("data", {})
        apps = sorted(d.keys()) if isinstance(d, dict) else [a.get("name") for a in d]
    except Exception:
        apps = raw[:200]
    print("apps now:", apps)

    q = "?check_port_conflict=false&uncontrolled=true"
    if mode == "dry":
        q = "?dry_run=true"
    if mode in ("dry", "real"):
        st, raw = req("POST", "/v2/app_management/compose" + q, body=y.encode("utf-8"),
                      headers={"Authorization": tok, "Content-Type": "application/yaml"}, timeout=180)
        print("POST compose (%s) -> %s" % (mode, st))
        print(raw.decode("utf-8", "replace")[:2000])
    if mode == "update":
        # 热更新已有应用（改 compose / 换 token / 换代码包都走这里，无需卸载）
        st, raw = req("PUT", "/v2/app_management/compose/" + APP, body=y.encode("utf-8"),
                      headers={"Authorization": tok, "Content-Type": "application/yaml"}, timeout=180)
        print("PUT compose (update) -> %s" % st)
        print(raw.decode("utf-8", "replace")[:500])
    if mode == "uninstall":
        st, raw = req("DELETE", "/v2/app_management/compose/" + APP + "?delete_config_folder=true",
                      headers={"Authorization": tok}, timeout=180)
        print("DELETE -> %s" % st, raw[:500])
    if mode in ("logs", "status"):
        st, raw = req("GET", "/v2/app_management/compose/" + APP + "/logs?lines=80",
                      headers={"Authorization": tok})
        print(raw.decode("utf-8", "replace")[:3000])
        st, raw = req("GET", "/v2/app_management/compose/" + APP + "/containers",
                      headers={"Authorization": tok})
        try:
            c = json.loads(raw)["data"]["containers"]["workbuddy2api"]
            print("state:", c.get("State"), "|", c.get("Status"))
        except Exception:
            print(raw[:300])


if __name__ == "__main__":
    main()
