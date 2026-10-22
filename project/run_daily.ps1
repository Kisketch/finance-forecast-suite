$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
py scripts\daily_update.py @args
