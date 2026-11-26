"""Tự đăng video lên YouTube bằng YouTube Data API v3, dưới tài khoản của chính bạn.

* Bạn tạo một OAuth client loại "Desktop app" trong Google Cloud (xem README) rồi nạp file client_secret*.json
  vào app. File và token được lưu ở <home>/.youtube/, không gửi đi đâu ngoài Google.
* Đăng nhập: OAuth "installed app" có PKCE; Google chuyển về chính server của app ở http://127.0.0.1:<cổng>/oauth/youtube.
* Tải lên: resumable upload (từng khúc 8 MB, có tiến độ). Gắn sẵn: tiêu đề, mô tả + hashtag, tag, thể loại Hài,
  ngôn ngữ tiếng Việt, "không dành cho trẻ em", và công bố "nội dung tổng hợp" (giọng AI).
* Giới hạn của Google: dự án chưa qua kiểm duyệt (audit) thì video tải lên qua API bị khoá ở chế độ riêng tư;
  mỗi lần tải tốn 1.600/10.000 đơn vị hạn mức ngày, tức khoảng 6 video/ngày.
"""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests

from .paths import home

SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK = 8 * 1024 * 1024
CATEGORY_COMEDY = "23"
AUDIT_FORM = "https://support.google.com/youtube/contact/yt_api_form"
_pending = {}   # state -> {"verifier", "redirect"} của lần đăng nhập đang chờ Google chuyển về


class YouTubeError(RuntimeError):
    pass


class QuotaError(YouTubeError):
    """Hết hạn mức tải lên trong ngày: dừng tự đăng tới hôm sau."""


def ydir():
    d = home() / ".youtube"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(name):
    try:
        return json.loads((ydir() / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(name, data):
    p = ydir() / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


# ---------- OAuth client (file client_secret*.json tải từ Google Cloud) ----------
def save_client(raw):
    """Kiểm tra rồi lưu file client_secret*.json. Trả về client_id."""
    try:
        data = json.loads(raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw)
    except ValueError:
        raise YouTubeError("File không phải JSON. Hãy tải đúng file client_secret*.json từ Google Cloud.") from None
    c = data.get("installed") or data.get("web") or {}
    if not c.get("client_id") or not c.get("client_secret"):
        raise YouTubeError("File thiếu client_id/client_secret. Tạo OAuth client loại \"Desktop app\" rồi tải JSON về.")
    if "installed" not in data:
        raise YouTubeError("Đây là client loại Web. Hãy tạo OAuth client loại \"Desktop app\" (ứng dụng máy tính).")
    _write("client_secret.json", data)
    return c["client_id"]


def _client():
    data = _read("client_secret.json") or {}
    c = data.get("installed") or {}
    if not c.get("client_id"):
        raise YouTubeError("Chưa nạp file client_secret.json (Cài đặt > YouTube).")
    return c


def auth_url(redirect_uri):
    """URL đăng nhập Google (PKCE). Google chuyển về redirect_uri?code=...&state=..."""
    c = _client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    _pending.clear()
    _pending[state] = {"verifier": verifier, "redirect": redirect_uri}
    q = {"client_id": c["client_id"], "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPES,
         "access_type": "offline", "prompt": "consent", "state": state,
         "code_challenge": challenge, "code_challenge_method": "S256"}
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def finish_auth(code, state):
    """Đổi code lấy token, lưu lại, đọc tên kênh. Trả về thông tin kênh."""
    p = _pending.pop(state, None)
    if not p:
        raise YouTubeError("Phiên đăng nhập không khớp hoặc đã hết hạn, bấm Kết nối YouTube lại.")
    c = _client()
    r = requests.post(TOKEN_URL, timeout=30, data={
        "code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": p["redirect"], "grant_type": "authorization_code", "code_verifier": p["verifier"]})
    if r.status_code != 200:
        raise YouTubeError(f"Google từ chối đăng nhập ({r.status_code}): {r.text[:200]}")
    tok = r.json()
    if not tok.get("refresh_token"):
        raise YouTubeError("Google không trả refresh token. Gỡ quyền của app ở myaccount.google.com/permissions rồi kết nối lại.")
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
    _write("token.json", tok)
    return refresh_channel()


def _token():
    tok = _read("token.json")
    if not tok or not tok.get("refresh_token"):
        raise YouTubeError("Chưa kết nối YouTube (Cài đặt > YouTube > Kết nối).")
    if time.time() < float(tok.get("expires_at") or 0) and tok.get("access_token"):
        return tok["access_token"]
    c = _client()
    r = requests.post(TOKEN_URL, timeout=30, data={
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        if "invalid_grant" in r.text:
            raise YouTubeError("Quyền truy cập YouTube đã hết hạn hoặc bị thu hồi: bấm Kết nối YouTube lại. "
                               "(App Google ở chế độ Testing thì token hết hạn sau 7 ngày, xem README.)")
        raise YouTubeError(f"Không làm mới được token ({r.status_code}): {r.text[:200]}")
    new = r.json()
    tok.update(access_token=new["access_token"], expires_at=time.time() + int(new.get("expires_in", 3600)) - 60)
    _write("token.json", tok)
    return tok["access_token"]


def _auth():
    return {"Authorization": f"Bearer {_token()}"}


def refresh_channel():
    r = requests.get(f"{API}/channels", params={"part": "snippet", "mine": "true"}, headers=_auth(), timeout=30)
    if r.status_code != 200:
        raise YouTubeError(f"Không đọc được kênh ({r.status_code}): {r.text[:200]}")
    items = r.json().get("items") or []
    if not items:
        raise YouTubeError("Tài khoản Google này chưa có kênh YouTube.")
    ch = {"id": items[0]["id"], "title": items[0]["snippet"].get("title", ""),
          "url": f"https://www.youtube.com/channel/{items[0]['id']}"}
    _write("channel.json", ch)
    return ch


def status():
    tok = _read("token.json") or {}
    return {"client": bool((_read("client_secret.json") or {}).get("installed")),
            "connected": bool(tok.get("refresh_token")), "channel": _read("channel.json"),
            "audit_form": AUDIT_FORM}


def disconnect():
    tok = _read("token.json") or {}
    if tok.get("refresh_token"):
        try:
            requests.post(REVOKE_URL, params={"token": tok["refresh_token"]}, timeout=15)
        except requests.RequestException:
            pass
    for name in ("token.json", "channel.json"):
        try:
            (ydir() / name).unlink()
        except OSError:
            pass


# ---------- đăng video ----------
def build_body(meta, privacy, publish_at=None):
    tags = [str(t).strip().lstrip("#") for t in meta.get("tags") or [] if str(t).strip()]
    kept, total = [], 0
    for t in tags:                                 # YouTube giới hạn tổng tag ~500 ký tự
        if total + len(t) + 1 > 450:
            break
        kept.append(t)
        total += len(t) + 1
    desc = (meta.get("description") or "").strip()
    hashtags = " ".join("#" + t.replace(" ", "") for t in kept[:5])
    if hashtags and "#" not in desc:
        desc = f"{desc}\n\n{hashtags}"
    status = {"privacyStatus": "private" if privacy == "schedule" else privacy,
              "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}
    if privacy == "schedule" and publish_at:
        status["publishAt"] = publish_at
    return {"snippet": {"title": (meta.get("title") or "Bình luận hài")[:100], "description": desc[:4900],
                        "tags": kept, "categoryId": CATEGORY_COMEDY,
                        "defaultLanguage": "vi", "defaultAudioLanguage": "vi"},
            "status": status}


def _api_error(r):
    try:
        err = r.json().get("error", {})
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        msg = err.get("message", "")
    except ValueError:
        reason, msg = "", r.text[:200]
    if reason in ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded"):
        return QuotaError("Hết hạn mức tải lên YouTube hôm nay (khoảng 6 video/ngày). Ngày mai tool đăng tiếp.")
    return YouTubeError(f"YouTube lỗi {r.status_code} {reason}: {msg}")


def upload(video_path, meta, privacy="private", publish_at=None, on_progress=lambda pct: None):
    """Tải video lên. Trả về {"id", "url"}."""
    size = os.path.getsize(video_path)
    body = build_body(meta, privacy, publish_at)
    r = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=body,
                      headers={**_auth(), "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      timeout=60)
    if r.status_code != 200 or "Location" not in r.headers:
        raise _api_error(r)
    session = r.headers["Location"]
    sent = 0
    with open(video_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            end = sent + len(chunk) - 1
            for attempt in range(4):
                try:
                    r = requests.put(session, data=chunk, timeout=300, headers={
                        **_auth(), "Content-Length": str(len(chunk)), "Content-Range": f"bytes {sent}-{end}/{size}"})
                    break
                except requests.RequestException:
                    if attempt == 3:
                        raise YouTubeError("Mất kết nối khi tải video lên YouTube.") from None
                    time.sleep(3 * (attempt + 1))
            if r.status_code in (200, 201):
                vid = r.json()["id"]
                on_progress(100)
                return {"id": vid, "url": f"https://youtube.com/shorts/{vid}"}
            if r.status_code != 308:
                raise _api_error(r)
            rng = r.headers.get("Range")                 # Google báo đã nhận tới byte nào
            sent = int(rng.split("-")[1]) + 1 if rng else sent + len(chunk)
            f.seek(sent)
            on_progress(round(sent * 100 / size))


# ---------- hẹn giờ đăng ----------
def parse_slots(text):
    """'11:30, 20:00' -> [(11, 30), (20, 0)] đã sắp xếp."""
    out = []
    for part in str(text or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            h, m = (part.split(":") + ["0"])[:2]
            h, m = int(h), int(m)
        except ValueError:
            continue
        if 0 <= h < 24 and 0 <= m < 60:
            out.append((h, m))
    return sorted(set(out))


def next_slot(slots, taken, now=None):
    """Khung giờ trống gần nhất (cách hiện tại ít nhất 15 phút), dạng RFC 3339 UTC: '2026-11-28T04:30:00Z'."""
    now = (now or datetime.now().astimezone())
    taken = set(taken)
    for day in range(0, 60):
        d = (now + timedelta(days=day)).date()
        for h, m in slots:
            t = datetime(d.year, d.month, d.day, h, m, tzinfo=now.tzinfo)
            if t < now + timedelta(minutes=15):
                continue
            iso = t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if iso not in taken:
                return iso
    return None
