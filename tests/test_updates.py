import hashlib
import importlib.util
import json
import time
from pathlib import Path

import pytest

from commentkit import __version__, updates
from commentkit.paths import home

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def own_home(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMENTKIT_HOME", str(tmp_path / "home"))
    updates.PROGRESS.update(phase="idle", progress=0.0, error="")
    return tmp_path


def fake_release(tmp_path, monkeypatch, version="99.0.0", payload=b"installer bytes", good_hash=True, body="- Mới"):
    name = f"CommentKit-Setup-{version}.exe"
    exe = tmp_path / name
    exe.write_bytes(payload)
    digest = hashlib.sha256(payload if good_hash else b"khac").hexdigest()
    sums = tmp_path / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  {name}\n", encoding="ascii")
    rel = {"tag_name": f"v{version}", "body": body, "html_url": "https://example.invalid/rel",
           "assets": [{"name": name, "browser_download_url": exe.as_uri()},
                      {"name": "SHA256SUMS.txt", "browser_download_url": sums.as_uri()}]}
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(rel), encoding="utf-8")
    monkeypatch.setenv("COMMENTKIT_UPDATE_URL", path.as_uri())
    return name


def test_parse_version():
    assert updates.parse_version("v0.10.2") > updates.parse_version("0.9.9")
    assert updates.parse_version("1.2") == (1, 2, 0)
    assert updates.parse_version("0.3.0-beta") == (0, 3, 0)


def test_release_notes_section():
    spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts" / "release_notes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = mod.section(text, f"v{__version__}")
    assert notes and "## " not in notes
    assert mod.section(text, "0.0.0") == ""


def test_check_reports_newer_release(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch)
    updates.check(force=True)
    st = updates.status()
    assert st["newer"] and st["latest"] == "99.0.0" and st["notes"] == "- Mới"
    assert st["mode"] == "python" and not st["can_install"]   # test chạy từ mã nguồn, không phải bản cài


def test_cache_older_than_running_version_is_rechecked(tmp_path, monkeypatch):
    # bản cài cũ vừa nhớ "latest = 0.0.1": bản này phải hỏi GitHub lại
    updates._save({"latest": "0.0.1", "checked_at": time.time(), "seen_version": __version__})
    fake_release(tmp_path, monkeypatch, version="99.0.0")
    updates.check()
    assert updates.status()["latest"] == "99.0.0" and updates.status()["newer"]


def test_fresh_cache_is_reused():
    updates._save({"latest": "99.0.0", "checked_at": time.time(), "seen_version": __version__})
    with pytest.MonkeyPatch.context() as m:
        m.setattr(updates, "_get", lambda *a, **k: pytest.fail("phải dùng câu trả lời đã nhớ"))
        updates.check()
    assert updates.status()["latest"] == "99.0.0"


def test_relaunch_port_is_taken_once():
    from commentkit import gui

    p = home() / "state" / gui.RELAUNCH_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"port": 54321, "at": time.time()}), encoding="utf-8")
    assert gui._take_relaunch() == 54321
    assert gui._take_relaunch() is None   # đã dùng
    p.write_text(json.dumps({"port": 54321, "at": time.time() - 3600}), encoding="utf-8")
    assert gui._take_relaunch() is None   # quá cũ: mở bình thường


def test_whats_new_after_update(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, version=__version__, body="- Tính năng mới")
    updates.check(force=True)
    assert updates.status()["whats_new"] is None   # lần chạy đầu: không có gì để báo
    state = updates._load()
    state["seen_version"] = "0.0.1"                  # giả như trước đó chạy bản cũ hơn
    updates._save(state)
    updates.check()
    assert updates.status()["whats_new"] == {"version": __version__, "notes": "- Tính năng mới"}
    updates.mark_seen()
    assert updates.status()["whats_new"] is None


def test_install_verifies_and_launches(tmp_path, monkeypatch):
    name = fake_release(tmp_path, monkeypatch)
    updates.check(force=True)
    monkeypatch.setattr(updates, "install_mode", lambda: "installer")
    launched = []
    monkeypatch.setattr(updates.subprocess, "Popen", lambda args, **kw: launched.append(args))
    done = []
    updates.download_and_install(lambda: done.append(True))
    assert launched and launched[0][0].endswith(name) and "/RELAUNCH=1" in launched[0] and done
    assert updates.PROGRESS["phase"] == "restarting"


def test_install_rejects_bad_checksum(tmp_path, monkeypatch):
    fake_release(tmp_path, monkeypatch, good_hash=False)
    updates.check(force=True)
    monkeypatch.setattr(updates, "install_mode", lambda: "installer")
    monkeypatch.setattr(updates.subprocess, "Popen", lambda *a, **k: pytest.fail("không được chạy"))
    with pytest.raises(updates.UpdateError, match="SHA-256"):
        updates.download_and_install(lambda: None)
    assert updates.PROGRESS["phase"] == "error"
    assert not list((home() / "state" / "updates").glob("*.exe"))


def test_update_endpoints(tmp_path, monkeypatch):
    from commentkit.gui import app

    fake_release(tmp_path, monkeypatch)
    c = app.test_client()
    u = c.post("/api/update/check", json={}).get_json()
    assert u["newer"] and u["latest"] == "99.0.0" and u["current"] == __version__
    assert c.get("/api/update").get_json()["enabled"] is True
    assert c.post("/api/link", json={"url": "https://evil.example/x"}).status_code == 400
