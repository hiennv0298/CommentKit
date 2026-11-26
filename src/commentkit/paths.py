"""CommentKit để mọi thứ ở đâu.

home()  dữ liệu của người dùng: .env, config.local.json, inbox, backgrounds, output, state, tts.
        - biến môi trường COMMENTKIT_HOME nếu có;
        - chạy từ mã nguồn (có pyproject.toml cạnh src/): chính thư mục dự án;
        - bản cài đặt: %LOCALAPPDATA%/CommentKit (cập nhật hay gỡ app không đụng tới).
PKG     thư mục gói commentkit (config.json mặc định, webui, tts_vieneu.py).
"""
import os
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # bản app không có console: không bật cửa sổ đen


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    return Path(sys.executable).resolve().parent if frozen() else PKG


def home() -> Path:
    env = os.environ.get("COMMENTKIT_HOME")
    if env:
        h = Path(env)
    else:
        repo = PKG.parent.parent
        if not frozen() and (repo / "pyproject.toml").is_file():
            h = repo
        else:
            h = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "CommentKit"
    h.mkdir(parents=True, exist_ok=True)
    return h


def add_bundled_tools() -> None:
    """Bản cài đặt có ffmpeg/ffprobe trong <thư mục app>/ffmpeg: đưa lên đầu PATH (tiến trình con cũng dùng được).
    Thư mục Links của winget thêm vào cuối, cho ffmpeg cài sau khi mở Windows."""
    parts = os.environ.get("PATH", "").split(os.pathsep)
    bundled = exe_dir() / "ffmpeg"
    if bundled.is_dir() and str(bundled) not in parts:
        parts.insert(0, str(bundled))
    links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if links.is_dir() and str(links) not in parts:
        parts.append(str(links))
    os.environ["PATH"] = os.pathsep.join(parts)
