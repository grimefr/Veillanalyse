@echo off
REM =============================================================================
REM DOPPELGANGER TRACKER - Setup Script for Windows
REM =============================================================================
REM Automated setup script for Docker deployment on Windows
REM Usage: setup.bat
REM =============================================================================

setlocal enabledelayedexpansion

REM Colors are limited in CMD, so we use simple output
echo ========================================
echo Doppelganger Tracker - Setup Script
echo ========================================
echo.

REM =============================================================================
REM Check Docker Installation
REM =============================================================================

echo [INFO] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop for Windows
    echo Visit: https://docs.docker.com/desktop/install/windows-install/
    pause
    exit /b 1
)

echo [OK] Docker found
docker --version

REM Check Docker Compose
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not available
    echo Please ensure Docker Desktop is properly installed
    pause
    exit /b 1
)

echo [OK] Docker Compose found
docker compose version
echo.

REM =============================================================================
REM Environment File Setup
REM =============================================================================

echo ========================================
echo Environment Configuration
echo ========================================
echo.

if exist .env (
    echo [WARNING] .env file already exists
    set /p RECREATE="Do you want to backup and recreate it? (y/N): "
    if /i "!RECREATE!"=="y" (
        set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
        set TIMESTAMP=!TIMESTAMP: =0!
        copy .env .env.backup.!TIMESTAMP! >nul
        echo [OK] Backup created: .env.backup.!TIMESTAMP!
    ) else (
        echo [INFO] Using existing .env file
        set ENV_EXISTS=1
    )
)

if not defined ENV_EXISTS (
    echo [INFO] Creating .env file from template...
    copy .env.example .env >nul

    REM Generate a simple secure password (Windows doesn't have openssl by default)
    set "PASSWORD=DoppelTracker_%RANDOM%%RANDOM%%RANDOM%"

    REM Use PowerShell to replace password in .env
    powershell -Command "(Get-Content .env) -replace 'your_secure_password_here', '%PASSWORD%' | Set-Content .env"

    echo [OK] .env file created with secure PostgreSQL password
)

echo.

REM =============================================================================
REM Telegram Configuration
REM =============================================================================

echo ========================================
echo Telegram API Configuration
echo ========================================
echo.
echo [INFO] Telegram collection requires API credentials
echo [INFO] Get them from: https://my.telegram.org/apps
echo.

set /p CONFIG_TELEGRAM="Do you want to configure Telegram now? (y/N): "
if /i "!CONFIG_TELEGRAM!"=="y" (
    set /p TELEGRAM_API_ID="Enter Telegram API ID: "
    set /p TELEGRAM_API_HASH="Enter Telegram API Hash: "

    REM Use PowerShell to update .env
    powershell -Command "(Get-Content .env) -replace 'TELEGRAM_API_ID=.*', 'TELEGRAM_API_ID=!TELEGRAM_API_ID!' | Set-Content .env"
    powershell -Command "(Get-Content .env) -replace 'TELEGRAM_API_HASH=.*', 'TELEGRAM_API_HASH=!TELEGRAM_API_HASH!' | Set-Content .env"

    echo [OK] Telegram credentials configured
) else (
    echo [WARNING] Skipping Telegram configuration
    echo [INFO] You can configure it later by editing .env
)

echo.

REM =============================================================================
REM Directory Setup
REM =============================================================================

echo ========================================
echo Creating Required Directories
echo ========================================
echo.

if not exist data mkdir data
if not exist logs mkdir logs
if not exist exports mkdir exports
if not exist exports\graphs mkdir exports\graphs
if not exist exports\reports mkdir exports\reports
if not exist exports\data mkdir exports\data

echo [OK] Created data directories
echo.

REM =============================================================================
REM Docker Build
REM =============================================================================

echo ========================================
echo Docker Build
echo ========================================
echo.

set /p BUILD_NOW="Do you want to build Docker images now? (y/N): "
if /i "!BUILD_NOW!"=="y" (
    echo [INFO] Building Docker images (this may take several minutes)...
    docker compose build --no-cache
    if errorlevel 1 (
        echo [ERROR] Docker build failed
        pause
        exit /b 1
    )
    echo [OK] Docker images built successfully
) else (
    echo [WARNING] Skipping Docker build
    echo [INFO] Run 'docker compose build' manually when ready
)

echo.

REM =============================================================================
REM Summary
REM =============================================================================

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo [OK] Environment configured successfully
echo.
echo Next steps:
echo.
echo   1. Review your configuration:
echo      type .env
echo.
echo   2. Start the services:
echo      docker compose up -d
echo.
echo   3. Check service status:
echo      docker compose ps
echo.
echo   4. View logs:
echo      docker compose logs -f
echo.
echo   5. Access the dashboard:
echo      http://localhost:8501
echo.
echo   6. Stop the services:
echo      docker compose down
echo.
echo Additional commands:
echo.
echo   * Initialize database only:
echo     docker compose run --rm db-init
echo.
echo   * Run analyzer (with profile):
echo     docker compose --profile analysis up analyzer
echo.
echo   * View collector logs:
echo     docker compose logs -f collector
echo.
echo ========================================
echo Happy Tracking!
echo ========================================
echo.

pause
