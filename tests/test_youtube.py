import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from commentkit import pipeline as P, youtube

CLIENT = {"installed": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "sec",
                        "redirect_uris": ["http://localhost"]}}


class Resp:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code, self._data, self.headers = status, data, headers or {}
        self.text = text or json.dumps(data or {})

    def json(self):
        return self._data


@pytest.fixture(autouse=True)
def own_home(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMENTKIT_HOME", str(tmp_path / "home"))
    youtube._pending.clear()


def connect(monkeypatch):
    youtube.save_client(json.dumps(CLIENT))
    url = youtube.auth_url("http://127.0.0.1:8765/oauth/youtube")
    state = parse_qs(urlparse(url).query)["state"][0]
    monkeypatch.setattr(youtube.requests, "post", lambda u, **k: Resp(data={
        "access_token": "at", "refresh_token": "rt", "expires_in": 3600}))
    monkeypatch.setattr(youtube.requests, "get", lambda u, **k: Resp(data={
        "items": [{"id": "UC123", "snippet": {"title": "Zapp Moments"}}]}))
    return youtube.finish_auth("the-code", state)


def test_client_file_is_checked():
    with pytest.raises(youtube.YouTubeError):
        youtube.save_client(b"not json")
    with pytest.raises(youtube.YouTubeError, match="Desktop"):
        youtube.save_client(json.dumps({"web": {"client_id": "a", "client_secret": "b"}}))
    assert youtube.save_client(json.dumps(CLIENT).encode()) == "cid.apps.googleusercontent.com"
    assert youtube.status()["client"] and not youtube.status()["connected"]


def test_auth_url_uses_pkce_and_loopback():
    youtube.save_client(json.dumps(CLIENT))
    q = parse_qs(urlparse(youtube.auth_url("http://127.0.0.1:8765/oauth/youtube")).query)
    assert q["client_id"] == ["cid.apps.googleusercontent.com"] and q["code_challenge_method"] == ["S256"]
    assert q["redirect_uri"] == ["http://127.0.0.1:8765/oauth/youtube"] and q["access_type"] == ["offline"]
    assert "youtube.upload" in q["scope"][0]


def test_connect_saves_token_and_channel(monkeypatch):
    ch = connect(monkeypatch)
    assert ch["title"] == "Zapp Moments"
    st = youtube.status()
    assert st["connected"] and st["channel"]["id"] == "UC123"
    with pytest.raises(youtube.YouTubeError, match="không khớp"):
        youtube.finish_auth("code", "wrong-state")


def test_expired_token_is_refreshed(monkeypatch):
    connect(monkeypatch)
    tok = youtube._read("token.json")
    tok["expires_at"] = time.time() - 10
    youtube._write("token.json", tok)
    seen = []
    monkeypatch.setattr(youtube.requests, "post", lambda u, **k: seen.append(k["data"]) or Resp(data={
        "access_token": "fresh", "expires_in": 3600}))
    assert youtube._token() == "fresh" and seen[0]["grant_type"] == "refresh_token"


def test_body_has_comedy_vietnamese_and_ai_disclosure():
    meta = {"title": "Sếp nhắn lúc 11 giờ đêm #shorts", "description": "Mô tả", "tags": ["hài", "đi làm", "threads"]}
    b = youtube.build_body(meta, "schedule", "2026-11-28T04:30:00Z")
    assert b["snippet"]["categoryId"] == "23" and b["snippet"]["defaultAudioLanguage"] == "vi"
    assert b["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": True, "publishAt": "2026-11-28T04:30:00Z"}
    assert "#hài" in b["snippet"]["description"] and "#đilàm" in b["snippet"]["description"]


def test_resumable_upload_in_chunks(tmp_path, monkeypatch):
    connect(monkeypatch)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"0123456789")
    monkeypatch.setattr(youtube, "CHUNK", 4)
    calls = []
    monkeypatch.setattr(youtube.requests, "post", lambda u, **k: calls.append(("post", k["json"])) or Resp(
        headers={"Location": "https://upload.example/session"}))
    replies = iter([Resp(308, headers={"Range": "bytes=0-3"}), Resp(308, headers={"Range": "bytes=0-7"}),
                    Resp(200, data={"id": "vid123"})])
    monkeypatch.setattr(youtube.requests, "put", lambda u, **k: calls.append(("put", k["headers"]["Content-Range"])) or next(replies))
    pct = []
    res = youtube.upload(str(video), {"title": "t"}, "unlisted", on_progress=pct.append)
    assert res == {"id": "vid123", "url": "https://youtube.com/shorts/vid123"}
    assert [c[1] for c in calls if c[0] == "put"] == ["bytes 0-3/10", "bytes 4-7/10", "bytes 8-9/10"]
    assert calls[0][1]["status"]["privacyStatus"] == "unlisted" and pct[-1] == 100


def test_quota_error_is_recognised(tmp_path, monkeypatch):
    connect(monkeypatch)
    video = tmp_path / "video.mp4"
    video.write_bytes(b"x")
    monkeypatch.setattr(youtube.requests, "post", lambda u, **k: Resp(403, data={
        "error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}))
    with pytest.raises(youtube.QuotaError):
        youtube.upload(str(video), {"title": "t"})


def test_schedule_slots():
    assert youtube.parse_slots("20:00, 11:30; 7, 25:00, x") == [(7, 0), (11, 30), (20, 0)]
    tz = timezone(timedelta(hours=7))
    now = datetime(2026, 11, 27, 11, 20, tzinfo=tz)            # 11:30 còn chưa tới 15 phút: bỏ
    first = youtube.next_slot([(11, 30), (20, 0)], [], now)
    assert first == "2026-11-27T13:00:00Z"                     # 20:00 giờ Việt Nam
    assert youtube.next_slot([(11, 30), (20, 0)], [first], now) == "2026-11-28T04:30:00Z"


def test_app_endpoints_and_worker_upload(tmp_path, monkeypatch):
    from commentkit import gui

    c = gui.app.test_client()
    monkeypatch.setattr(gui.webbrowser, "open", lambda url: None)
    assert c.post("/api/youtube/connect").status_code == 400          # chưa nạp client
    r = c.post("/api/youtube/client", data={"file": (__import__("io").BytesIO(json.dumps(CLIENT).encode()), "cs.json")})
    assert r.get_json()["ok"]
    url = c.post("/api/youtube/connect", headers={"Host": "commentkit.localhost:8765"}).get_json()["url"]
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8765%2Foauth%2Fyoutube" in url
    state = parse_qs(urlparse(url).query)["state"][0]
    monkeypatch.setattr(youtube.requests, "post", lambda u, **k: Resp(data={"access_token": "at", "refresh_token": "rt"}))
    monkeypatch.setattr(youtube.requests, "get", lambda u, **k: Resp(data={"items": [{"id": "UC1", "snippet": {"title": "Kênh"}}]}))
    assert "Đã kết nối kênh Kênh" in c.get(f"/oauth/youtube?code=x&state={state}").get_data(as_text=True)
    assert c.get("/api/state").get_json()["youtube"]["connected"]

    out = Path(gui.W.settings["output_dir"]) / "2026-11-27_120000_thu"
    out.mkdir(parents=True, exist_ok=True)
    (out / "video.mp4").write_bytes(b"x")
    (out / "metadata.json").write_text(json.dumps({"title": "Thử"}), encoding="utf-8")
    assert c.post("/api/youtube/upload", json={"name": out.name}).get_json()["ok"]
    assert gui.W.upload_req == [out.name]
    monkeypatch.setattr(youtube, "upload", lambda path, meta, privacy, at, on_progress: {"id": "v1", "url": "https://youtube.com/shorts/v1"})
    gui.W.upload_video(gui.W.upload_req.pop(0))
    meta = P.load_meta(str(out))
    assert meta["youtube"]["id"] == "v1" and meta["youtube"]["privacy"] == "private"
    assert c.post("/api/link", json={"url": "https://youtube.com/shorts/v1"}).status_code == 200
    assert c.post("/api/link", json={"url": "https://evil.example/"}).status_code == 400
