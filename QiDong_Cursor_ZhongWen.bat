@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title Cursor Launcher

echo ============================================================
echo   Cursor Launcher
echo   Auto inject translation script, then start Cursor
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "HANHUA_SCRIPT=%SCRIPT_DIR%CursorHanHua_GongJu.py"
set "INJECTION_MARKER=CURSOR_HANHUA_INJECTION"
set "CURSOR_USER_DIR=%APPDATA%\Cursor"

if defined CURSOR_USER_DATA_DIR set "CURSOR_USER_DIR=%CURSOR_USER_DATA_DIR%"

if defined CURSOR_INSTALL_DIR (
    if not exist "%CURSOR_INSTALL_DIR%\Cursor.exe" set "CURSOR_INSTALL_DIR="
)

if not defined CURSOR_INSTALL_DIR (
    if defined CURSOR_ROOT (
        if exist "%CURSOR_ROOT%\Cursor.exe" set "CURSOR_INSTALL_DIR=%CURSOR_ROOT%"
    )
)

if not defined CURSOR_INSTALL_DIR call :DetectCursorDir

if not defined CURSOR_INSTALL_DIR (
    echo [ERROR] Cursor install directory not found.
    echo [TIP] Set CURSOR_INSTALL_DIR or install Cursor in a common path.
    pause
    exit /b 1
)

set "CURSOR_EXE=%CURSOR_INSTALL_DIR%\Cursor.exe"
set "WORKBENCH_HTML=%CURSOR_INSTALL_DIR%\resources\app\out\vs\code\electron-sandbox\workbench\workbench.html"

if not exist "%HANHUA_SCRIPT%" (
    echo [ERROR] Translation script not found: %HANHUA_SCRIPT%
    pause
    exit /b 1
)

if not exist "%CURSOR_EXE%" (
    echo [ERROR] Cursor.exe not found: %CURSOR_EXE%
    pause
    exit /b 1
)

if not exist "%WORKBENCH_HTML%" (
    echo [ERROR] workbench.html not found: %WORKBENCH_HTML%
    echo [TIP] Check whether CURSOR_INSTALL_DIR is correct.
    pause
    exit /b 1
)

findstr /c:"%INJECTION_MARKER%" "%WORKBENCH_HTML%" >nul 2>&1
if errorlevel 1 (
    echo [CHECK] Not injected, running translation...
    python "%HANHUA_SCRIPT%"
    if errorlevel 1 (
        echo.
        echo [ERROR] Translation failed, still trying to start Cursor...
    ) else (
        echo.
        echo [OK] Translation completed
    )
) else (
    echo [CHECK] Already injected, starting Cursor directly
)

echo.
echo [START] Launching Cursor...
start "" "%CURSOR_EXE%" --user-data-dir="%CURSOR_USER_DIR%"
echo [DONE] Cursor launched
exit /b 0

:DetectCursorDir
for %%D in (
    "%LOCALAPPDATA%\Programs\Cursor"
    "%PROGRAMFILES%\Cursor"
    "%PROGRAMFILES(X86)%\Cursor"
) do (
    if not defined CURSOR_INSTALL_DIR if exist "%%~fD\Cursor.exe" if exist "%%~fD\resources\app" (
        set "CURSOR_INSTALL_DIR=%%~fD"
    )
)
exit /b 0
