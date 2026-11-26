"""Kiểm tra nhanh token Threads và quyền keyword_search (không in token)."""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dotenv import load_dotenv
from threads_api import Threads, ThreadsError

load_dotenv(os.path.join(ROOT, ".env"))
cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
tok = os.getenv("THREADS_ACCESS_TOKEN") or ""
print("token length:", len(tok))
api = Threads(tok, cfg["threads"]["api_base"])
try:
    me = api.me()
    print("me:", me.get("username"))
except ThreadsError as e:
    print("me ERR:", e)
    me = {}
for q in sys.argv[1:] or ["hài", "sếp"]:
    try:
        r = api.search(q, "TOP", 7, 10)
        others = {p.get("username") for p in r} - {me.get("username")}
        print(f"'{q}' -> {len(r)} bài, của người khác: {len(others) > 0}")
        for p in r[:3]:
            print("   ", p.get("has_replies"), (p.get("text") or "")[:80].replace("\n", " "))
    except ThreadsError as e:
        print(f"'{q}' ERR:", e)
