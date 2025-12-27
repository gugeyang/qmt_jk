@echo off
:: 设置控制台为 UTF-8 编码以支持中文显示
chcp 65001 >nul
title QMT 股票监控系统

echo 正在检查并清理旧进程 (端口 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo 正在启动 QMT 股票监控系统...
echo.

:: 设置 Python 路径
set PYTHON_EXE="C:\Users\admin\AppData\Local\Programs\Python\Python39\python.exe"

:: 检查 Python 路径是否存在
if not exist %PYTHON_EXE% (
    echo [错误] 找不到 Python 3.9 环境，请检查路径:
    echo %PYTHON_EXE%
    pause
    exit /b
)

:: 自动启动 MiniQMT 客户端 (如果已经在运行则会被置顶)
echo 正在启动 MiniQMT 客户端...
start "" "E:\gj_qmt\bin.x64\XtMiniQmt.exe"
timeout /t 5 >nul

:: 运行程序
echo 正在启动监控后台...
%PYTHON_EXE% main.py

echo.
echo 程序已停止运行。
pause
