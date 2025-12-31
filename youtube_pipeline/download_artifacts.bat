@echo off
REM Simple batch script to download latest artifacts
REM Usage: download_artifacts.bat [GITHUB_TOKEN]

set GITHUB_TOKEN=%1
if "%GITHUB_TOKEN%"=="" (
    echo Checking for GITHUB_TOKEN environment variable...
    if not defined GITHUB_TOKEN (
        echo Error: GitHub token required
        echo Usage: download_artifacts.bat YOUR_GITHUB_TOKEN
        echo Or set GITHUB_TOKEN environment variable
        echo.
        echo Create a token at: https://github.com/settings/tokens
        exit /b 1
    )
)

echo Downloading latest artifacts...
echo Download location will be read from download_config.json if it exists
echo.

python download_artifacts.py --latest

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Download completed successfully!
) else (
    echo.
    echo Download failed. Check the error messages above.
)

pause

