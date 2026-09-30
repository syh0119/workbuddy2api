@echo off
setlocal
cd /d "%~dp0"

set "PY="
rem 依次尝试常见解释器，先用能跑起来的
for %%C in ("python" "py -3") do (
  if not defined PY (
    %%~C -c "import sys" >nul 2>nul && set "PY=%%~C"
  )
)
rem 兜底：WorkBuddy 自带的 python
if not defined PY (
  for /f "delims=" %%F in ('dir /b /o-n "%USERPROFILE%\.workbuddy\binaries\python\versions" 2^>nul') do (
    if not defined PY if exist "%USERPROFILE%\.workbuddy\binaries\python\versions\%%F\python.exe" (
      set "PY=%USERPROFILE%\.workbuddy\binaries\python\versions\%%F\python.exe"
    )
  )
)

if not defined PY (
  echo [x] 没找到可用的 Python，请手动执行:  python update.py
  pause
  exit /b 1
)

echo 使用解释器: %PY%
%PY% update.py %*
echo.
pause
