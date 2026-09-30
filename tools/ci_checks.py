#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目自检脚本：语法、结构、文档链接、Dockerfile 依赖、敏感信息。

只用标准库（YAML 检查可选依赖 pyyaml）。CI 与本地开发跑的是同一套，
所以提交前先跑一遍通常能省一次 CI 往返：

    python tools/ci_checks.py
    python tools/ci_checks.py --import-smoke    # 额外做导入冒烟（需先装 fastapi）

退出码 0 = 全部通过，1 = 有失败项。
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

FAILS: list[str] = []
PASSES: list[str] = []

# 绝不允许进入版本库的文件名模式
FORBIDDEN_FILES = [
    r"^\.env$",
    r"local_tokens\.json$",
    r"casaos/casaos\.env$",
    r"\.db(-wal|-shm)?$",
    r"keyblob$",
    r"tokens\.json$",
]

# 绝不允许出现在文件内容里的真实凭据样式
FORBIDDEN_CONTENT = [
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub PAT"),
    (r"github_pat_[A-Za-z0-9_]{40,}", "GitHub 细粒度 PAT"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI 风格密钥"),
    (r"eyJhbGciOiJSUzI1NiIsImtpZCI6[A-Za-z0-9+/=]{40,}", "真实 JWT"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥"),
]

REQUIRED_FILES = [
    "README.md",
    "README.en.md",
    "LICENSE",
    "SECURITY.md",
    "CHANGELOG.md",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "docker-compose.yml",
    "server.py",
    "codebuddy_direct_api.py",
    "store.py",
    "billing.py",
    "admin_routes.py",
    "static/admin.html",
    "tools/get_token.py",
    "tools/probe_models.py",
]


def ok(msg: str) -> None:
    PASSES.append(msg)
    print(f"  \033[32m✓\033[0m {msg}")


def bad(msg: str) -> None:
    FAILS.append(msg)
    print(f"  \033[31m✗\033[0m {msg}")


def track(path: str) -> bool:
    """该路径是否会被打进发布包（用 git 判断，回退到文件系统）。"""
    return os.path.exists(path)


def git_files() -> list[str]:
    """git 跟踪的文件列表；不在 git 仓库里时退化为遍历目录。"""
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout
        files = [l for l in out.splitlines() if l.strip()]
        if files:
            return files
    except Exception:
        pass
    skip = {".git", "__pycache__", "node_modules", ".build", "_tmp", ".venv", "venv"}
    found = []
    for base, dirs, names in os.walk("."):
        dirs[:] = [d for d in dirs if d not in skip]
        for n in names:
            found.append(os.path.relpath(os.path.join(base, n), ".").replace(os.sep, "/"))
    return found


def check_files_present() -> None:
    print("\n[1/7] 必需文件")
    missing = [f for f in REQUIRED_FILES if not os.path.exists(f)]
    if missing:
        bad(f"缺少文件: {', '.join(missing)}")
    else:
        ok(f"{len(REQUIRED_FILES)} 个必需文件齐备")


def check_forbidden_files(files: list[str]) -> None:
    print("\n[2/7] 敏感文件未被提交")
    hits = []
    for f in files:
        for pat in FORBIDDEN_FILES:
            if re.search(pat, f, re.I):
                hits.append(f)
                break
    if hits:
        bad(f"这些文件不该进版本库: {', '.join(hits)}")
    else:
        ok(f"{len(files)} 个跟踪文件里没有 .env / token / db / 私钥")


def check_forbidden_content(files: list[str]) -> None:
    print("\n[3/7] 文件内容不含真实凭据")
    hits = []
    for f in files:
        if f.endswith((".png", ".jpg", ".ico", ".woff", ".woff2", ".gz")):
            continue
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for pat, label in FORBIDDEN_CONTENT:
            m = re.search(pat, text)
            if m:
                hits.append(f"{f} 含 {label}")
    if hits:
        for h in hits:
            bad(h)
    else:
        ok("没有出现 PAT / JWT / 私钥 / OpenAI 风格密钥")


def check_python_syntax(files: list[str]) -> None:
    print("\n[4/7] Python 语法")
    pys = [f for f in files if f.endswith(".py")]
    errs = []
    for f in pys:
        try:
            ast.parse(open(f, encoding="utf-8").read(), filename=f)
        except SyntaxError as e:
            errs.append(f"{f}:{e.lineno}: {e.msg}")
    if errs:
        for e in errs:
            bad(e)
    else:
        ok(f"{len(pys)} 个 .py 文件语法正确")


def check_dockerfile() -> None:
    print("\n[5/7] Dockerfile 引用的文件都存在")
    if not os.path.exists("Dockerfile"):
        bad("没有 Dockerfile")
        return
    text = open("Dockerfile", encoding="utf-8").read()
    missing = []
    for m in re.finditer(r"^\s*COPY\s+(.+)$", text, re.M | re.I):
        parts = m.group(1).split()
        srcs = [p for p in parts[:-1] if not p.startswith("--")]
        for s in srcs:
            s = s.rstrip("/")
            if "*" in s or "$" in s:
                continue
            if not os.path.exists(s):
                missing.append(s)
    if missing:
        bad(f"COPY 的源文件不存在: {', '.join(missing)}")
    else:
        ok("所有 COPY 源文件都存在（漏拷模块会导致镜像启动即崩）")

    if "ADMIN_DB" not in text:
        bad("Dockerfile 未设置 ADMIN_DB，容器重建会丢密钥与日志")
    else:
        ok("Dockerfile 已设置 ADMIN_DB / 数据卷")


def check_yaml() -> None:
    print("\n[6/7] YAML 可解析")
    files = ["docker-compose.yml", "casaos/compose.tpl.yml"]
    wf = ".github/workflows/ci.yml"
    if os.path.exists(wf):
        files.append(wf)
    try:
        import yaml  # noqa
    except ImportError:
        print("  - 跳过（未安装 pyyaml）")
        return
    import yaml
    errs = []
    for f in files:
        if not os.path.exists(f):
            continue
        try:
            yaml.safe_load(open(f, encoding="utf-8").read())
        except Exception as e:
            errs.append(f"{f}: {e}")
    if errs:
        for e in errs:
            bad(e)
    else:
        ok(f"{len(files)} 个 YAML 文件解析正常")


def check_markdown_links(files: list[str]) -> None:
    print("\n[7/7] Markdown 相对链接")
    mds = [f for f in files if f.endswith(".md")]
    broken = []
    for f in mds:
        base = os.path.dirname(f)
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"\]\(([^)]+)\)", text):
            link = m.group(1).split("#")[0].strip()
            if not link or link.startswith(("http://", "https://", "mailto:")):
                continue
            target = os.path.normpath(os.path.join(base, link))
            if not os.path.exists(target):
                broken.append(f"{f} -> {link}")
    if broken:
        for b in broken:
            bad(f"失效链接 {b}")
    else:
        ok(f"{len(mds)} 个文档的相对链接都有效")


def check_shell() -> None:
    print("\n[额外] Shell 脚本语法")
    if not shutil_which("bash"):
        print("  - 跳过（没有 bash）")
        return
    scripts = [f for f in ("start.sh", "update_casaos.sh") if os.path.exists(f)]
    errs = []
    for s in scripts:
        r = subprocess.run(["bash", "-n", s], capture_output=True, text=True)
        if r.returncode != 0:
            errs.append(f"{s}: {r.stderr.strip()[:200]}")
    if errs:
        for e in errs:
            bad(e)
    else:
        ok(f"{len(scripts)} 个 shell 脚本语法正确")


def shutil_which(name: str):
    from shutil import which
    return which(name)


def collect_paths(routes) -> set:
    """递归收集路由路径。

    新版 FastAPI 把 include_router 的结果表示成 `_IncludedRouter`，
    子路由不会摊平到 app.routes 里，所以要往下钻一层。
    """
    out: set = set()
    stack = list(routes)
    while stack:
        r = stack.pop()
        p = getattr(r, "path", None)
        if isinstance(p, str) and p:
            out.add(p)
        for attr in ("routes",):
            sub = getattr(r, attr, None)
            if sub:
                stack.extend(sub)
        sub_router = getattr(r, "router", None)
        if sub_router is not None:
            stack.extend(getattr(sub_router, "routes", None) or [])
    return out


def import_smoke() -> None:
    print("\n[额外] 导入冒烟测试")
    os.environ.setdefault("CODEBUDDY_AUTH_TOKEN", "dummy-token-for-ci")
    os.environ.setdefault("API_KEY", "dummy-key-for-ci")
    os.environ.setdefault("ADMIN_PASSWORD", "dummy-pw-for-ci")
    os.environ.setdefault("ADMIN_DB", os.path.join(ROOT, ".build", "ci-smoke.db"))
    try:
        sys.path.insert(0, ROOT)
        import server  # noqa
    except ImportError as e:
        bad(f"导入 server 失败（缺模块或没装依赖）: {e}")
        return
    except Exception as e:
        bad(f"导入 server 抛异常: {type(e).__name__}: {e}")
        return

    try:
        paths = set(server.app.openapi().get("paths", {}).keys())
    except Exception as e:
        # 退回路由对象遍历（新版 FastAPI 的 include_router 不一定能摊平）
        print(f"  - openapi() 不可用（{e}），改走路由遍历")
        paths = collect_paths(server.app.routes)
    need = ["/health", "/v1/models", "/v1/chat/completions", "/admin", "/admin/api/overview"]
    lack = [p for p in need if p not in paths]
    if lack:
        bad(f"缺少路由: {', '.join(lack)}")
    else:
        ok(f"server 导入成功，{len(paths)} 条路由，关键端点齐全")


def main() -> int:
    print("=" * 60)
    print("WorkBuddy2API 自检")
    print("=" * 60)
    files = git_files()

    check_files_present()
    check_forbidden_files(files)
    check_forbidden_content(files)
    check_python_syntax(files)
    check_dockerfile()
    check_yaml()
    check_markdown_links(files)
    check_shell()
    if "--import-smoke" in sys.argv:
        import_smoke()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"结果：{len(PASSES)} 项通过，\033[31m{len(FAILS)} 项失败\033[0m")
        for f in FAILS:
            print(f"  ✗ {f}")
        return 1
    print(f"结果：\033[32m全部 {len(PASSES)} 项检查通过\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
