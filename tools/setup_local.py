"""Ghi config.local.json (cấu hình riêng của máy này, đè lên config.json). Dùng bởi install.ps1.
  python tools/setup_local.py --tts-python <python.exe> --hf-home <thư mục>"""
import argparse, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from pipeline import save_local_cfg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--tts-python")
ap.add_argument("--hf-home")
a = ap.parse_args()
tts = {}
if a.tts_python:
    tts["python"] = a.tts_python.replace("\\", "/")
if a.hf_home:
    tts["hf_home"] = a.hf_home.replace("\\", "/")
if tts:
    save_local_cfg({"tts": tts})
