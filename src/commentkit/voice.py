"""Giọng đọc VieNeu-TTS, cài khi dùng lần đầu.

VieNeu cần onnxruntime, librosa, gradio... (vài trăm MB) và model ~600 MB, quá nặng để nhét vào bộ cài.
Nút "Cài giọng đọc" tải uv (trình cài gói Python của Astral, kiểm tra SHA-256), để uv tải một Python 3.12
riêng rồi cài vieneu vào <home>/tts/venv. Model tải về <home>/tts/hf. Không cài gì ra ngoài hệ thống.

Cũng có thể trỏ Cài đặt > "Python của VieNeu" vào một venv đã có sẵn gói vieneu.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .paths import NO_WINDOW, PKG, home

UV_URL = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
PACKAGES = ["vieneu==3.8.5"]
TTS_SCRIPT = PKG / "tts_vieneu.py"
CHECK = "import importlib.util as u; print('found' if u.find_spec('vieneu') else 'missing')"


def tts_dir() -> Path:
    return home() / "tts"


def managed_python() -> Path:
    return tts_dir() / "venv" / "Scripts" / "python.exe"


def default_hf_home() -> Path:
    return tts_dir() / "hf"


def check_python(py) -> dict:
    """{'ok': bool, 'error': str}: python này có gói vieneu không."""
    py = Path(py) if py else None
    if not py or not py.is_file():
        return {"ok": False, "error": f"không thấy {py}" if py else "chưa cài"}
    try:
        r = subprocess.run([str(py), "-I", "-c", CHECK], capture_output=True, text=True, timeout=60,
                           creationflags=NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "error": str(e)}
    if "found" in r.stdout:
        return {"ok": True, "error": ""}
    if "missing" in r.stdout:
        return {"ok": False, "error": "python này chưa có gói vieneu"}
    return {"ok": False, "error": (r.stderr or r.stdout).strip()[-200:]}


def status(cfg) -> dict:
    py = cfg["tts"]["python"]
    return {**check_python(py), "python": py, "managed": Path(py) == managed_python(),
            "hf_home": cfg["tts"]["hf_home"], "managed_path": str(managed_python())}


def _run(cmd, env, on_line):
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                         text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    tail = []
    for line in p.stdout:
        line = line.rstrip()
        if line:
            tail = (tail + [line])[-15:]
            on_line("  " + line[:200])
    if p.wait() != 0:
        raise RuntimeError(f"{Path(str(cmd[0])).name} lỗi ({p.returncode}): " + " | ".join(tail[-3:]))


def _uv(on_line) -> Path:
    exe = tts_dir() / "bin" / "uv.exe"
    if exe.is_file():
        return exe
    found = shutil.which("uv")
    if found:
        return Path(found)
    exe.parent.mkdir(parents=True, exist_ok=True)
    archive = exe.parent / "uv.zip"
    on_line("Tải uv (trình cài gói Python, khoảng 20 MB)...")
    expected = urllib.request.urlopen(UV_URL + ".sha256", timeout=30).read().decode().split()[0].lower()
    digest = hashlib.sha256()
    with urllib.request.urlopen(UV_URL, timeout=120) as resp, open(archive, "wb") as out:
        while chunk := resp.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError("File uv tải về không khớp SHA-256, đã xoá cho an toàn.")
    with zipfile.ZipFile(archive) as zf:
        for name in zf.namelist():
            if Path(name).name == "uv.exe":
                exe.write_bytes(zf.read(name))
    archive.unlink(missing_ok=True)
    if not exe.is_file():
        raise RuntimeError("Không thấy uv.exe trong file tải về.")
    return exe


def warm_up(cfg, on_line) -> None:
    """Đọc thử một câu: lần đầu VieNeu tải model (~600 MB) về hf_home."""
    on_line("Tải model giọng đọc và đọc thử một câu (lần đầu khoảng 600 MB)...")
    with tempfile.TemporaryDirectory() as tmp:
        job = Path(tmp) / "job.json"
        voice = cfg["characters"]["nguoi_dang"]["voice"]
        job.write_text('{"gap": 0.3, "lines": [{"id": "00", "tts": "Xin chào, giọng đọc đã sẵn sàng.", '
                       '"voice": "%s", "fx": ""}]}' % voice, encoding="utf-8")
        env = dict(os.environ, HF_HOME=cfg["tts"]["hf_home"], PYTHONIOENCODING="utf-8")
        _run([cfg["tts"]["python"], "-I", TTS_SCRIPT, job, Path(tmp) / "out"], env, on_line)


def install(cfg, on_line=print) -> dict:
    """Tạo <home>/tts/venv có vieneu rồi đọc thử. Mất vài phút."""
    uv = _uv(on_line)
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(tts_dir() / "python"), UV_CACHE_DIR=str(tts_dir() / "cache"))
    if not managed_python().is_file():
        on_line("Tạo Python 3.12 riêng cho giọng đọc...")
        _run([uv, "venv", "--python", "3.12", tts_dir() / "venv"], env, on_line)
    on_line("Cài VieNeu-TTS (vài trăm MB)...")
    _run([uv, "pip", "install", "--python", managed_python(), *PACKAGES], env, on_line)
    res = check_python(managed_python())
    if not res["ok"]:
        raise RuntimeError("Đã cài nhưng chưa chạy được: " + res["error"])
    cfg["tts"]["python"] = str(managed_python())
    warm_up(cfg, on_line)
    on_line("✔ Giọng đọc đã sẵn sàng.")
    return res
