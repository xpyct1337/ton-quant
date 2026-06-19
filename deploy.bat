@echo off
set GIT="C:\Program Files\Git\bin\git.exe"
title TON Quant Deploy

cd /d "%~dp0"

echo.
echo ===================================
echo   TON Quant - Deploy
echo ===================================
echo.

if exist ".git\index.lock" (
    echo Removing stale .git\index.lock ...
    del /f /q ".git\index.lock"
)

%GIT% status --short
echo.

echo === Staging and committing local changes ===
%GIT% add -A
%GIT% commit -m "update"
echo.

echo === Pulling latest from GitHub (rebase) ===
%GIT% pull --rebase --autostash origin main
if not %ERRORLEVEL%==0 (
    echo.
    echo ===================================
    echo   ERROR - git pull failed, resolve conflicts manually
    echo ===================================
    echo.
    pause
    exit /b 1
)
echo.

echo Pushing to GitHub...
%GIT% push origin main

if %ERRORLEVEL%==0 (
    echo.
    echo ===================================
    echo   SUCCESS - site will update in ~1min
    echo   https://xpyct1337.github.io
    echo ===================================
) else (
    echo.
    echo ===================================
    echo   ERROR - check SSH or connection
    echo ===================================
)

echo.
pause
