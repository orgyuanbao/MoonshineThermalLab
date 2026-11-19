@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1
set "MOONSHINE_INSTALL_EXIT=1"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3.12 "%~dp0setup_environment.py"
set "MOONSHINE_INSTALL_EXIT=%errorlevel%"
goto finished
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python "%~dp0setup_environment.py"
set "MOONSHINE_INSTALL_EXIT=%errorlevel%"
goto finished
:missing_python
echo 请先安装 Python 3.12 64 位，然后重新运行本文件。
:finished
echo.
pause
exit /b %MOONSHINE_INSTALL_EXIT%
