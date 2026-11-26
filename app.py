"""Giao diện web chạy trên máy: http://127.0.0.1:8765
- Kéo thả ảnh chụp Threads (hoặc chép thẳng vào thư mục inbox).
- Worker nền quét inbox, Claude đọc ảnh -> VieNeu đọc -> dựng video có gameplay nền.
- Ảnh đã đọc chuyển sang inbox/_done (lỗi: inbox/_failed) nên không bị đọc lại."""
import os, sys, threading, time, webbrowser
from collections import deque
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
from flask import Flask, jsonify, request, send_from_directory, abort  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402
import pipeline as P  # noqa: E402
from write_script import check_llm  # noqa: E402
from llm import has_openai_key, has_gemini_key, set_env  # noqa: E402
from render import VIDEO_EXT  # noqa: E402

PORT = int(os.environ.get("PORT", 8765))
app = Flask(__name__, static_folder=os.path.join(ROOT, "web"), static_url_path="/static")


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

    def log(self, *a):
        line = datetime.now().strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
        self.logs.append(line)
        print(line, flush=True)

    def run(self):
        self.log("Worker sẵn sàng. Inbox:", self.settings["inbox_dir"])
        while True:
            due = self.settings["auto"] and time.time() >= self.next_scan
            if self.compose_req:
                self.compose(self.compose_req.pop(0) or None)
                continue
            if self.trigger.is_set() or due:
                self.trigger.clear()
                self.scan()
                self.next_scan = time.time() + max(5, int(self.settings["interval_sec"]))
            time.sleep(1)

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
            except Exception as e:  # noqa
                self.error = str(e)
                self.log("✖ lỗi:", e)
            finally:
                self.current = None


W = Worker()


def _rel(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


@app.get("/")
def index():
    return send_from_directory(os.path.join(ROOT, "web"), "index.html")


@app.get("/api/state")
def state():
    s, inbox = W.settings, W.settings["inbox_dir"]
    img = lambda p: "/media/inbox/" + _rel(p, inbox)  # noqa: E731
    pend = [dict(name=j["name"], ready=j["ready"], added=j["added"], images=[img(x) for x in j["images"]])
            for j in P.list_jobs(inbox)]
    failed = [dict(name=j["name"], error=j.get("error", ""), images=[img(x) for x in j["images"]])
              for j in P.list_marked(inbox, "_failed")]
    done = [dict(name=j["name"], title=j.get("title"), skipped=j.get("skipped"), reason=j.get("reason"),
                 images=[img(x) for x in j["images"]][:1]) for j in P.list_marked(inbox, "_done")[:30]]
    bgs = sorted(f for f in os.listdir(s["bg_dir"]) if f.lower().endswith(VIDEO_EXT))
    return jsonify(
        settings=s, current=W.current, error=W.error, llm=W.llm, openai_key=has_openai_key(), openai_model=P.load_cfg().get("openai", {}).get("model", ""),
        gemini_key=has_gemini_key(), gemini_model=P.load_cfg().get("gemini", {}).get("model", ""),
        composed_today=P.composed_today(), compose_queue=len(W.compose_req), topics=P.load_cfg().get("compose", {}).get("topics", []), logs=list(W.logs)[-120:],
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
    if request.form.get("mode", "group") == "group" and len(files) > 1:
        d = os.path.join(inbox, f"{stamp}-post")
        os.makedirs(d, exist_ok=True)
        for i, f in enumerate(files, 1):
            ext = os.path.splitext(f.filename)[1].lower()
            f.save(os.path.join(d, f"{i:02d}_{secure_filename(f.filename) or 'anh'}"[:80] + ("" if secure_filename(f.filename) else ext)))
    else:
        for i, f in enumerate(files, 1):
            ext = os.path.splitext(f.filename)[1].lower()
            f.save(os.path.join(inbox, f"{stamp}-{i:02d}{ext}"))
    W.log(f"Đã nhận {len(files)} ảnh")
    return jsonify(ok=True, n=len(files))


@app.post("/api/scan")
def scan_now():
    W.trigger.set()
    return jsonify(ok=True)


@app.post("/api/auto")
def set_auto():
    W.settings["auto"] = bool(request.json.get("on"))
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
    if body.get("openai_model") or body.get("gemini_model"):
        patch = {}
        if body.get("openai_model"):
            patch["openai"] = {"model": body["openai_model"].strip()}
        if body.get("gemini_model"):
            patch["gemini"] = {"model": body["gemini_model"].strip()}
        P.save_local_cfg(patch)
    if "interval_sec" in body:
        W.settings["interval_sec"] = max(5, int(body["interval_sec"]))
    for k in ("inbox_dir", "bg_dir", "output_dir"):
        if body.get(k):
            os.makedirs(body[k], exist_ok=True)
            W.settings[k] = os.path.abspath(body[k])
    P.save_settings(W.settings)
    return jsonify(ok=True)


@app.post("/api/retry")
def retry():
    try:
        P.retry_failed(W.settings["inbox_dir"], request.json["name"])
    except FileNotFoundError:
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
    name = os.path.basename(request.json["name"])
    p = os.path.join(W.settings["bg_dir"], name)
    if not os.path.isfile(p):
        abort(404)
    os.remove(p)
    return jsonify(ok=True)


@app.post("/api/open")
def open_folder():
    kind, name = request.json.get("kind"), os.path.basename(request.json.get("name", ""))
    base = {"output": W.settings["output_dir"], "inbox": W.settings["inbox_dir"], "bg": W.settings["bg_dir"]}.get(kind)
    if not base:
        abort(400)
    p = os.path.join(base, name) if name else base
    if not os.path.exists(p):
        abort(404)
    os.startfile(p)
    return jsonify(ok=True)


@app.get("/media/<kind>/<path:p>")
def media(kind, p):
    base = {"inbox": W.settings["inbox_dir"], "out": W.settings["output_dir"], "bg": W.settings["bg_dir"]}.get(kind)
    if not base:
        abort(404)
    return send_from_directory(base, p, conditional=True, max_age=0)


if __name__ == "__main__":
    W.start()
    if "--no-browser" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, threaded=True)
