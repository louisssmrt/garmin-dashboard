# run.ps1 - refresh data + lance le serveur + ouvre le dashboard
# Usage : .\run.ps1            # 90j (defaut)
#         .\run.ps1 -Days 30   # fenetre custom

param(
  [int]$Days = 90,
  [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host "[1/3] Refresh data Supabase ($Days j)..." -ForegroundColor Cyan
python build_data.py --days $Days
if ($LASTEXITCODE -ne 0) { throw "build_data.py a echoue" }

Write-Host "[2/3] Demarrage serveur http://localhost:$Port ..." -ForegroundColor Cyan
$server = Start-Process -FilePath "python" -ArgumentList "-m","http.server",$Port -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 1

Write-Host "[3/3] Ouverture navigateur..." -ForegroundColor Cyan
Start-Process "http://localhost:$Port/index.html"

Write-Host ""
Write-Host "Dashboard ouvert. Ctrl+C ici pour arreter le serveur." -ForegroundColor Green
try {
  Wait-Process -Id $server.Id
} finally {
  if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
  Write-Host "Serveur arrete." -ForegroundColor Yellow
}
