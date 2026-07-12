@echo off
chcp 65001 >nul 2>&1
title GT_agent - 面试题智能学习平台
cd /d "%~dp0"

echo ============================================
echo    GT_agent 面试题智能学习平台 启动中...
echo ============================================
echo.

:: 检查 Python 是否可用
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并添加到 PATH
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查 .env 文件
if not exist ".env" (
    echo [警告] 未找到 .env 文件，请确保已配置 DEEPSEEK_API_KEY
    echo.
)

:: 检查端口 8000 是否被占用，若占用则用 8001
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo [提示] 端口 8000 已被占用，自动切换到 8001
    echo.
    start "" "http://localhost:8001"
    python -m uvicorn main:app --host 0.0.0.0 --port 8001
) else (
    start "" "http://localhost:8000"
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
)

pause
