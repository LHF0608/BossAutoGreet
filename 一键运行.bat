@echo off
chcp 936 >nul
title BOSS直聘智能全自动打招呼系统 - 一键启动
cd /d "%~dp0"

echo ========================================================
echo        BOSS直聘智能全自动打招呼系统 (一键独立启动)
echo ========================================================
echo.

REM 1. 检查是否已经在后台运行 (端口 8080)
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [*] 检测到系统后台已在运行中！
    echo [*] 正在直接唤醒浏览器打开控制台: http://127.0.0.1:8080
    start http://127.0.0.1:8080
    echo.
    echo [*] 控制台已就绪，无需重复开启！
    ping 127.0.0.1 -n 3 >nul
    exit /b 0
)

REM 2. 自动定位 Python 解释器
set "PY_CMD="

REM 2.1 检查便携环境 / 当前目录内置环境
if exist "%~dp0python_env\python.exe" (
    set "PY_CMD=%~dp0python_env\python.exe"
    goto py_found
)

REM 2.2 测试系统全局 PATH 中的 python
python -V >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto py_found
)

REM 2.3 测试 Python Launcher (py)
py -3 -V >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
    goto py_found
)

REM 2.4 扫描本机已知 Python 路径
if exist "L:\EnvSoftware\Python\python.exe" (
    set "PY_CMD=L:\EnvSoftware\Python\python.exe"
    goto py_found
)

for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto py_found
)
)

for /d %%D in ("C:\Python*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto py_found
)
)

for /d %%D in ("D:\Python*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto py_found
)
)

echo ========================================================
echo [错误] 未在电脑中检测到 Python 环境！
echo 请先安装 Python 3.10+ 并勾选 Add Python to PATH 选项。
echo 官方下载地址: https://www.python.org/downloads/
echo ========================================================
echo.
pause
exit /b 1

:py_found
echo [*] 已定位 Python 解释器: %PY_CMD%
echo [*] 正在检查依赖环境 (使用国内清华源高速通道)...
%PY_CMD% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet

echo [*] 启动后台服务 (纯后台无弹窗运行，扫码直接在网页内完成)...
echo [*] 控制台即将就绪: http://127.0.0.1:8080
echo [*] 提示: 本程序完全独立运行，无需打开 VS Code 或任何开发工具！
echo.

%PY_CMD% app.py

pause
