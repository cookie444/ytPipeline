@echo off
REM Simple batch script to download latest artifacts
REM Usage: download_artifacts.bat [GITHUB_TOKEN]

set GITHUB_TOKEN=%1
if "%GITHUB_TOKEN%"=="" (
    echo Error: GitHub token required
    echo Usage: download_artifacts.bat YOUR_GITHUB_TOKEN
    echo Or set GITHUB_TOKEN environment variable
    exit /b 1
)

python download_artifacts.py --latest --output "F:\Split YT Links Project"

pause

