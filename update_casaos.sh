#!/usr/bin/env bash
# 一键更新 CasaOS 上的 workbuddy2api（等价于 python update.py）
#   bash update_casaos.sh          # 重新打包代码 + 推送 + 验证
#   bash update_casaos.sh env      # 只推送（改了 .env）
#   bash update_casaos.sh verify   # 只验证
#   bash update_casaos.sh logs     # 看容器日志
set -e
cd "$(dirname "$0")"
exec python update.py "$@"
