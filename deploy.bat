@echo off
set GIT="C:\Program Files\Git\bin\git.exe"
title TON Quant Deploy

cd /d "%~dp0"

echo.
echo ===================================
echo   TON Quant - Deploy
echo ===================================
echo.

%GIT% status --short
echo.

%GIT% add -A
%GIT% commit -m "update"

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
