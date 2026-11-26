"""Chạy bằng python của venv VieNeu.  Dùng: tts_vieneu.py lines.json out_dir
lines.json: {"gap": 0.35, "lines": [{"id": "00", "tts": "...", "voice": "Hải Đăng", "fx": ""}]}
Kết quả: out_dir/voice.wav (ghép cả bài) + out_dir/timing.json [{id, start, end}]"""
import sys, os, json, subprocess
import numpy as np, soundfile as sf
from vieneu import Vieneu

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # chạy với -I nên PYTHONIOENCODING bị bỏ qua
SR = 48000
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
job = json.load(open(src, encoding="utf-8"))
tts = Vieneu()


def to48(y, sr):
    if sr == SR:
        return y
    import soxr
    return soxr.resample(y, sr, SR)


def trim(x, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(0.03 * SR)): min(len(x), idx[-1] + int(0.08 * SR))]


def synth(text, voice, fx):
    tmp = os.path.join(out, "_tmp.wav")
    for attempt in range(3):
        try:
            a = tts.infer(text, voice=voice)
            tts.save(a, tmp)
            y, sr = sf.read(tmp, dtype="float32")
            y = y.mean(axis=1) if y.ndim > 1 else y
            y = trim(to48(y, sr))
            if fx:
                sf.write(tmp, y, SR, subtype="PCM_16")
                fx_out = os.path.join(out, "_fx.wav")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", fx, "-ar", str(SR), fx_out], check=True)
                y, _ = sf.read(fx_out, dtype="float32")
                y = trim(y.mean(axis=1) if y.ndim > 1 else y)
                os.remove(fx_out)
            if len(y) < SR * 0.3:
                raise RuntimeError("audio quá ngắn")
            return y
        except Exception as e:  # noqa
            print("retry", attempt, e, flush=True)
    raise SystemExit("TTS lỗi: " + text[:60])


parts, timing, t = [], [], 0.4          # 0.4 s lặng đầu video
parts.append(np.zeros(int(0.4 * SR), np.float32))
gap = float(job.get("gap", 0.35))
speed = float(job.get("speed", 1.0))      # tăng tốc giữ nguyên cao độ (atempo)
for ln in job["lines"]:
    chain = ",".join(x for x in (ln.get("fx", ""), f"atempo={speed}" if abs(speed - 1) > 0.01 else "") if x)
    y = synth(ln["tts"], ln["voice"], chain)
    peak = np.abs(y).max()
    y = y / peak * 0.89 if peak > 0 else y
    timing.append(dict(id=ln["id"], start=round(t, 3), end=round(t + len(y) / SR, 3)))
    parts += [y, np.zeros(int(gap * SR), np.float32)]
    t += len(y) / SR + gap
    print(ln["id"], ln["voice"], round(len(y) / SR, 2), flush=True)
parts.append(np.zeros(int(0.9 * SR), np.float32))   # giữ khung cuối
sf.write(os.path.join(out, "voice.wav"), np.concatenate(parts), SR, subtype="PCM_16")
json.dump(dict(total=round(t + 0.9, 3), lines=timing), open(os.path.join(out, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False)
for f in ("_tmp.wav",):
    p = os.path.join(out, f)
    if os.path.exists(p):
        os.remove(p)
print("DONE")
