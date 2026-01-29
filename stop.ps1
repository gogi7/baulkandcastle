# Baulk & Castle Stop Script
# Stops backend API and frontend servers, clears Python cache

$ErrorActionPreference = "SilentlyContinue"
$projectRoot = $PSScriptRoot

Write-Host "=== Baulk & Castle Stop Script ===" -ForegroundColor Cyan
Write-Host ""

# Kill Python processes running our API server
Write-Host "Stopping Backend API server..." -ForegroundColor Yellow
$pythonProcesses = Get-WmiObject Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*baulkandcastle*" -or $_.CommandLine -like "*api_server*" }

$backendKilled = 0
foreach ($proc in $pythonProcesses) {
    try {
        Stop-Process -Id $proc.ProcessId -Force
        $backendKilled++
    } catch { }
}

if ($backendKilled -gt 0) {
    Write-Host "  Killed $backendKilled backend process(es)" -ForegroundColor Green
} else {
    Write-Host "  No backend processes found" -ForegroundColor Gray
}

# Kill Node processes running on typical dev ports (Vite uses 5173, 3000, etc.)
Write-Host "Stopping Frontend dev server..." -ForegroundColor Yellow
$nodeProcesses = Get-WmiObject Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -like "*vite*" -or $_.CommandLine -like "*$projectRoot\frontend*" }

$frontendKilled = 0
foreach ($proc in $nodeProcesses) {
    try {
        Stop-Process -Id $proc.ProcessId -Force
        $frontendKilled++
    } catch { }
}

if ($frontendKilled -gt 0) {
    Write-Host "  Killed $frontendKilled frontend process(es)" -ForegroundColor Green
} else {
    Write-Host "  No frontend processes found" -ForegroundColor Gray
}

# Clear Python cache
Write-Host "Clearing Python cache..." -ForegroundColor Yellow
$cacheDirs = Get-ChildItem -Path $projectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*\.venv\*" }

$cacheCleared = 0
foreach ($dir in $cacheDirs) {
    try {
        Remove-Item -Path $dir.FullName -Recurse -Force
        $cacheCleared++
    } catch { }
}

if ($cacheCleared -gt 0) {
    Write-Host "  Cleared $cacheCleared __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "  No cache directories found" -ForegroundColor Gray
}

# Also clear any .pyc files that might be loose
$pycFiles = Get-ChildItem -Path "$projectRoot\src" -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
foreach ($file in $pycFiles) {
    try {
        Remove-Item -Path $file.FullName -Force
    } catch { }
}

Write-Host ""
Write-Host "=== Stop Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run start.bat to restart with fresh code." -ForegroundColor White
Write-Host ""
