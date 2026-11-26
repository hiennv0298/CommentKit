"""Giao diện CommentKit: server Flask trên 127.0.0.1, cửa sổ là Edge/Chrome ở chế độ app.
- Kéo thả ảnh chụp Threads (hoặc chép thẳng vào thư mục inbox).
- Worker nền quét inbox: AI đọc ảnh -> VieNeu đọc -> dựng video có gameplay nền.
- Ảnh đã đọc chuyển sang inbox/_done (lỗi: inbox/_failed) nên không bị đọc lại.
- Đóng cửa sổ thì app tự thoát (đợi xong video đang làm)."""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from collections import deque
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.serving import make_server
from werkzeug.utils import secure_filename

from . import __version__, pipeline as P, updates, voice
from .llm import has_gemini_key, has_openai_key, set_env
from .paths import PKG, add_bundled_tools, home
from .render import VIDEO_EXT
from .write_script import check_llm

WEBUI = PKG / "webui"
PREFERRED_PORT = 8765   # cố định để cửa sổ giữ địa chỉ giữa các lần mở; bận thì lấy cổng ngẫu nhiên
SERVER_FILE = "server.json"
RELAUNCH_FILE = "relaunch.json"   # cổng của bản cũ, để bản mới mở lại đúng cửa sổ sau khi cập nhật
IDLE_EXIT = 150         # cửa sổ thu nhỏ lâu chỉ gọi /api/state 1 lần/phút: chờ quá 2 lần như vậy
app = Flask(__name__, static_folder=None)
SERVER = None


class Worker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.settings = P.load_settings()
        self.logs = deque(maxlen=300)
        self.current = None
        self.error = None
        self.llm = {}
        self.trigger = threading.Event()
        self.compose_req = []
        self.next_scan = 0
        self.voice_job = None   # None | "running" | "done" | "error: ..."
        self.voice_req = False

    def log(self, *a):
        line = datetime.now().strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
        self.logs.append(line)
        print(line, flush=True)

    @property
    def busy(self):
        return bool(self.current or self.compose_req or self.voice_req or self.voice_job == "running"
                    or updates.PROGRESS["phase"] in ("downloading", "verifying"))

    def run(self):
        self.log(f"CommentKit {__version__} sẵn sàng. Inbox:", self.settings["inbox_dir"])
        while True:
            if self.voice_req:
                self.voice_req = False
                self.install_voice()
                continue
            due = self.settings["auto"] and time.time() >= self.next_scan
            if self.compose_req:
                self.compose(self.compose_req.pop(0) or None)
                continue
            if self.trigger.is_set() or due:
                self.trigger.clear()
                self.scan()
                self.next_scan = time.time() + max(5, int(self.settings["interval_sec"]))
            time.sleep(1)

    def install_voice(self):
        self.voice_job, self.current = "running", "cài giọng đọc"
        try:
            P.save_local_cfg({"tts": {"python": ""}})   # dùng bản CommentKit tự cài
            voice.install(P.load_cfg(), self.log)
            self.voice_job = "done"
        except Exception as e:  # noqa: BLE001
            self.voice_job = f"error: {e}"
            self.log("✖ cài giọng đọc lỗi:", e)
        finally:
            self.current = None

    def compose(self, topic=None):
        self.current = "sáng tác" + (f": {topic}" if topic else "")
        try:
            P.compose_one(P.load_cfg(), self.settings, self.log, topic)
            self.error = None
        except P.AuthError as e:
            self.error = str(e)
            self.settings["compose_auto"] = False
            P.save_settings(self.settings)
            self.log("⏸ Tắt tự sáng tác:", e)
        finally:
            self.current = None

    def scan(self):
        jobs = [j for j in P.list_jobs(self.settings["inbox_dir"]) if j["ready"]]
        if not jobs and self.settings.get("compose_auto") and P.composed_today() < int(self.settings.get("compose_per_day", 3)):
            self.compose()
            return
        for j in jobs:
            self.current = j["name"]
            try:
                P.process_job(j, P.load_cfg(), self.settings, self.log)
                self.error = None
            except P.AuthError as e:
                self.error = str(e)
                self.settings["auto"] = False
                P.save_settings(self.settings)
                self.log("⏸ Tạm dừng tự động:", e)
                break
            except Exception as e:  # noqa: BLE001
                self.error = str(e)
                self.log("✖ lỗi:", e)
            finally:
                self.current = None


W = Worker()


class Presence:
    """Cửa sổ còn mở không: trang gọi /api/state đều đặn, đóng thì gửi /api/bye."""
    seen = False
    last_seen = 0.0
    bye_at = 0.0


def _rel(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


@app.before_request
def _local_only():
    # chặn DNS rebinding: chỉ nhận request gửi tới chính 127.0.0.1/localhost
    host = (request.host or "").rsplit(":", 1)[0].strip("[]").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        abort(403)


@app.get("/")
def index():
    return send_from_directory(WEBUI, "index.html", max_age=0)


@app.get("/<name>")
def webui_file(name):
    if name == "favicon.ico":
        return send_from_directory(WEBUI, "commentkit.ico")
    if name in ("icon-32.png", "icon-192.png", "icon-512.png", "commentkit.ico"):
        return send_from_directory(WEBUI, name)
    abort(404)


@app.get("/api/ping")
def ping():
    return jsonify(app="commentkit", version=__version__)


@app.post("/api/bye")
def bye():
    Presence.bye_at = time.monotonic()
    return jsonify(ok=True)


_voice_cache = {}


def voice_status(cfg):
    """Kiểm tra python của VieNeu mất ~0,5 giây: nhớ kết quả 30 giây (hoặc tới khi đổi đường dẫn / cài xong)."""
    key = (cfg["tts"]["python"], W.voice_job)
    hit = _voice_cache.get("v")
    if hit and hit[0] == key and time.monotonic() - hit[1] < 30:
        return hit[2]
    st = voice.status(cfg)
    _voice_cache["v"] = (key, time.monotonic(), st)
    return st


@app.get("/api/state")
def state():
    Presence.seen, Presence.last_seen = True, time.monotonic()
    s, inbox = W.settings, W.settings["inbox_dir"]
    cfg = P.load_cfg()
    img = lambda p: "/media/inbox/" + _rel(p, inbox)  # noqa: E731
    pend = [dict(name=j["name"], ready=j["ready"], added=j["added"], images=[img(x) for x in j["images"]])
            for j in P.list_jobs(inbox)]
    failed = [dict(name=j["name"], error=j.get("error", ""), images=[img(x) for x in j["images"]])
              for j in P.list_marked(inbox, "_failed")]
    done = [dict(name=j["name"], title=j.get("title"), skipped=j.get("skipped"), reason=j.get("reason"),
                 images=[img(x) for x in j["images"]][:1]) for j in P.list_marked(inbox, "_done")[:30]]
    bgs = sorted(f for f in os.listdir(s["bg_dir"]) if f.lower().endswith(VIDEO_EXT))
    return jsonify(
        version=__version__, home=str(home()),
        settings=s, current=W.current, error=W.error, llm=W.llm,
        openai_key=has_openai_key(), openai_model=cfg.get("openai", {}).get("model", ""),
        gemini_key=has_gemini_key(), gemini_model=cfg.get("gemini", {}).get("model", ""),
        voice=dict(voice_status(cfg), job=W.voice_job), ffmpeg=bool(shutil.which("ffmpeg")),
        composed_today=P.composed_today(), compose_queue=len(W.compose_req),
        topics=cfg.get("compose", {}).get("topics", []), logs=list(W.logs)[-120:],
        next_scan=max(0, int(W.next_scan - time.time())) if s["auto"] else None,
        pending=pend, failed=failed, done=done, backgrounds=bgs, outputs=P.list_outputs(s["output_dir"]),
    )


@app.post("/api/upload")
def upload():
    files = [f for f in request.files.getlist("files") if f.filename]
    files = [f for f in files if f.filename.lower().endswith(P.IMG_EXT)]
    if not files:
        return jsonify(ok=False, msg="Không có ảnh hợp lệ (png/jpg/webp)"), 400
    inbox, stamp = W.settings["inbox_dir"], datetime.now().strftime("%Y%m%d-%H%M%S")
    files.sort(key=lambda f: P._natural(f.filename))   # giữ thứ tự tên gốc: Screenshot_1, Screenshot_2...
    if request.form.get("mode", "group") == "group" and len(files) > 1:
        d = os.path.join(inbox, f"{stamp}-post")
        os.makedirs(d, exist_ok=True)
        for i, f in enumerate(files, 1):
            f.save(os.path.join(d, f"{i:02d}{os.path.splitext(f.filename)[1].lower()}"))
    else:   # mỗi ảnh một thư mục: ảnh lẻ thả vào cùng lúc sẽ bị gộp thành một bài
        for i, f in enumerate(files, 1):
            d = os.path.join(inbox, f"{stamp}-{i:02d}")
            os.makedirs(d, exist_ok=True)
            f.save(os.path.join(d, f"01{os.path.splitext(f.filename)[1].lower()}"))
    W.log(f"Đã nhận {len(files)} ảnh")
    return jsonify(ok=True, n=len(files))


@app.post("/api/scan")
def scan_now():
    W.trigger.set()
    return jsonify(ok=True)


@app.post("/api/auto")
def set_auto():
    W.settings["auto"] = bool((request.json or {}).get("on"))
    W.next_scan = 0
    if W.settings["auto"]:
        W.error = None
    P.save_settings(W.settings)
    return jsonify(ok=True)


@app.post("/api/settings")
def set_settings():
    body = request.json or {}
    for k in ("provider_read", "provider_compose"):
        if body.get(k) in ("claude", "openai", "gemini"):
            W.settings[k] = body[k]
    if "compose_auto" in body:
        W.settings["compose_auto"] = bool(body["compose_auto"])
    if "compose_per_day" in body:
        W.settings["compose_per_day"] = max(0, int(body["compose_per_day"]))
    if body.get("openai_key"):
        set_env("OPENAI_API_KEY", body["openai_key"])
    if body.get("gemini_key"):
        set_env("GEMINI_API_KEY", body["gemini_key"])
    patch = {}
    if body.get("openai_model"):
        patch["openai"] = {"model": body["openai_model"].strip()}
    if body.get("gemini_model"):
        patch["gemini"] = {"model": body["gemini_model"].strip()}
    if "tts_python" in body:   # "" = dùng bản CommentKit tự cài
        py = (body.get("tts_python") or "").strip().strip('"')
        if py and not voice.check_python(py)["ok"]:
            return jsonify(ok=False, msg="Python này không có gói vieneu: " + py), 400
        patch["tts"] = {"python": py.replace("\\", "/")}
    if patch:
        P.save_local_cfg(patch)
    if "check_updates" in body:
        W.settings["check_updates"] = bool(body["check_updates"])
    if "interval_sec" in body:
        W.settings["interval_sec"] = max(5, int(body["interval_sec"]))
    for k in ("inbox_dir", "bg_dir", "output_dir"):
        if body.get(k):
            os.makedirs(body[k], exist_ok=True)
            W.settings[k] = os.path.abspath(body[k])
    P.save_settings(W.settings)
    return jsonify(ok=True)


@app.get("/api/update")
def update_state():
    return jsonify(dict(updates.status(), enabled=W.settings.get("check_updates", True)))


@app.post("/api/update/check")
def update_check():
    # {force: false} = dùng câu trả lời đã nhớ trong 1 giờ
    updates.check(force=(request.json or {}).get("force", True) is not False)
    return update_state()


@app.post("/api/update/seen")
def update_seen():
    updates.mark_seen()
    return jsonify(ok=True)


@app.post("/api/update/install")
def update_install():
    if W.busy:
        return jsonify(ok=False, msg="Đợi CommentKit làm xong việc đang chạy rồi hãy cập nhật."), 409
    if updates.PROGRESS["phase"] not in ("downloading", "verifying", "restarting"):
        threading.Thread(target=_install_update, daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/link")
def open_link():
    url = str((request.json or {}).get("url", ""))
    if not url.startswith(f"https://github.com/{updates.REPO}/"):   # chỉ mở trang release của CommentKit
        abort(400)
    webbrowser.open(url)
    return jsonify(ok=True)


@app.post("/api/voice/install")
def voice_install():
    if W.voice_job != "running":
        W.voice_req = True
        W.voice_job = "running"
    return jsonify(ok=True)


@app.post("/api/retry")
def retry():
    try:
        P.retry_failed(W.settings["inbox_dir"], (request.json or {})["name"])
    except (FileNotFoundError, KeyError):
        abort(404)
    W.trigger.set()
    return jsonify(ok=True)


@app.post("/api/check-llm")
def chk():
    prov = (request.json or {}).get("provider", "claude")
    ok, msg = check_llm(P.load_cfg(), prov)
    W.llm[prov] = dict(ok=ok, msg=msg, at=datetime.now().strftime("%H:%M:%S"))
    return jsonify(W.llm[prov])


@app.post("/api/compose")
def compose_now():
    topic = ((request.json or {}).get("topic") or "").strip()
    W.compose_req.append(topic)
    return jsonify(ok=True, queued=len(W.compose_req))


@app.post("/api/bg/upload")
def bg_upload():
    n = 0
    for f in request.files.getlist("files"):
        if f.filename.lower().endswith(VIDEO_EXT):
            name = secure_filename(f.filename) or f"bg_{int(time.time())}.mp4"
            f.save(os.path.join(W.settings["bg_dir"], name))
            n += 1
    return jsonify(ok=n > 0, n=n)


@app.post("/api/bg/delete")
def bg_delete():
    name = os.path.basename((request.json or {}).get("name", ""))
    p = os.path.join(W.settings["bg_dir"], name)
    if not name or not os.path.isfile(p):
        abort(404)
    os.remove(p)
    return jsonify(ok=True)


@app.post("/api/open")
def open_folder():
    body = request.json or {}
    kind, name = body.get("kind"), os.path.basename(body.get("name", ""))
    base = {"output": W.settings["output_dir"], "inbox": W.settings["inbox_dir"], "bg": W.settings["bg_dir"],
            "home": str(home())}.get(kind)
    if not base:
        abort(400)
    p = os.path.join(base, name) if name else base
    if not os.path.exists(p):
        abort(404)
    os.startfile(p)  # noqa: S606 - mở thư mục của chính người dùng trong Explorer
    return jsonify(ok=True)


@app.post("/api/output/delete")
def output_delete():
    """Xoá một video đã làm: cả thư mục của nó (video, thumbnail, kịch bản) vào Thùng rác."""
    name = os.path.basename((request.json or {}).get("name", ""))
    d = os.path.join(W.settings["output_dir"], name)
    if not name or name in (".", "..") or not os.path.isfile(os.path.join(d, "video.mp4")):
        abort(404)
    try:
        P.move_to_trash(d)
    except OSError as e:
        return jsonify(ok=False, msg=str(e)), 409
    W.log("Đã xoá video (vào Thùng rác):", name)
    return jsonify(ok=True)


@app.get("/media/<kind>/<path:p>")
def media(kind, p):
    base = {"inbox": W.settings["inbox_dir"], "out": W.settings["output_dir"], "bg": W.settings["bg_dir"]}.get(kind)
    if not base:
        abort(404)
    return send_from_directory(base, p, conditional=True, max_age=0)


# ---------------------------------------------------------------- cửa sổ và vòng đời

def _install_update():
    def remember_port():
        # Bản mới chạy lại trên đúng cổng này, nên cửa sổ đang mở tự tải lại vào bản mới thay vì mở thêm
        # cửa sổ thứ hai cạnh cửa sổ chết. Ghi trước khi chạy bộ cài: bộ cài có thể đóng app ngay.
        if SERVER:
            try:
                (home() / "state" / RELAUNCH_FILE).write_text(json.dumps(
                    {"port": SERVER.server_port, "at": time.time(), "from": __version__}), encoding="utf-8")
            except OSError:
                pass

    def quit_soon():
        if SERVER:
            threading.Timer(1.0, SERVER.shutdown).start()   # để trang kịp đọc trạng thái "restarting"

    try:
        updates.download_and_install(quit_soon, remember_port)
    except updates.UpdateError:
        pass   # lỗi nằm trong updates.PROGRESS để trang hiện ra


def _take_relaunch():
    """Cổng bản cũ đã dùng, nếu lần mở này là lần mở lại sau khi cập nhật trong app (trong 10 phút)."""
    p = home() / "state" / RELAUNCH_FILE
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        p.unlink(missing_ok=True)
        if isinstance(data, dict) and time.time() - float(data.get("at") or 0) < 600:
            return int(data["port"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _open_window_unless_reloaded(url, wait=15):
    """Sau khi cập nhật, cửa sổ cũ tự tải lại vào bản mới; chỉ mở cửa sổ mới nếu nó không quay lại."""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        if Presence.seen:
            return
        time.sleep(0.5)
    open_window(url)


def _browser():
    for env in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if not base:
            continue
        for c in (Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"):
            if c.is_file():
                return str(c)
    return shutil.which("msedge") or shutil.which("chrome")


def open_window(url):
    exe = _browser()
    if not exe:
        webbrowser.open(url)
        return
    extra = os.environ.get("COMMENTKIT_BROWSER_ARGS", "").split()
    subprocess.Popen([exe, f"--app={url}", "--window-size=1400,950", *extra])
    from .winapp import tag_window_later

    tag_window_later()   # nút taskbar và icon riêng, không gộp chung với cửa sổ Edge, PlaylistKit hay ClipKit


def _server_file():
    return home() / "state" / SERVER_FILE


def _running_instance():
    try:
        port = int(json.loads(_server_file().read_text(encoding="utf-8"))["port"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            if json.loads(r.read()).get("app") == "commentkit":
                return f"http://127.0.0.1:{port}/"
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _watchdog(server):
    while True:
        time.sleep(1)
        if W.busy or not Presence.seen:
            continue
        now = time.monotonic()
        closed = Presence.bye_at > Presence.last_seen and now - Presence.bye_at > 5
        if closed or now - Presence.last_seen > IDLE_EXIT:
            W.log("Cửa sổ đã đóng, thoát.")
            server.shutdown()
            return


def _ensure_streams():
    """Bản app không có console: ghi log ra file thay vì mất."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    (home() / "state").mkdir(parents=True, exist_ok=True)
    stream = open(home() / "state" / "commentkit-app.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream


def main(open_ui=True):
    global SERVER
    _ensure_streams()
    add_bundled_tools()
    existing = _running_instance()
    if existing:
        if open_ui and not os.environ.get("COMMENTKIT_NO_WINDOW"):
            open_window(existing)
        return 0
    relaunch = _take_relaunch()
    port = int(os.environ.get("COMMENTKIT_PORT") or relaunch or PREFERRED_PORT)
    try:
        server = make_server("127.0.0.1", port, app, threaded=True)
    except OSError:   # cổng đang bận: chạy bình thường, mở cửa sổ mới
        server, relaunch = make_server("127.0.0.1", 0, app, threaded=True), None
    SERVER = server
    url = f"http://127.0.0.1:{server.server_port}/"
    try:
        _server_file().parent.mkdir(parents=True, exist_ok=True)
        _server_file().write_text(json.dumps({"port": server.server_port, "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass
    W.start()
    updates.start_background_check(lambda: W.settings.get("check_updates", True))
    if open_ui and not os.environ.get("COMMENTKIT_NO_WINDOW"):
        threading.Thread(target=_watchdog, args=(server,), daemon=True).start()
        if relaunch:
            threading.Thread(target=_open_window_unless_reloaded, args=(url,), daemon=True).start()
        else:
            open_window(url)
    print(f"CommentKit đang chạy ở {url}  (đóng cửa sổ app để thoát)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            _server_file().unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main("--no-browser" not in sys.argv))
