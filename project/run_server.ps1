$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $root "src"
Set-Location $root
Write-Host "API: http://127.0.0.1:8765"
py -m finance_app.ui.server
