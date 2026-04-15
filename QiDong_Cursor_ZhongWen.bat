

@echo off
chcp 65001 >nul 2>&1
title Cursor 中文版启动器

echo ============================================================
echo   Cursor 中文版启动器
echo   功能：自动注入汉化脚本后启动 Cursor
echo ============================================================
echo.

REM ============================================================
REM ★★★ 用户配置区域 - 请根据您的实际路径修改 ★★★
REM ============================================================
set "CURSOR_EXE=D:\Tools\cursor\Cursor.exe"
set "CURSOR_USER_DIR=D:\Tools\cursor\user"
set "HANHUA_SCRIPT=E:\Cursor_chinese\CursorHanHua_GongJu.py"
set "WORKBENCH_HTML=D:\Tools\cursor\resources\app\out\vs\code\electron-sandbox\workbench\workbench.html"
set "INJECTION_MARKER=CURSOR_HANHUA_INJECTION"
REM ============================================================

REM 检查 Cursor 是否存在
if not exist "%CURSOR_EXE%" (
    echo [错误] 未找到 Cursor: %CURSOR_EXE%
    echo [提示] 请修改本文件中的 CURSOR_EXE 路径
    pause
    exit /b 1
)

REM 检查汉化脚本是否存在
if not exist "%HANHUA_SCRIPT%" (
    echo [错误] 未找到汉化脚本: %HANHUA_SCRIPT%
    pause
    exit /b 1
)

REM 检查 workbench.html 中是否已注入
findstr /c:"%INJECTION_MARKER%" "%WORKBENCH_HTML%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [检测] 汉化脚本未注入，正在注入...
    echo.
    python "%HANHUA_SCRIPT%"
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 汉化注入失败，尝试直接启动 Cursor...
    ) else (
        echo.
        echo [成功] 汉化脚本注入完成
    )
) else (
    echo [检测] 汉化脚本已注入，跳过注入步骤
    REM 静默更新 JS 文件（字典可能有更新）
    python "%HANHUA_SCRIPT%" >nul 2>&1
)

echo.
echo [启动] 正在启动 Cursor...
::start "" "%CURSOR_EXE%" --user-data-dir="%CURSOR_USER_DIR%"
cmdow @ /hid
start "" "%CURSOR_EXE%" --user-data-dir="%CURSOR_USER_DIR%"

echo [完成] Cursor 已启动

