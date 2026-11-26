# Cai CommentKit bang 1 lenh (PowerShell):
#   irm https://raw.githubusercontent.com/hiennv0298/CommentKit/main/get.ps1 | iex
# Cai vao thu muc khac: dat $env:COMMENTKIT_DIR = "D:\CommentKit" truoc khi chay.
# Chay lai lenh nay de cap nhat: code moi duoc chep de, giu nguyen .env, config.local.json, inbox, output, backgrounds.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Dir = if ($env:COMMENTKIT_DIR) { $env:COMMENTKIT_DIR } else { Join-Path $env:USERPROFILE "CommentKit" }
$Zip = Join-Path $env:TEMP "CommentKit-main.zip"
$Tmp = Join-Path $env:TEMP ("CommentKit-" + [guid]::NewGuid().ToString("N"))

Write-Host "Tai CommentKit ve $Dir ..." -ForegroundColor Cyan
Invoke-WebRequest "https://github.com/hiennv0298/CommentKit/archive/refs/heads/main.zip" -OutFile $Zip -UseBasicParsing
Expand-Archive $Zip -DestinationPath $Tmp -Force
$Src = Join-Path $Tmp "CommentKit-main"
New-Item -ItemType Directory -Force $Dir | Out-Null
Copy-Item (Join-Path $Src "*") $Dir -Recurse -Force
Remove-Item $Zip, $Tmp -Recurse -Force -ErrorAction SilentlyContinue

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dir "install.ps1")
