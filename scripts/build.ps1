# Build the Windows downloads:
#   dist\CommentKit\                     app folder (CommentKitApp.exe, commentkit.exe, Python runtime, ffmpeg)
#   dist\CommentKit-<ver>-portable.zip   unzip-and-run version
#   dist\CommentKit-Setup-<ver>.exe      installer (needs Inno Setup 6: winget install JRSoftware.InnoSetup)
#
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 [-DownloadFfmpeg] [-SkipInstaller]
#
# -DownloadFfmpeg  bundle BtbN's "gpl" ffmpeg build (checked against its SHA-256)
#                  instead of copying ffmpeg/ffprobe found on PATH. CI uses this.
# ASCII-only on purpose (Windows PowerShell 5.1 reads BOM-less files as ANSI).

$ErrorActionPreference = "Stop"
$DownloadFfmpeg = ($args -contains "-DownloadFfmpeg")
$SkipInstaller = ($args -contains "-SkipInstaller")
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

# 1. Clean build environment
$venv = Join-Path $Root ".venv-build"
$py = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv $venv }
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet . "pyinstaller>=6.10"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
$version = (& $py -c "import commentkit; print(commentkit.__version__)").Trim()
Write-Host "Building CommentKit $version"

# 2. PyInstaller (one folder: faster start-up than one-file, and AV scanners like it better).
#    The spec builds commentkit.exe (command line) and CommentKitApp.exe (app window) side by side.
& $py -m PyInstaller --noconfirm --clean --distpath dist --workpath build scripts\commentkit.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
$app = Join-Path $Root "dist\CommentKit"

# 3. Bundle ffmpeg + ffprobe next to the exe (commentkit.paths puts <exe dir>\ffmpeg first on PATH)
$ffDir = Join-Path $app "ffmpeg"
New-Item -ItemType Directory -Force $ffDir | Out-Null
if ($DownloadFfmpeg) {
    # BtbN "gpl" build: has librubberband, which the deeper "uncle" voice effect needs.
    $rel = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"
    $name = "ffmpeg-master-latest-win64-gpl.zip"
    $zip = Join-Path $env:TEMP "commentkit-ffmpeg.zip"
    Invoke-WebRequest "$rel/$name" -OutFile $zip -UseBasicParsing
    # served as application/octet-stream, so save it to a file and read it as text
    $sumsFile = Join-Path $env:TEMP "commentkit-ffmpeg-checksums.txt"
    Invoke-WebRequest "$rel/checksums.sha256" -OutFile $sumsFile -UseBasicParsing
    $line = Get-Content $sumsFile | Where-Object { $_.Trim().EndsWith("  $name") } | Select-Object -First 1
    Remove-Item $sumsFile -ErrorAction SilentlyContinue
    if (-not $line) { throw "no checksum for $name" }
    $expected = ($line.Trim() -split "\s+")[0].ToLower()
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($expected -ne $actual) { throw "ffmpeg SHA-256 mismatch: $actual vs $expected" }
    $tmp = Join-Path $env:TEMP "commentkit-ffmpeg"
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive $zip $tmp
    Get-ChildItem $tmp -Recurse -Include ffmpeg.exe, ffprobe.exe | Copy-Item -Destination $ffDir
    Remove-Item $zip, $tmp -Recurse -Force
} else {
    foreach ($tool in "ffmpeg", "ffprobe") {
        $src = (Get-Command $tool -ErrorAction SilentlyContinue).Source
        if (-not $src) { throw "$tool not on PATH; install it or use -DownloadFfmpeg" }
        Copy-Item $src -Destination (Join-Path $ffDir "$tool.exe")
    }
}
Copy-Item README.md, LICENSE -Destination $app

# 4. Smoke test the frozen app (in a throwaway data folder)
$env:COMMENTKIT_HOME = Join-Path $env:TEMP "commentkit-smoke"
& (Join-Path $app "commentkit.exe") doctor
$code = $LASTEXITCODE
Remove-Item $env:COMMENTKIT_HOME -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item Env:\COMMENTKIT_HOME
if ($code -ne 0) { throw "commentkit.exe doctor failed" }
if (-not (Test-Path (Join-Path $app "CommentKitApp.exe"))) { throw "CommentKitApp.exe missing" }
if (-not (Get-ChildItem $app -Recurse -Filter tts_vieneu.py)) { throw "voice script missing" }
if (-not (Get-ChildItem $app -Recurse -Filter config.json | Where-Object { $_.FullName -match "commentkit" })) { throw "default config missing" }
$filters = & (Join-Path $ffDir "ffmpeg.exe") -hide_banner -filters 2>$null | Out-String
if ($filters -notmatch "rubberband") { Write-Warning "the bundled ffmpeg has no rubberband filter" }
if (-not (Get-ChildItem $app -Recurse -Filter index.html | Where-Object { $_.FullName -match "webui" })) { throw "web UI files missing" }

# 5. Portable zip
$portable = Join-Path $Root "dist\CommentKit-$version-portable.zip"
Remove-Item $portable -ErrorAction SilentlyContinue
# Antivirus often keeps freshly copied exes open for a few seconds: retry.
for ($try = 1; $try -le 6; $try++) {
    try { Compress-Archive -Path $app -DestinationPath $portable -Force -ErrorAction Stop; break }
    catch {
        if ($try -eq 6) { throw }
        Write-Host "Files still locked, retrying in 10 s ($try/5) ..."
        Start-Sleep -Seconds 10
    }
}
Write-Host "Portable: $portable"

# 6. Installer
if ($SkipInstaller) { return }
$iscc = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    Write-Warning "Inno Setup not found, skipped the installer. Install it with: winget install JRSoftware.InnoSetup"
    return
}
& $iscc "/DAppVersion=$version" (Join-Path $Root "installer\commentkit.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Write-Host "Installer: $(Join-Path $Root "dist\CommentKit-Setup-$version.exe")"
