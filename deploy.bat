@echo off
set GIT="C:\Program Files\Git\bin\git.exe"
title TON Quant Deploy

cd /d "%~dp0"

echo.
echo ===================================
echo   TON Quant - Deploy
echo ===================================
echo.

for %%L in ("index.lock" "HEAD.lock" "refs\heads\main.lock") do (
    if exist ".git\%%~L" (
        echo Removing stale .git\%%~L ...
        del /f /q ".git\%%~L"
    )
)

%GIT% status --short
echo.

echo === Integrity check (no truncated HTML) ===
set BAD=0
for %%F in (*.html) do (
    findstr /c:"</html>" "%%F" >nul
    if errorlevel 1 (
        echo   TRUNCATED: %%F  ^(missing ^</html^>^) - deploy aborted
        set BAD=1
    )
)
if %BAD%==1 (
    echo.
    echo ===================================
    echo   ERROR - truncated file^(s^) detected, deploy aborted
    echo   Re-save the file^(s^) and run deploy again
    echo ===================================
    echo.
    pause
    exit /b 1
)
echo   All HTML files OK
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
    echo   https://xpyct1337.github.io/ton-quant/
    echo ===================================
) else (
    echo.
    echo ===================================
    echo   ERROR - check SSH or connection
    echo ===================================
)

echo.
pause
