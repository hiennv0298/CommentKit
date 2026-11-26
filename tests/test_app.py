from pathlib import Path

import pytest
from PIL import Image

from commentkit import __version__, pipeline as P
from commentkit.gui import app
from commentkit.winapp import APP_ID, TITLE

ROOT = Path(__file__).resolve().parent.parent
WEBUI = ROOT / "src" / "commentkit" / "webui"


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_state_and_ping(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    s = r.get_json()
    assert s["version"] == __version__ and s["voice"]["ok"] is False and s["topics"]
    assert client.get("/api/ping").get_json()["app"] == "commentkit"


def test_other_hosts_are_refused(client):
    assert client.get("/api/state", headers={"Host": "evil.example:8765"}).status_code == 403


def test_page_and_icons_are_served(client):
    html = client.get("/").get_data(as_text=True)
    assert "<title>CommentKit</title>" in html and 'href="/icon-192.png"' in html
    for name in ("icon-32.png", "icon-192.png", "icon-512.png", "favicon.ico"):
        assert client.get("/" + name).status_code == 200
    assert client.get("/config.json").status_code == 404


def test_settings_model_goes_to_local_config(client):
    r = client.post("/api/settings", json={"gemini_model": "gemini-test", "provider_read": "gemini"})
    assert r.get_json()["ok"]
    assert P.load_cfg()["gemini"]["model"] == "gemini-test"
    assert P.load_settings()["provider_read"] == "gemini"


def test_settings_rejects_a_python_without_vieneu(client):
    r = client.post("/api/settings", json={"tts_python": "C:/nope/python.exe"})
    assert r.status_code == 400


def test_ui_is_vietnamese():
    html = (WEBUI / "index.html").read_text(encoding="utf-8")
    assert '<html lang="vi">' in html and "Cài giọng đọc" in html and "Kéo thả ảnh vào đây" in html


def test_icon_sizes():
    ico = Image.open(WEBUI / "commentkit.ico")
    assert {16, 24, 32, 48, 256} <= {w for w, _ in ico.info["sizes"]}
    for s in (32, 192, 512):
        assert Image.open(WEBUI / f"icon-{s}.png").size == (s, s)


def test_taskbar_identity_is_our_own():
    # không bao giờ được trùng cửa sổ Edge hay bộ cài của PlaylistKit/ClipKit
    assert APP_ID == "hiennv0298.CommentKit" and TITLE == "CommentKit"
    iss = (ROOT / "installer" / "commentkit.iss").read_text(encoding="utf-8")
    assert iss.count(f'AppUserModelID: "{APP_ID}"') == 2
    for other in ("hiennv0298.PlaylistKit", "hiennv0298.ClipKit", "4F7A2C19-8D3E-4B6A-A1F5-2E9C7B0D6A43",
                  "8C1E5B52-4E0B-4E52-9A43-6E3B7C2F9D11"):
        assert other not in iss
