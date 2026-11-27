"""Meme cho bình luận khi tự sáng tác.

Nguồn meme:
* 100 meme template phổ biến nhất của Imgflip (api.imgflip.com/get_memes, công khai, không cần tài khoản).
  Danh sách được nhớ 7 ngày; ảnh chỉ tải khi được dùng, lưu ở <home>/state/memes/.
  Chỉ lấy template phản ứng (tối đa 2 ô chữ) để ghép chữ kiểu thanh chú thích phía trên, cộng Drake (chữ vào 2 ô).
* Meme của riêng bạn trong <home>/memes/ (png/jpg/webp/gif tĩnh): tên file nói meme đó là gì,
  vd "meo-ngac-nhien.jpg", "chill-guy.png". AI đọc tên file để chọn.

Ghép chữ: thanh trắng chữ đen phía trên hình (kiểu meme đăng Threads), hoặc chữ vào từng ô với template có ô định sẵn.
"""
import json
import os
import re
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from .paths import home

CATALOG_URL = "https://api.imgflip.com/get_memes"
CATALOG_DAYS = 7
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
FONT_DIR = os.environ.get("WINDIR", "C:/Windows") + "/Fonts/"
# template có ô chữ định sẵn: (x0, y0, x1, y1) theo tỉ lệ 0-1 của ảnh
PANELS = {
    "181913649": [(0.5, 0.0, 1.0, 0.5), (0.5, 0.5, 1.0, 1.0)],   # Drake Hotline Bling: chê / thích
}
SKIP = {"87743020", "112126428", "124822590", "322841258", "131940431", "135256802", "131087935"}  # nhiều ô, cần vị trí chữ


def mem_dir():
    d = home() / "state" / "memes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def user_dir():
    d = home() / "memes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _imgflip():
    p = mem_dir() / "catalog.json"
    try:
        if time.time() - p.stat().st_mtime < CATALOG_DAYS * 86400:
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        r = requests.get(CATALOG_URL, timeout=20)
        memes = r.json()["data"]["memes"]
        p.write_text(json.dumps(memes, ensure_ascii=False), encoding="utf-8")
        return memes
    except (requests.RequestException, ValueError, KeyError):
        try:
            return json.loads(p.read_text(encoding="utf-8"))   # mất mạng: dùng bản cũ
        except (OSError, ValueError):
            return []


def catalog():
    """[{"id", "name", "kind": "caption"|"panels", "panels": n, "source": "imgflip"|"local", ...}]"""
    out = []
    for f in sorted(user_dir().iterdir()):
        if f.suffix.lower() in IMG_EXT:
            name = re.sub(r"[-_]+", " ", f.stem).strip()
            out.append({"id": "local:" + f.name, "name": name, "kind": "caption", "panels": 0, "source": "local", "path": str(f)})
    for m in _imgflip():
        mid = str(m.get("id"))
        if mid in SKIP or not str(m.get("url", "")).startswith("https://i.imgflip.com/"):
            continue
        if mid in PANELS:
            out.append({"id": mid, "name": m["name"], "kind": "panels", "panels": len(PANELS[mid]), "source": "imgflip", "url": m["url"]})
        elif int(m.get("box_count") or 0) <= 2:
            out.append({"id": mid, "name": m["name"], "kind": "caption", "panels": 0, "source": "imgflip", "url": m["url"]})
    return out


def catalog_text(memes, used=()):
    """Danh sách cho AI chọn, meme dùng gần đây đánh dấu để AI tránh lặp."""
    used = set(used)
    lines = []
    for m in memes:
        how = f'chữ vào {m["panels"]} ô' if m["kind"] == "panels" else "chú thích phía trên"
        tag = " (meme riêng của kênh)" if m["source"] == "local" else ""
        old = " [vừa dùng, tránh]" if m["id"] in used else ""
        lines.append(f'- {m["id"]} | {m["name"]}{tag} | {how}{old}')
    return "\n".join(lines)


def _image(m):
    if m["source"] == "local":
        return Image.open(m["path"]).convert("RGB")
    ext = os.path.splitext(m["url"])[1] or ".jpg"
    p = mem_dir() / f"{m['id']}{ext}"
    if not p.exists():
        r = requests.get(m["url"], timeout=30)
        r.raise_for_status()
        p.write_bytes(r.content)
    return Image.open(p).convert("RGB")


def _font(size):
    return ImageFont.truetype(FONT_DIR + "segoeuib.ttf", size)


def _wrap(text, font, width):
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_text(dr, box, text, max_size, min_size=18, fill=(0, 0, 0), stroke=None):
    x0, y0, x1, y1 = box
    for size in range(max_size, min_size - 1, -2):
        f = _font(size)
        lines = _wrap(text, f, x1 - x0 - 16)
        lh = int(size * 1.22)
        if lh * len(lines) <= y1 - y0 - 8:
            break
    y = y0 + (y1 - y0 - lh * len(lines)) / 2
    for ln in lines:
        kw = {"stroke_width": max(2, size // 12), "stroke_fill": stroke} if stroke else {}
        dr.text(((x0 + x1) / 2, y + lh / 2), ln, font=f, fill=fill, anchor="mm", **kw)
        y += lh


def render(meme_id, out_path, caption="", panels=None, width=820):
    """Ghép ảnh meme với chữ, lưu PNG. Trả về đường dẫn, hoặc None nếu không có meme đó."""
    m = next((x for x in catalog() if x["id"] == str(meme_id)), None)
    if not m:
        return None
    im = _image(m)
    s = width / im.width
    im = im.resize((width, max(1, int(im.height * s))), Image.LANCZOS)
    if m["kind"] == "panels" and panels:
        dr = ImageDraw.Draw(im)
        for (x0, y0, x1, y1), text in zip(PANELS[m["id"]], panels):
            box = (int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height))
            _fit_text(dr, box, text, max_size=int(im.height * 0.07))
    if caption:
        f = _font(54)
        lines = _wrap(caption, f, width - 60)[:4]
        bar = int(54 * 1.25 * len(lines)) + 44
        canvas = Image.new("RGB", (width, im.height + bar), (255, 255, 255))
        canvas.paste(im, (0, bar))
        dr = ImageDraw.Draw(canvas)
        y = 22
        for ln in lines:
            dr.text((30, y), ln, font=f, fill=(20, 20, 20))
            y += int(54 * 1.25)
        im = canvas
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path)
    return str(out_path)
