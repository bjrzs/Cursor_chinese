cmdow @ /hid

@echo off
chcp 65001 >nul 2>&1
title Cursor 中文版启动器

echo ============================================================
echo   Cursor 中文版启动器
echo   功能：自动注入汉化脚本后启动 Cursor
echo ============================================================
echo.

REM ============================================================
REM 用户配置区域 - 默认按本脚本所在位置自动推断 Cursor 根目录
REM 如需手动指定，可在运行前设置：
REM   set CURSOR_INSTALL_DIR=D:\Tools\cursor
REM   set CURSOR_USER_DATA_DIR=D:\Tools\cursor\user
REM ============================================================
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "AUTO_CURSOR_ROOT=%%~fI"
if not defined CURSOR_INSTALL_DIR set "CURSOR_INSTALL_DIR=%AUTO_CURSOR_ROOT%"
if not defined CURSOR_USER_DATA_DIR set "CURSOR_USER_DATA_DIR=%APPDATA%\Cursor"

set "CURSOR_EXE=%CURSOR_INSTALL_DIR%\Cursor.exe"
set "CURSOR_USER_DIR=%CURSOR_USER_DATA_DIR%"
set "HANHUA_SCRIPT=%SCRIPT_DIR%CursorHanHua_GongJu.py"
set "WORKBENCH_HTML=%CURSOR_INSTALL_DIR%\resources\app\out\vs\code\electron-sandbox\workbench\workbench.html"
set "INJECTION_MARKER=CURSOR_HANHUA_INJECTION"
REM ============================================================

if not exist "%CURSOR_EXE%" (
    echo [错误] 未找到 Cursor: %CURSOR_EXE%
    echo [提示] 请修改本文件中的 CURSOR_EXE 路径
    pause
    exit /b 1
)

if not exist "%HANHUA_SCRIPT%" (
    echo [错误] 未找到汉化脚本: %HANHUA_SCRIPT%
    pause
    exit /b 1
)

if not exist "%WORKBENCH_HTML%" (
    echo [错误] 未找到 workbench.html: %WORKBENCH_HTML%
    echo [提示] 请确认 Cursor 安装目录是否正确
    pause
    exit /b 1
)

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
    python "%HANHUA_SCRIPT%" >nul 2>&1
)

echo.
echo [启动] 正在启动 Cursor...
start "" "%CURSOR_EXE%" --user-data-dir="%CURSOR_USER_DIR%"

echo [完成] Cursor 已启动
