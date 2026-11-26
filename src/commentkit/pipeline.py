"""Phần lõi dùng chung cho giao diện và dòng lệnh: quét thư mục inbox, đọc ảnh, dựng video, đánh dấu đã đọc."""
import json, os, re, shutil, subprocess, time, traceback

from PIL import Image
from datetime import datetime

from .write_script import write_script_from_images, write_script_original
from .llm import AuthError, LLMError  # noqa: F401
from .render import render
from .crop import detect_photos
from .paths import NO_WINDOW, PKG, home
from . import voice

ROOT = str(home())   # thư mục dữ liệu (xem paths.home)
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
SETTINGS_PATH = os.path.join(ROOT, "state", "settings.json")
DEFAULT_SETTINGS = dict(
    inbox_dir=os.path.join(ROOT, "inbox"),
    bg_dir=os.path.join(ROOT, "backgrounds"),
    output_dir=os.path.join(ROOT, "output"),
    auto=True,
    interval_sec=30,
    provider_read="claude",      # ai đọc ảnh chụp: "claude" | "openai" | "gemini"
    provider_compose="claude",   # ai tự sáng tác: "claude" | "openai" | "gemini"
    compose_auto=False,          # tự sáng tác khi inbox trống
    compose_per_day=3,
    check_updates=True,          # tự kiểm tra bản mới trên GitHub
    yt_auto=False,               # tự đăng video mới làm xong lên YouTube
    yt_privacy="private",        # private | unlisted | public | schedule (hẹn giờ theo khung)
    yt_slots="11:30, 20:00",     # khung giờ đăng khi hẹn giờ
)
HISTORY_PATH = os.path.join(ROOT, "state", "compose_history.json")
STABLE_SEC = 8      # file phải "yên" từng này giây (đã chép xong) mới xử lý
GROUP_GAP = 20      # ảnh lẻ vào inbox cách nhau không quá ngần này giây = cùng một bài
GROUP_WAIT = 25     # nhóm ảnh lẻ phải yên ngần này giây (chờ thả nốt ảnh) mới xử lý


LOCAL_CFG = os.path.join(ROOT, "config.local.json")   # chỉnh riêng từng máy (không đưa lên git), đè lên config.json


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def _abs(p):
    return p if not p or os.path.isabs(p) else os.path.normpath(os.path.join(ROOT, p))


def load_local_cfg():
    try:
        return json.load(open(LOCAL_CFG, encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def save_local_cfg(patch):
    json.dump(_merge(load_local_cfg(), patch), open(LOCAL_CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def load_cfg():
    cfg = _merge(json.load(open(os.path.join(PKG, "config.json"), encoding="utf-8-sig")), load_local_cfg())
    t = cfg["tts"]
    t["python"] = _abs(t.get("python")) or str(voice.managed_python())
    t["hf_home"] = _abs(t.get("hf_home")) or str(voice.default_hf_home())
    return cfg


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        s.update(json.load(open(SETTINGS_PATH, encoding="utf-8")))
    except (OSError, ValueError):
        pass
    for k in ("inbox_dir", "bg_dir", "output_dir"):
        os.makedirs(s[k], exist_ok=True)
    return s


def save_settings(s):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    json.dump(s, open(SETTINGS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def slug(s):
    s = re.sub(r"[^\w\-]+", "-", os.path.splitext(s)[0], flags=re.U).strip("-")
    return s[:40] or "job"


def _natural(name):
    """Sắp tên kiểu người đọc: Screenshot_2 đứng trước Screenshot_10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(name))]


def _images_in(d):
    return sorted((os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(IMG_EXT)), key=_natural)


def _arrived(p):
    """Lúc file xuất hiện trong inbox. Trên Windows là thời điểm tạo file (chép/kéo thả vào), không phải lúc chụp."""
    st = os.stat(p)
    return max(getattr(st, "st_birthtime", 0) or st.st_ctime, st.st_mtime) if os.name == "nt" else st.st_mtime


def list_jobs(inbox):
    """Mỗi thư mục con = 1 bài. Ảnh lẻ được thả vào cùng một đợt (cách nhau <= GROUP_GAP giây) cũng gộp thành
    1 bài, xếp theo tên (Screenshot_1, Screenshot_2...). Thư mục bắt đầu bằng "_" (_done, _failed) bị bỏ qua."""
    jobs, now, loose = [], time.time(), []
    if not os.path.isdir(inbox):
        return jobs
    for name in sorted(os.listdir(inbox), key=_natural):
        if name.startswith(("_", ".")):
            continue
        p = os.path.join(inbox, name)
        if os.path.isdir(p):
            imgs = _images_in(p)
            if not imgs:
                continue
            newest = max(os.path.getmtime(x) for x in imgs + [p])
            jobs.append(dict(name=name, path=p, images=imgs, ready=now - newest >= STABLE_SEC,
                             added=datetime.fromtimestamp(newest).isoformat(timespec="seconds")))
        elif name.lower().endswith(IMG_EXT):
            try:
                loose.append((_arrived(p), p))
            except OSError:
                continue
    groups = []
    for t, p in sorted(loose):
        if groups and t - groups[-1][-1][0] <= GROUP_GAP:
            groups[-1].append((t, p))
        else:
            groups.append([(t, p)])
    for g in groups:
        imgs = sorted((p for _, p in g), key=_natural)
        newest = max(t for t, _ in g)
        first = os.path.basename(imgs[0])
        name = first if len(imgs) == 1 else f"{os.path.splitext(first)[0]} (+{len(imgs) - 1} ảnh)"
        jobs.append(dict(name=name, path=imgs[0], files=imgs, images=imgs,
                         ready=now - newest >= (STABLE_SEC if len(imgs) > 1 or now - newest > GROUP_WAIT else GROUP_WAIT),
                         added=datetime.fromtimestamp(newest).isoformat(timespec="seconds")))
    return jobs


def list_marked(inbox, sub):
    d = os.path.join(inbox, sub)
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d), reverse=True):
        p = os.path.join(d, name)
        if not os.path.isdir(p):
            continue
        info = {}
        try:
            info = json.load(open(os.path.join(p, "_info.json"), encoding="utf-8"))
        except (OSError, ValueError):
            pass
        out.append(dict(name=name, path=p, images=_images_in(p), **info))
    return out


def mark(job, inbox, sub, info):
    """Chuyển job sang inbox/_done hoặc inbox/_failed để lần sau không đọc lại."""
    dest = os.path.join(inbox, sub, datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + slug(job["name"]))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isdir(job["path"]):
        shutil.move(job["path"], dest)
    else:
        os.makedirs(dest, exist_ok=True)
        for f in job.get("files") or [job["path"]]:
            shutil.move(f, os.path.join(dest, os.path.basename(f)))
    json.dump(dict(info, at=datetime.now().isoformat(timespec="seconds"), original=job["name"]),
              open(os.path.join(dest, "_info.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return dest


def retry_failed(inbox, name):
    src = os.path.join(inbox, "_failed", name)
    if not os.path.isdir(src):
        raise FileNotFoundError(name)
    imgs = _images_in(src)
    base = name.split("_", 1)[-1]
    dest = os.path.join(inbox, base)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(inbox, f"{base}-{i}")
        i += 1
    os.makedirs(dest)
    for p in imgs:
        shutil.move(p, os.path.join(dest, os.path.basename(p)))
    shutil.rmtree(src, ignore_errors=True)
    return dest


def tts(script, cfg, out_dir):
    chars = cfg["characters"]
    nd = chars["nguoi_dang"]
    lines = [dict(id="00", tts=script["post"].get("tts") or script["post"]["text"], voice=nd["voice"], fx=nd.get("fx", ""))]
    for i, c in enumerate(script["comments"], 1):
        ch = chars[c["who"]]
        lines.append(dict(id=f"{i:02d}", tts=c.get("tts") or c["text"], voice=ch["voice"], fx=ch.get("fx", "")))
    job = os.path.join(out_dir, "tts_job.json")
    json.dump(dict(gap=cfg["tts"]["gap_sec"], speed=cfg["tts"].get("speed", 1.0), lines=lines), open(job, "w", encoding="utf-8"), ensure_ascii=False)
    if not os.path.exists(cfg["tts"]["python"]):
        raise RuntimeError("Chưa cài giọng đọc VieNeu: bấm \"Cài giọng đọc\" trên giao diện (hoặc chạy: commentkit install-voices)")
    env = dict(os.environ, HF_HOME=cfg["tts"]["hf_home"], PYTHONIOENCODING="utf-8")
    r = subprocess.run([cfg["tts"]["python"], "-I", str(voice.TTS_SCRIPT), job, out_dir], creationflags=NO_WINDOW,
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or "DONE" not in r.stdout:
        raise RuntimeError("TTS lỗi:\n" + r.stdout[-600:] + r.stderr[-1200:])
    return json.load(open(os.path.join(out_dir, "timing.json"), encoding="utf-8"))


def make_video(script, cfg, settings, name, log=print):
    out_dir = os.path.join(settings["output_dir"], datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_" + slug(name))
    os.makedirs(out_dir, exist_ok=True)
    items = [("post_image.png", script.get("post", {}))]
    items += [(f"comment_{k + 1:02d}_image.png", c) for k, c in enumerate(script.get("comments", []))]
    for fname, item in items:   # chép hình vào thư mục video để video tự đủ, xoá file tạm
        img = item.get("image")
        if not isinstance(img, str) or not os.path.exists(img):
            item.pop("image", None)
            continue
        if os.path.dirname(os.path.abspath(img)) != out_dir:
            dst = os.path.join(out_dir, fname)
            shutil.copyfile(img, dst)
            if os.path.basename(img).startswith("_photo_"):
                os.remove(img)
            item["image"] = dst
    json.dump(script, open(os.path.join(out_dir, "script.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"VieNeu đọc {len(script['comments']) + 1} câu...")
    timing = tts(script, cfg, out_dir)
    log(f"dựng video {timing['total']:.1f}s...")
    mp4 = os.path.join(out_dir, "video.mp4")
    info = render(script, timing, os.path.join(out_dir, "voice.wav"), mp4, cfg, settings["bg_dir"])
    meta = dict(script.get("yt", {}), file=mp4, duration=timing["total"], source=name,
                background=info.get("background"), synthetic_content=True,
                created=datetime.now().isoformat(timespec="seconds"))
    json.dump(meta, open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f in ("tts_job.json",):
        try:
            os.remove(os.path.join(out_dir, f))
        except OSError:
            pass
    return out_dir, meta


def _cut(job, ref, tag, cache):
    """Cắt hình theo {"index": ảnh chụp thứ mấy, "nth": hình thứ mấy trong ảnh đó (từ trên xuống)} -> đường dẫn PNG."""
    if not isinstance(ref, dict) or not isinstance(ref.get("index"), int) or not 0 <= ref["index"] < len(job["images"]):
        return None
    i = ref["index"]
    if i not in cache:
        cache[i] = detect_photos(job["images"][i])
    photos = cache[i]
    if not photos:
        return None
    nth = ref.get("nth") if isinstance(ref.get("nth"), int) else 0
    photo = photos[min(max(nth, 0), len(photos) - 1)]
    tmp = os.path.join(ROOT, "state", f"_photo_{slug(job['name'])}_{tag}.png")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    photo.save(tmp)
    return tmp


def attach_photos(script, job, log=print):
    """Gắn hình/meme thật vào bài gốc và vào những bình luận AI đánh dấu là có hình."""
    cache = {}
    targets = [("post", script.get("post_image"), script.get("post"))]
    targets += [(f"c{k}", c.get("image"), c) for k, c in enumerate(script.get("comments", []))]
    for tag, ref, item in targets:
        if item is None:
            continue
        item.pop("image", None)
        if not ref:
            continue
        try:
            path = _cut(job, ref, tag, cache)
        except Exception as e:  # noqa: BLE001
            log(f"  ! không cắt được hình ({tag}): {e}")
            continue
        if path:
            item["image"] = path
            w, h = Image.open(path).size
            log(f"  cắt được hình {'của bài' if tag == 'post' else 'của bình luận ' + tag[1:]} {w}x{h}")


def process_job(job, cfg, settings, log=print):
    """Đọc ảnh -> kịch bản -> video. Xong thì đánh dấu đã đọc. Lỗi đăng nhập Claude thì để nguyên trong inbox."""
    inbox = settings["inbox_dir"]
    log(f"▶ {job['name']}: {settings.get('provider_read', 'claude')} đọc {len(job['images'])} ảnh...")
    try:
        script = write_script_from_images(job["images"], cfg, slug(job["name"]), settings.get("provider_read", "claude"))
    except AuthError:
        raise
    except (LLMError, RuntimeError) as e:
        log(f"✖ {job['name']}: {e}")
        mark(job, inbox, "_failed", dict(error=str(e)))
        return None
    attach_photos(script, job, log)
    if script.get("skip"):
        reason = script.get("reason", "")
        log(f"⤼ {job['name']}: Claude bỏ qua ({reason})")
        mark(job, inbox, "_done", dict(skipped=True, reason=reason))
        return None
    try:
        out_dir, meta = make_video(script, cfg, settings, job["name"], log)
    except Exception as e:  # noqa
        log(f"✖ {job['name']}: {e}")
        mark(job, inbox, "_failed", dict(error=str(e)[-1500:], trace=traceback.format_exc()[-1500:]))
        return None
    mark(job, inbox, "_done", dict(output=out_dir, title=meta.get("title")))
    log(f"✔ {job['name']}: {meta.get('title')}")
    return out_dir


def move_to_trash(path):
    """Chuyển file/thư mục vào Thùng rác của Windows (khôi phục lại được)."""
    if not os.path.exists(path):
        return
    if os.name != "nt":
        shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        return
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    fo_delete, flags = 3, 0x40 | 0x10 | 0x04 | 0x400   # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
    op = SHFILEOPSTRUCTW(None, fo_delete, os.path.abspath(path) + "\0", None, flags, False, None, None)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc or op.fAnyOperationsAborted or os.path.exists(path):
        raise OSError(f"Không chuyển được {os.path.basename(path)} vào Thùng rác (file đang mở ở chương trình khác?).")


def list_outputs(output_dir, limit=60):
    res = []
    if not os.path.isdir(output_dir):
        return res
    for name in sorted(os.listdir(output_dir), reverse=True)[:limit]:
        d = os.path.join(output_dir, name)
        if not os.path.exists(os.path.join(d, "video.mp4")):
            continue
        meta = {}
        try:
            meta = json.load(open(os.path.join(d, "metadata.json"), encoding="utf-8"))
        except (OSError, ValueError):
            pass
        res.append(dict(name=name, title=meta.get("title", name), description=meta.get("description", ""),
                        tags=meta.get("tags", []), duration=meta.get("duration"), background=meta.get("background"),
                        source=meta.get("source"), youtube=meta.get("youtube"), youtube_error=meta.get("youtube_error")))
    return res


def load_meta(out_dir):
    try:
        return json.load(open(os.path.join(out_dir, "metadata.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def update_meta(out_dir, **fields):
    """Ghi thêm/xoá trường trong metadata.json của một video (None = xoá)."""
    meta = load_meta(out_dir)
    for k, v in fields.items():
        if v is None:
            meta.pop(k, None)
        else:
            meta[k] = v
    json.dump(meta, open(os.path.join(out_dir, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def scheduled_times(output_dir):
    """Các giờ đăng đã hẹn (RFC 3339 UTC) của những video đã tải lên, để không hẹn trùng khung."""
    out = []
    for o in list_outputs(output_dir, limit=500):
        at = (o.get("youtube") or {}).get("publish_at")
        if at:
            out.append(at)
    return out


# ---------- tự sáng tác ----------
def load_history():
    try:
        return json.load(open(HISTORY_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def composed_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for h in load_history() if str(h.get("at", "")).startswith(today))


def compose_one(cfg, settings, log=print, topic=None):
    """LLM tự nghĩ ra một bài + bình luận, rồi dựng video. Trả về thư mục output (hoặc None nếu bỏ qua/lỗi)."""
    provider = settings.get("provider_compose", "claude")
    hist = load_history()
    log(f"✎ Sáng tác bằng {provider}{' (chủ đề: ' + topic + ')' if topic else ''}...")
    try:
        script = write_script_original(cfg, [h.get("summary") or h.get("hook", "") for h in hist], provider, topic)
    except AuthError:
        raise
    except (LLMError, RuntimeError) as e:
        log(f"✖ sáng tác lỗi: {e}")
        return None
    if script.get("skip"):
        log("⤼ bỏ qua:", script.get("reason"))
        return None
    log(f"  chủ đề '{script['topic']}': {script.get('hook')}")
    try:
        out_dir, meta = make_video(script, cfg, settings, "sangtac-" + slug(script["topic"]), log)
    except Exception as e:  # noqa
        log(f"✖ dựng video lỗi: {e}")
        return None
    hist.append(dict(at=datetime.now().isoformat(timespec="seconds"), topic=script["topic"], hook=script.get("hook"),
                     summary=script.get("summary"), provider=provider, output=out_dir))
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    json.dump(hist, open(HISTORY_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"✔ sáng tác xong: {meta.get('title')}")
    return out_dir
