"""Dòng lệnh CommentKit.
  commentkit                        mở cửa sổ app (giống CommentKitApp.exe)
  commentkit run                    xử lý hết ảnh đang chờ trong inbox rồi thoát
  commentkit compose [chủ đề]       tự sáng tác 1 truyện và làm video
  commentkit script X.json          dựng video từ một kịch bản có sẵn (bỏ qua bước AI)
  commentkit install-voices         cài giọng đọc VieNeu (Python riêng, ~1 GB cả model)
  commentkit doctor                 kiểm tra ffmpeg, giọng đọc, AI và thư mục dữ liệu
Tuỳ chọn cho run/compose: --provider claude|openai|gemini"""
import argparse
import json
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import __version__


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def _setup_console():
    for s in (sys.stdout, sys.stderr):
        if s is not None and hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")


def build_parser():
    ap = argparse.ArgumentParser(prog="commentkit", description="Làm YouTube Shorts bình luận hài.")
    ap.add_argument("--version", action="version", version=f"CommentKit {__version__}")
    sub = ap.add_subparsers(dest="command")
    for name, help_ in (("run", "xử lý inbox một lần"), ("compose", "sáng tác 1 video")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--provider", choices=["claude", "openai", "gemini"])
        if name == "compose":
            p.add_argument("topic", nargs="?", default="")
    p = sub.add_parser("script", help="dựng video từ file kịch bản JSON")
    p.add_argument("path")
    sub.add_parser("install-voices", help="cài giọng đọc VieNeu-TTS")
    sub.add_parser("doctor", help="kiểm tra cài đặt")
    sub.add_parser("gui", help="mở cửa sổ app")
    return ap


def cmd_doctor():
    from . import pipeline as P, voice
    from .llm import has_gemini_key, has_openai_key
    from .paths import PKG, home

    ok = True

    def line(good, what, detail=""):
        nonlocal ok
        print(f"  [{'OK' if good else '--'}] {what}" + (f": {detail}" if detail else ""))

    print(f"CommentKit {__version__}")
    print(f"  thư mục dữ liệu: {home()}")
    cfg = P.load_cfg()
    ff = shutil.which("ffmpeg")
    line(bool(ff), "ffmpeg", ff or "không thấy")
    ok &= bool(ff)
    web = (PKG / "webui" / "index.html").is_file() and (PKG / "webui" / "commentkit.ico").is_file()
    line(web, "file giao diện", str(PKG / "webui"))
    ok &= web
    line(voice.TTS_SCRIPT.is_file(), "script giọng đọc", str(voice.TTS_SCRIPT))
    ok &= voice.TTS_SCRIPT.is_file()
    vs = voice.status(cfg)
    line(vs["ok"], "Giọng đọc VieNeu", vs["python"] if vs["ok"] else vs["error"] + " (chạy: commentkit install-voices)")
    line(bool(shutil.which("claude") or shutil.which("claude.cmd")), "Claude CLI (không bắt buộc)")
    line(has_gemini_key(), "Key Gemini (không bắt buộc)")
    line(has_openai_key(), "Key OpenAI (không bắt buộc)")
    return 0 if ok else 1


def main(argv=None):
    _setup_console()
    argv = sys.argv[1:] if argv is None else argv
    from .paths import add_bundled_tools

    add_bundled_tools()
    try:
        if not argv or argv == ["gui"]:
            from .gui import main as gui_main

            return gui_main()
        args = build_parser().parse_args(argv)
        if args.command == "doctor":
            return cmd_doctor()
        from . import pipeline as P

        cfg, settings = P.load_cfg(), P.load_settings()
        if args.command == "install-voices":
            from . import voice

            P.save_local_cfg({"tts": {"python": ""}})
            voice.install(P.load_cfg(), log)
            return 0
        if getattr(args, "provider", None):
            settings["provider_read"] = settings["provider_compose"] = args.provider
        if args.command == "compose":
            try:
                out = P.compose_one(cfg, settings, log, args.topic or None)
            except P.AuthError as e:
                log("DỪNG:", e)
                return 1
            return 0 if out else 3
        if args.command == "script":
            script = json.load(open(args.path, encoding="utf-8"))
            out_dir, _ = P.make_video(script, cfg, settings, Path(args.path).stem, log)
            log("XONG:", out_dir)
            return 0
        if args.command == "run":
            jobs = [j for j in P.list_jobs(settings["inbox_dir"]) if j["ready"]]
            log(f"{len(jobs)} job trong {settings['inbox_dir']}")
            for j in jobs:
                try:
                    P.process_job(j, cfg, settings, log)
                except P.AuthError as e:
                    log("DỪNG:", e)
                    return 1
            return 0
        build_parser().print_help()
        return 0
    except KeyboardInterrupt:
        log("Đã dừng.")
        return 130
    except Exception:  # noqa: BLE001 - in lỗi ra, đừng tắt cửa sổ im lặng
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
