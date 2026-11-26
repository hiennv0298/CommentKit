"""Tìm bản CommentKit mới trên GitHub và cài đặt.

* App hỏi https://api.github.com/repos/<repo>/releases/latest tối đa 1 lần/giờ (không cần tài khoản,
  không gửi gì về người dùng) và nhớ câu trả lời; khi app mở lâu thì vài tiếng hỏi lại một lần.
* Bản cài bằng bộ cài cập nhật được bằng 1 nút: tải CommentKit-Setup-*.exe mới, đối chiếu với
  SHA256SUMS.txt của release, chạy im lặng, bộ cài mở lại app khi xong (xem installer/commentkit.iss).
* Bản portable và bản chạy từ mã nguồn thì được chỉ chỗ tải bản mới.

COMMENTKIT_REPO (owner/name) và COMMENTKIT_UPDATE_URL (URL trả về JSON của một release) đổi nơi đọc
release, dùng cho bản fork và khi test.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__
from .paths import home

REPO = os.environ.get("COMMENTKIT_REPO", "hiennv0298/CommentKit")
CHECK_EVERY = 3600          # câu trả lời đã nhớ được dùng lại trong 1 giờ (mở lại app không hỏi GitHub lại)
RECHECK_EVERY = 6 * 3600    # khi app mở liên tục
STATE_FILE = "update-check.json"
_lock = threading.Lock()
PROGRESS = {"phase": "idle", "progress": 0.0, "error": ""}   # idle | downloading | verifying | restarting | error


class UpdateError(RuntimeError):
    pass


def parse_version(text):
    nums = [int(x) for x in re.findall(r"\d+", str(text).lstrip("vV").split("-")[0].split("+")[0])[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def install_mode():
    """installer | portable | python (chạy từ mã nguồn)."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        return "installer" if any(exe_dir.glob("unins*.exe")) else "portable"
    return "python"


def _state_path():
    return home() / "state" / STATE_FILE


def _load():
    try:
        data = json.loads(_state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data):
    try:
        p = _state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": f"CommentKit/{__version__}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - URL https của GitHub hoặc URL test


def _release_url(tag=None):
    if tag is None and os.environ.get("COMMENTKIT_UPDATE_URL"):
        return os.environ["COMMENTKIT_UPDATE_URL"]
    base = f"https://api.github.com/repos/{REPO}/releases"
    return f"{base}/tags/{tag}" if tag else f"{base}/latest"


def _release_info(rel):
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in rel.get("assets") or []}
    installer = next((n for n in assets if n.startswith("CommentKit-Setup-") and n.endswith(".exe")), "")
    return {"latest": str(rel.get("tag_name") or "").lstrip("vV"), "notes": rel.get("body") or "",
            "page": rel.get("html_url") or f"https://github.com/{REPO}/releases/latest",
            "installer": installer, "installer_url": assets.get(installer, ""),
            "sums_url": assets.get("SHA256SUMS.txt", "")}


def check(force=False):
    """Hỏi GitHub bản mới nhất (dùng câu trả lời đã nhớ trong 1 giờ, trừ khi force)."""
    with _lock:
        state = _load()
        now = time.time()
        # câu trả lời cũ hơn bản đang chạy là của bản cài trước: không tin
        fresh = (state.get("latest") and parse_version(state["latest"]) >= parse_version(__version__)
                 and now - float(state.get("checked_at") or 0) < CHECK_EVERY)
        if force or not fresh:
            try:
                with _get(_release_url()) as resp:
                    rel = json.loads(resp.read().decode("utf-8"))
                state.update(_release_info(rel), error="")
            except (OSError, ValueError) as e:
                state["error"] = f"Không kiểm tra được bản mới: {e}"
            state["checked_at"] = now
        _note_whats_new(state)   # cả ngay sau khi cập nhật, lúc câu trả lời đã nhớ vẫn còn mới
        _save(state)
        return state


def _note_whats_new(state):
    """Sau khi cập nhật: giữ ghi chú của bản đang chạy để hiện cửa sổ "Có gì mới"."""
    seen = state.get("seen_version")
    if not seen:
        state["seen_version"] = __version__   # lần chạy đầu tiên: không có gì để báo
        return
    if seen == __version__ or (state.get("whats_new") or {}).get("version") == __version__:
        return
    notes = state.get("notes", "") if state.get("latest") == __version__ else ""
    if not notes:
        try:
            with _get(_release_url(f"v{__version__}")) as resp:
                notes = json.loads(resp.read().decode("utf-8")).get("body") or ""
        except (OSError, ValueError):
            notes = ""
    state["whats_new"] = {"version": __version__, "notes": notes}


def mark_seen():
    with _lock:
        state = _load()
        state["seen_version"] = __version__
        state.pop("whats_new", None)
        _save(state)


def status():
    state = _load()
    latest = state.get("latest", "")
    newer = bool(latest) and parse_version(latest) > parse_version(__version__)
    mode = install_mode()
    whats_new = state.get("whats_new") if state.get("seen_version") != __version__ else None
    return {"current": __version__, "latest": latest, "newer": newer, "notes": state.get("notes", ""),
            "page": state.get("page") or f"https://github.com/{REPO}/releases/latest", "mode": mode,
            "can_install": newer and mode == "installer" and bool(state.get("installer_url") and state.get("sums_url")),
            "checked_at": state.get("checked_at", 0), "error": state.get("error", ""),
            "whats_new": whats_new, "progress": dict(PROGRESS), "repo": REPO}


def _expected_hash(sums_url, name):
    with _get(sums_url) as resp:
        for line in resp.read().decode("utf-8", "replace").splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].lstrip("*") == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                return parts[0].lower()
    raise UpdateError(f"SHA256SUMS.txt không có dòng cho {name}.")


def download_and_install(on_launched, before_launch=lambda: None):
    """Tải bộ cài mới, kiểm tra, gọi before_launch(), chạy im lặng rồi gọi on_launched().
    Bộ cài có thể đóng tiến trình này ngay, nên việc gì cần lưu thì làm trong before_launch."""
    state = _load()
    if not status()["can_install"]:
        raise UpdateError("Bản CommentKit này không tự cập nhật được. Tải bản mới ở trang Releases.")
    name = state["installer"]
    folder = home() / "state" / "updates"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*"):
        try:
            old.unlink()
        except OSError:
            pass
    dest = folder / name
    PROGRESS.update(phase="downloading", progress=0.0, error="")
    try:
        expected = _expected_hash(state["sums_url"], name)
        digest = hashlib.sha256()
        tmp = dest.with_suffix(".part")
        with _get(state["installer_url"], timeout=60) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while chunk := resp.read(1 << 20):
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if total:
                    PROGRESS["progress"] = round(done * 100 / total, 1)
        PROGRESS.update(phase="verifying", progress=100.0)
        if digest.hexdigest() != expected:
            tmp.unlink(missing_ok=True)
            raise UpdateError("Bộ cài tải về không khớp mã SHA-256 đã công bố nên đã bị xoá. "
                              "Thử lại sau hoặc tải ở trang Releases.")
        tmp.replace(dest)
        before_launch()
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([str(dest), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                          "/RELAUNCH=1"], creationflags=flags, close_fds=True)
        PROGRESS.update(phase="restarting")
    except UpdateError as e:
        PROGRESS.update(phase="error", error=str(e))
        raise
    except OSError as e:
        PROGRESS.update(phase="error", error=f"Cập nhật lỗi: {e}")
        raise UpdateError(f"Cập nhật lỗi: {e}") from e
    on_launched()


def start_background_check(enabled=lambda: True):
    """Kiểm tra ngay, rồi vài tiếng một lần khi app còn mở (nếu enabled() vẫn bật)."""
    def loop():
        while True:
            if enabled():
                check()
            time.sleep(RECHECK_EVERY)

    threading.Thread(target=loop, daemon=True).start()
