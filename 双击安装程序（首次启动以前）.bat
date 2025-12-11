@echo off
setlocal
cd /d "%~dp0"

set "PY_DIR=python-3.10.11"

if exist "%PY_DIR%\" (
    echo [!] 便携版 Python 已存在，跳过下载。
    goto :run_py
)

echo [*] 下载 Python 3.10.11 嵌入版...
curl -fL -o python-3.10.11-embed-amd64.zip https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip || (
    echo [!] 下载失败，请检查网络。
    pause
    exit /b 1
)

echo [*] 创建目标目录...
mkdir "%PY_DIR%" 2>nul

echo [*] 解压...
tar -xf python-3.10.11-embed-amd64.zip -C "%PY_DIR%" || (
    echo [!] 解压失败。
    pause
    exit /b 1
)

del python-3.10.11-embed-amd64.zip

:: ✅ 关键：正确写入 _pth 文件（无空行！）
(
echo python310.zip
echo .
echo import site
) > "%PY_DIR%\python310._pth"

echo [*] Python 便携环境已就绪！

:run_py
if not exist "install_deps.py" (
    echo [!] 缺少 install_deps.py，无法安装依赖。
    pause
    exit /b 1
)

echo [*] 启动依赖安装脚本...
call "%PY_DIR%\python.exe" install_deps.py
pause