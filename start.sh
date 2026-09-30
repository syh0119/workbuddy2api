#!/usr/bin/env bash
# WorkBuddy2API 本地启动脚本（从 .env 读取 token 与 API_KEY）
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "[!] 缺少 .env，请先 cp .env.example .env 并填写 token" >&2
  exit 1
fi

set -a
. ./.env
set +a

# 依次尝试可用的解释器，选出能 import fastapi 的那个
TRIED=()
for cand in "${PYTHON:-}" python python3 py; do
  [ -n "$cand" ] || continue
  command -v "$cand" >/dev/null 2>&1 || continue
  TRIED+=("$cand -> $(command -v "$cand")")
  if "$cand" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    exec "$cand" server.py
  fi
done

echo "" >&2
echo "[!] 没找到装了 fastapi/uvicorn 的 Python。" >&2
if [ ${#TRIED[@]} -gt 0 ]; then
  echo "    已尝试的解释器：" >&2
  for t in "${TRIED[@]}"; do echo "      $t" >&2; done
fi
echo "" >&2
echo "    机器上可能有多个 Python，装包和跑服务的必须是同一个。请执行：" >&2
echo "      python -c \"import sys;print(sys.executable)\"   # 看当前用的是哪个" >&2
echo "      <上面的路径> -m pip install fastapi uvicorn" >&2
echo "    或者指定解释器启动：" >&2
echo "      PYTHON=/path/to/python bash start.sh" >&2
exit 1
