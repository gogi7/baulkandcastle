# Baulk & Castle Launcher
# Starts both backend API and frontend dev server

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Write-Host "=== Baulk & Castle Launcher ===" -ForegroundColor Cyan
Write-Host ""

# Check Python venv
if (-not (Test-Path "$projectRoot\.venv\Scripts\python.exe")) {
    Write-Host "ERROR: Python venv not found. Run: py -3.12 -m venv .venv && pip install -e ." -ForegroundColor Red
    exit 1
}

# Check frontend node_modules
if (-not (Test-Path "$projectRoot\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location "$projectRoot\frontend"
    npm install
    Pop-Location
}

Write-Host "Starting Backend API (http://127.0.0.1:5000)..." -ForegroundColor Green

# Start backend in a new window that stays open
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; .\.venv\Scripts\Activate.ps1; python -m baulkandcastle.cli.api_server"

Start-Sleep -Seconds 2

Write-Host "Starting Frontend (http://localhost:5173)..." -ForegroundColor Green

# Start frontend in a new window that stays open
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "=== Servers starting in separate windows ===" -ForegroundColor Cyan
Write-Host "Backend API: http://127.0.0.1:5000/api/health" -ForegroundColor White
Write-Host "Frontend:    http://localhost:3000 (or 3001 if 3000 is busy)" -ForegroundColor White
Write-Host ""
Write-Host "Check the new terminal windows for any errors." -ForegroundColor Yellow

# Open browser after a short delay
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"
