# CommentKit installer (Windows 10/11). Chay bang install.bat, hoac:
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-VieneuPython <python.exe>] [-HfHome <thu muc>] [-SkipTts] [-SkipTest] [-NoShortcut]
#   -VieneuPython : dung lai VieNeu-TTS da cai san (python.exe cua venv co goi vieneu), khoi cai lai
#   -HfHome       : thu muc cache model HuggingFace (mac dinh .cache\hf trong thu muc tool)
param(
    [string]$VieneuPython = "",
    [string]$HfHome = "",
    [switch]$SkipTts,
    [switch]$SkipTest,
    [switch]$NoShortcut
)
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "    !!  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host ""; Write-Host "LOI: $m" -ForegroundColor Red; exit 1 }
function Update-PathEnv {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                "$env:LOCALAPPDATA\Microsoft\WinGet\Links"
}
function Test-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Install-Winget($id, $what) {
    if (-not (Test-Cmd winget)) { Fail "Khong co winget de cai $what. Hay tu cai $what roi chay lai install.bat." }
    Write-Host "    Dang cai $what bang winget ($id)..."
    winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements
    Update-PathEnv
}
function Find-Python {
    if (Test-Cmd py) {
        foreach ($v in "3.12", "3.11", "3.10") {
            $exe = (& py "-$v" -c "import sys; print(sys.executable)" 2>$null | Out-String).Trim()
            if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe }
        }
    }
    foreach ($c in @("python", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $ver = (& $cmd.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -eq 0 -and @("3.10", "3.11", "3.12") -contains $ver) { return $cmd.Source }
    }
    return $null
}
function Invoke-Pip($py, $req) {
    & $py -m pip install --disable-pip-version-check -q --upgrade pip
    & $py -m pip install --disable-pip-version-check -r $req
    if ($LASTEXITCODE -ne 0) { Fail "pip install $req that bai (xem loi phia tren)." }
}

Write-Host "CommentKit - cai dat tai $Root" -ForegroundColor White
Update-PathEnv

# 1. Python
Step "Python 3.10 - 3.12"
$Py = Find-Python
if (-not $Py) {
    Install-Winget "Python.Python.3.12" "Python 3.12"
    $Py = Find-Python
    if (-not $Py) { Fail "Da cai Python nhung chua tim thay. Dong cua so nay, mo lai install.bat." }
}
Ok $Py

# 2. ffmpeg
Step "ffmpeg"
if (-not (Test-Cmd ffmpeg)) { Install-Winget "Gyan.FFmpeg" "ffmpeg" }
if (-not (Test-Cmd ffmpeg)) { Fail "Chua tim thay ffmpeg. Dong cua so nay, mo lai install.bat." }
Ok (Get-Command ffmpeg).Source
$filters = (& ffmpeg -hide_banner -filters 2>$null | Out-String)
if ($filters -notmatch "rubberband") { Warn "ffmpeg nay khong co bo loc rubberband: giong 'ong_chu' se khong doi cao do. Nen dung ban 'full' (winget install Gyan.FFmpeg)." }

# 3. App venv
Step "Moi truong Python cho app (.venv)"
$AppPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $AppPy)) {
    & $Py -m venv (Join-Path $Root ".venv")
    if (-not (Test-Path $AppPy)) { Fail "Khong tao duoc .venv" }
}
Invoke-Pip $AppPy (Join-Path $Root "requirements.txt")
Ok "Flask, Pillow, requests"

# 4. Thu muc + .env
Step "Thu muc va file cau hinh"
foreach ($d in "inbox", "backgrounds", "output", "state") { New-Item -ItemType Directory -Force (Join-Path $Root $d) | Out-Null }
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Ok "Tao .env (nhap API key trong Cai dat cua giao dien)"
} else { Ok ".env da co, giu nguyen" }

# 5. VieNeu-TTS
Step "Giong doc VieNeu-TTS"
$SetLocal = Join-Path $Root "tools\setup_local.py"
if ($VieneuPython) {
    if (-not (Test-Path $VieneuPython)) { Fail "Khong thay $VieneuPython" }
    & $VieneuPython -I -c "import vieneu" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "$VieneuPython khong co goi vieneu" }
    & $AppPy $SetLocal --tts-python $VieneuPython
    Ok "Dung lai VieNeu tai $VieneuPython"
} elseif ($SkipTts) {
    Warn "Bo qua cai VieNeu (-SkipTts)"
} else {
    $TtsPy = Join-Path $Root ".venv-tts\Scripts\python.exe"
    if (-not (Test-Path $TtsPy)) { & $Py -m venv (Join-Path $Root ".venv-tts") }
    if (-not (Test-Path $TtsPy)) { Fail "Khong tao duoc .venv-tts" }
    Write-Host "    Dang cai goi vieneu (lan dau co the mat vai phut)..."
    Invoke-Pip $TtsPy (Join-Path $Root "requirements-tts.txt")
    & $AppPy $SetLocal --tts-python ".venv-tts/Scripts/python.exe"
    Ok "vieneu da cai trong .venv-tts"
}
if ($HfHome) {
    & $AppPy $SetLocal --hf-home $HfHome
    Ok "Cache model: $HfHome"
}

# 6. Claude CLI (khong bat buoc)
Step "Claude Code CLI (khong bat buoc)"
if (Test-Cmd claude) { Ok "Co claude. Neu chua dang nhap: mo terminal, chay claude roi go /login" }
else { Warn "Khong co claude CLI. Van dung duoc bang Gemini (mien phi) hoac ChatGPT: chon trong Cai dat cua giao dien." }

# 7. Shortcut
if (-not $NoShortcut) {
    Step "Shortcut tren Desktop"
    try {
        $ws = New-Object -ComObject WScript.Shell
        $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "CommentKit.lnk"))
        $lnk.TargetPath = Join-Path $Root "start-ui.bat"
        $lnk.WorkingDirectory = $Root
        $lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,18"
        $lnk.Save()
        Ok "Desktop\CommentKit.lnk"
    } catch { Warn "Khong tao duoc shortcut: $_" }
}

# 8. Chay thu: doc giong + dung 1 video mau (lan dau se tai model ~600 MB)
if (-not $SkipTest -and -not $SkipTts) {
    Step "Chay thu: dung video mau samples\demo_script.json (lan dau tai model giong doc ~600 MB)"
    $env:PYTHONIOENCODING = "utf-8"
    & $AppPy (Join-Path $Root "run.py") --script (Join-Path $Root "samples\demo_script.json")
    if ($LASTEXITCODE -ne 0) { Fail "Chay thu that bai (xem loi phia tren)." }
    Ok "Video mau nam trong thu muc output"
}

Write-Host ""
Write-Host "XONG. Mo giao dien: nhap dup CommentKit tren Desktop (hoac start-ui.bat)." -ForegroundColor Green
Write-Host "Nho them video gameplay vao thu muc backgrounds (hoac them tren giao dien)." -ForegroundColor Green
