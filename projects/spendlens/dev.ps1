# Start SpendLens: Flask (5050) + Vite (5173)
$root = $PSScriptRoot
$flask = Join-Path $root "scripts"

Write-Host "Starting Flask on http://127.0.0.1:5050 ..."
Start-Process powershell -ArgumentList @(
  "-NoExit",
  "-Command",
  "Set-Location '$flask'; python app.py"
)

Start-Sleep -Seconds 2

Write-Host "Starting Vite on http://127.0.0.1:5173 ..."
Set-Location (Join-Path $root "frontend")
npm run dev
