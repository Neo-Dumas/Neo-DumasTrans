@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 👇 关键：把绿色 Python 和 Scripts 加入 PATH
set "PATH=%SCRIPT_DIR%python-3.10.11;%SCRIPT_DIR%python-3.10.11\Scripts;%PATH%"

echo 使用 Python: %SCRIPT_DIR%python-3.10.11\python.exe
"%SCRIPT_DIR%python-3.10.11\python.exe" Neo-DumasTrans.py

pause