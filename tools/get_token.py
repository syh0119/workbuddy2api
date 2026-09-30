#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本地 WorkBuddy 客户端里取出 access_token / refresh_token，方便写进 .env。

用法：
    python tools/get_token.py                # 自动查找并检查本地 auth 文件
    python tools/get_token.py --json         # 打印 JSON（自己复制到 .env）
    python tools/get_token.py --write        # 直接写入同目录上一级的 .env
    python tools/get_token.py --access <TOKEN> [--refresh <TOKEN>] [--write]
                                             # 手动传入（配合抓包法）

退出码：0 成功；2 需要手动获取（token 被加密或找不到文件）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

AUTH_REL = "CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info"

CANDIDATES = [
    # Electron 标准 userData 目录
    os.path.join(os.environ.get("APPDATA", ""), AUTH_REL),                       # Windows
    os.path.join(os.environ.get("LOCALAPPDATA", ""), AUTH_REL),                  # Windows（实测在 Local）
    os.path.expanduser("~/Library/Application Support/" + AUTH_REL),             # macOS
    os.path.expanduser("~/.config/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info"),
    os.path.expanduser("~/.workbuddy/auth/workbuddy-desktop.info"),
]


def is_encrypted(v) -> bool:
    return isinstance(v, dict) and ("$wbEncrypted" in v or "envelope" in v)


def find_auth_file() -> str | None:
    for p in CANDIDATES:
        if p and os.path.isfile(p):
            return p
    return None


def manual_help() -> None:
    print(
        "\n需要手动获取 token（30 秒）：\n"
        "  1. 打开 WorkBuddy 桌面端并确保已登录\n"
        "  2. 按 F12 打开开发者工具 → Network 面板\n"
        "  3. 在客户端里随便发一条消息\n"
        "  4. 找到发往 copilot.tencent.com 的请求，复制请求头里的\n"
        "     Authorization: Bearer <access_token>   （这串就是 CODEBUDDY_AUTH_TOKEN）\n"
        "  5. refresh token 在登录/刷新接口的响应里，字段名 refreshToken；\n"
        "     没有也行，只是过期后要手动换。\n\n"
        "拿到后写入 .env：\n"
        "  python tools/get_token.py --access <ACCESS> [--refresh <REFRESH>] --write\n",
        file=sys.stderr,
    )


def write_env(pairs: dict) -> None:
    path = os.path.join(ROOT, ".env")
    lines = []
    if os.path.isfile(path):
        lines = open(path, encoding="utf-8").read().splitlines()
    for k, v in pairs.items():
        for i, ln in enumerate(lines):
            if ln.startswith(k + "="):
                lines[i] = "%s=%s" % (k, v)
                break
        else:
            lines.append("%s=%s" % (k, v))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("[✓] 已写入 %s" % path)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--access", default="")
    ap.add_argument("--refresh", default="")
    ap.add_argument("--domain", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    access, refresh, domain = args.access, args.refresh, args.domain
    source = "命令行参数"

    if not access:
        path = find_auth_file()
        if not path:
            print("[x] 没找到本地 auth 文件，试过：")
            for p in CANDIDATES:
                if p:
                    print("    -", p)
            manual_help()
            return 2
        print("[*] auth 文件: %s" % path)
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print("[x] 解析失败: %s" % e)
            manual_help()
            return 2

        auth = data.get("auth") or data
        raw_access = auth.get("accessToken") or auth.get("access_token")
        raw_refresh = auth.get("refreshToken") or auth.get("refresh_token")
        domain = domain or auth.get("domain") or "www.workbuddy.cn"

        if raw_access is None:
            print("[x] auth 文件里没有 accessToken 字段，内容为：")
            print(json.dumps(data, ensure_ascii=False)[:800])
            manual_help()
            return 2

        if is_encrypted(raw_access) or is_encrypted(raw_refresh):
            print("[!] 该版本客户端把 token 加密存储了（字段是 $wbEncrypted 信封），")
            print("    直接读文件拿不到明文。请用上面的抓包法。")
            manual_help()
            return 2

        access = raw_access or ""
        refresh = raw_refresh or ""
        source = "本地 auth 文件"

    print("[✓] 来源: %s" % source)
    print("    access_token  : %s（%d 字符）" % (access[:16] + "...", len(access)))

    if refresh:
        print("    refresh_token : %s（%d 字符）" % (refresh[:16] + "...", len(refresh)))
    else:
        print("    refresh_token : （没有）access_token 过期后需要手动更换")

    pairs = {"CODEBUDDY_AUTH_TOKEN": access}
    if refresh:
        pairs["CODEBUDDY_REFRESH_TOKEN"] = refresh
    if domain:
        pairs["CODEBUDDY_DOMAIN"] = domain

    if args.write:
        write_env(pairs)
    if args.json:
        print(json.dumps(pairs, ensure_ascii=False, indent=2))
    elif not args.write:
        print("\n加上 --write 可直接写入 .env，或加 --json 打印 JSON。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
