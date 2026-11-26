"""Chạy không cần UI.
  python run.py                  # xử lý hết ảnh đang chờ trong inbox rồi thoát
  python run.py --script X.json  # dựng video từ một kịch bản có sẵn (bỏ qua bước đọc ảnh)
  python run.py --compose [chủ đề] # tự sáng tác 1 video (Claude hoặc ChatGPT tuỳ Cài đặt)
Giao diện: python app.py (hoặc nhấp đúp start-ui.bat)"""
import argparse, json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))
from pipeline import AuthError, compose_one, list_jobs, load_cfg, load_settings, make_video, process_job  # noqa: E402


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script")
    ap.add_argument("--compose", nargs="?", const="", default=None)
    ap.add_argument("--provider", choices=["claude", "openai", "gemini"])
    args = ap.parse_args()
    cfg, settings = load_cfg(), load_settings()
    if args.provider:
        settings["provider_read"] = settings["provider_compose"] = args.provider
    if args.compose is not None:
        try:
            out = compose_one(cfg, settings, log, args.compose or None)
        except AuthError as e:
            log("DỪNG:", e)
            return 1
        return 0 if out else 3
    if args.script:
        script = json.load(open(args.script, encoding="utf-8"))
        out_dir, _ = make_video(script, cfg, settings, os.path.basename(args.script), log)
        log("XONG:", out_dir)
        return 0
    jobs = [j for j in list_jobs(settings["inbox_dir"]) if j["ready"]]
    log(f"{len(jobs)} job trong {settings['inbox_dir']}")
    for j in jobs:
        try:
            process_job(j, cfg, settings, log)
        except AuthError as e:
            log("DỪNG:", e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
