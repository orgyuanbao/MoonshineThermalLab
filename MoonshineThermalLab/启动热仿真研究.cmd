@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo 尚未安装本项目环境。请先双击“安装环境.cmd”。
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -u -B "%~dp0thermal_agent.py"
set "MOONSHINE_RUN_EXIT=%errorlevel%"
echo.
pause
exit /b %MOONSHINE_RUN_EXIT%
