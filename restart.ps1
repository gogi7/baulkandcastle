# Baulk & Castle Restart Script
# Stops all servers, clears cache, then starts fresh

$projectRoot = $PSScriptRoot

Write-Host "=== Baulk & Castle Restart ===" -ForegroundColor Cyan
Write-Host ""

# Run stop script
& "$projectRoot\stop.ps1"

Write-Host ""
Write-Host "Waiting for processes to fully terminate..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

# Run start script
& "$projectRoot\start.ps1"
