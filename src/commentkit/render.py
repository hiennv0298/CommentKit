"""Dựng video 1080x1920.
Gameplay (lấy ngẫu nhiên trong backgrounds/) phủ kín màn hình, thẻ Threads (tên đã ẩn) hiện lần lượt theo giọng đọc."""
import hashlib, json, os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFont

from .paths import NO_WINDOW

FONT_DIR = os.environ.get("WINDIR", "C:/Windows") + "/Fonts/"
BG, ACTIVE = (16, 16, 16), (36, 36, 36)
WHITE, GRAY, LINE, ACCENT = (243, 245, 247), (119, 119, 119), (51, 51, 51), (255, 214, 10)
PAL = [(229, 115, 115), (240, 98, 146), (186, 104, 200), (121, 134, 203), (79, 195, 247),
       (77, 182, 172), (129, 199, 132), (255, 183, 77), (161, 136, 127), (144, 164, 174)]
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm")


def F(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


FT = dict(
    handle_p=F("segoeuib.ttf", 40), text_p=F("segoeui.ttf", 48), meta=F("segoeui.ttf", 32),
    handle_c=F("segoeuib.ttf", 34), text_c=F("segoeui.ttf", 42), icon=F("seguisym.ttf", 38),
    small=F("segoeui.ttf", 28), avatar=F("segoeuib.ttf", 38),
)
EMOJI = re.compile("[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D]")


def clean(s):
    return EMOJI.sub("", str(s or "")).strip()


def wrap(text, font, width):
    lines = []
    for para in clean(text).split("\n"):
        cur = ""
        for w in para.split():
            test = (cur + " " + w).strip()
            if font.getlength(test) <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def color_of(h):
    return PAL[int(hashlib.md5(h.encode()).hexdigest(), 16) % len(PAL)]


class Layout:
    """Đo sẵn chiều cao từng mục (bài đăng + bình luận) để cuộn chính xác."""

    def __init__(self, script, W, entries=None):
        """entries: [(dữ liệu, là bài gốc?, là trả lời lồng?)]; mặc định là bài gốc + mọi bình luận."""
        self.W = W
        if entries is None:
            entries = [(script["post"], True, False)] + [(c, False, False) for c in script["comments"]]
        self.items = [self._item(d, post, nested) for d, post, nested in entries]
        y = 0
        for it in self.items:
            it["y"] = y
            y += it["h"]
        self.total = y

    def _item(self, d, post, nested=False):
        av = 92 if post else (56 if nested else 72)
        ax = 44 + 72 + 24 if nested else 44            # trả lời lồng: thụt vào, avatar thẳng hàng chữ của bình luận cha
        x_text = ax + av + 22
        tf = FT["text_p" if post else "text_c"]
        lines = wrap(d.get("text", ""), tf, self.W - x_text - 52)
        lh = int(tf.size * 1.32)
        photo = None
        if d.get("image") and os.path.exists(d["image"]):     # hình/meme của bài gốc
            im = Image.open(d["image"]).convert("RGB")
            mw, mh = self.W - x_text - 52, 640    # hình/meme to, dễ xem trên điện thoại
            s = min(mw / im.width, mh / im.height)
            photo = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        h = (18 if nested else 34) + 54 + len(lines) * lh + (photo.height + 18 if photo else 0) + 80 + 18
        return dict(d=d, post=post, nested=nested, av=av, ax=ax, x=x_text, lines=lines, lh=lh, h=h, photo=photo)

    def draw(self, upto, active):
        img = Image.new("RGB", (self.W, self.total + 10), BG)
        dr = ImageDraw.Draw(img)
        shown = self.items[: upto + 1]
        for i, it in enumerate(shown):
            last = i == len(shown) - 1 or shown[i + 1]["nested"]
            self._draw_item(img, dr, it, i == active, line=not last)
            if it["nested"]:                               # đường nối từ avatar bình luận cha xuống câu trả lời
                parent = next(p for p in reversed(shown[:i]) if not p["nested"])
                px = parent["ax"] + parent["av"] / 2
                top = parent["y"] + 34 + parent["av"] + 10
                cy = it["y"] + 18 + it["av"] / 2
                r = 22
                dr.line([px, top, px, cy - r], fill=LINE, width=3)
                dr.arc([px, cy - 2 * r, px + 2 * r, cy], 90, 180, fill=LINE, width=3)
                dr.line([px + r, cy, it["ax"] - 10, cy], fill=LINE, width=3)
        return img

    def _draw_item(self, img, dr, it, active, line=True):
        d, y0, W = it["d"], it["y"], self.W
        if active:
            dr.rounded_rectangle([14, y0 + 6, W - 14, y0 + it["h"] - 6], 26, fill=ACTIVE)
        handle = clean(d.get("handle", "a***")) or "a***"
        av, ax, ay = it["av"], it["ax"], y0 + (18 if it["nested"] else 34)
        dr.ellipse([ax, ay, ax + av, ay + av], fill=color_of(handle))
        dr.text((ax + av / 2, ay + av / 2), handle[:1].upper(), font=FT["avatar"] if av > 60 else FT["meta"], fill=WHITE, anchor="mm")
        hf = FT["handle_p" if it["post"] else "handle_c"]
        x, y = it["x"], ay - 4
        dr.text((x, y), handle, font=hf, fill=WHITE)
        tx = x + hf.getlength(handle) + 16
        tm = clean(d.get("time", "")) or "vừa xong"
        dr.text((tx, y + 4), tm, font=FT["meta"], fill=GRAY)
        if d.get("author") and not it["post"]:            # câu trả lời của chính người đăng bài, như Threads
            dr.text((tx + FT["meta"].getlength(tm) + 12, y + 4), "· Tác giả", font=FT["meta"], fill=GRAY)
        y += 58
        tf = FT["text_p" if it["post"] else "text_c"]
        for ln in it["lines"]:
            dr.text((x, y), ln, font=tf, fill=WHITE)
            y += it["lh"]
        if it.get("photo"):
            ph = it["photo"]
            mask = Image.new("L", ph.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, ph.width - 1, ph.height - 1], 22, fill=255)
            img.paste(ph, (x, y + 8), mask)
            y += ph.height + 18
        y += 14
        cells = [("\u2661", d.get("likes", "")), ("\u2709", d.get("replies", "") if it["post"] else ""), ("\u21BB", "")]
        if it["post"]:
            cells.append(("\u27A4", ""))
        cx = x
        for g, n in cells:
            dr.text((cx, y), g, font=FT["icon"], fill=GRAY)
            cx += 50
            if clean(n):
                dr.text((cx, y + 3), clean(n), font=FT["meta"], fill=GRAY)
                cx += FT["meta"].getlength(clean(n)) + 18
            cx += 24
        if line:
            dr.line([44, y0 + it["h"] - 2, W - 44, y0 + it["h"] - 2], fill=LINE, width=2)


def fit_font(text, max_w, start, minimum=40):
    size = start
    while size > minimum and F("segoeuib.ttf", size).getlength(text) > max_w:
        size -= 2
    return F("segoeuib.ttf", size)


def ease(x):
    return 1 - (1 - x) ** 3


def probe_duration(path):
    r = subprocess.run(creationflags=NO_WINDOW, args=["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout)["format"]["duration"])
    except (ValueError, KeyError):
        return 0.0


def pick_background(bg_dir):
    if not bg_dir or not os.path.isdir(bg_dir):
        return None
    vids = [os.path.join(bg_dir, f) for f in os.listdir(bg_dir) if f.lower().endswith(VIDEO_EXT)]
    return random.choice(vids) if vids else None


CARD_W = 940          # bề rộng thẻ Threads
REGION_Y = 150        # vùng phủ (hook + thẻ) bắt đầu từ y này trên khung 1920
REGION_H = 1250


def groups_of(script):
    """Gom bình luận với các câu trả lời của nó (reply_to) thành nhóm, mỗi nhóm một thẻ.
    Trả về (nhóm [[(dữ liệu, là bài gốc?, là trả lời lồng?)]], nhóm của từng câu đọc [0 = bài gốc, 1.. = bình luận]).
    Câu trả lời chỉ lồng vào thẻ đang hiện; trả lời một bình luận đã qua thì thành thẻ riêng."""
    groups, ids = [[(script["post"], True, False)]], [["post"]]
    line_group = [0]
    for i, c in enumerate(script.get("comments", [])):
        rt = c.get("reply_to")
        if len(groups) > 1 and isinstance(rt, int) and rt in ids[-1]:
            groups[-1].append((c, False, True))
            ids[-1].append(i)
        else:
            groups.append([(c, False, False)])
            ids.append([i])
        line_group.append(len(groups) - 1)
    return groups, line_group


def _card(img):
    band = img.convert("RGBA")
    mask = Image.new("L", band.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, band.width - 1, band.height - 1], 30, fill=255)
    card = Image.new("RGBA", band.size, (0, 0, 0, 0))
    card.paste(band, (0, 0), mask)
    ImageDraw.Draw(card).rounded_rectangle([0, 0, band.width - 1, band.height - 1], 30, outline=(60, 60, 60, 255), width=2)
    return card


def make_cards(script):
    """Thẻ RGBA hiện lúc đọc từng câu (bài gốc, từng bình luận). Câu trả lời lồng nằm chung thẻ với bình luận
    cha: thẻ lúc đọc câu trả lời là thẻ của bình luận cha thêm câu trả lời bên dưới."""
    groups, line_group = groups_of(script)
    cards, stage = [], {}
    for g in line_group:
        s = stage[g] = stage.get(g, -1) + 1
        lay = Layout(script, CARD_W, groups[g])
        full = lay.draw(s, active=-1)
        bottom = lay.items[s]["y"] + lay.items[s]["h"] - 4
        cards.append(_card(full.crop((0, 0, CARD_W, bottom))))
    return cards


def overlay_static(W, script, channel):
    """Phần cố định trong vùng phủ: hook trên cùng."""
    img = Image.new("RGBA", (W, REGION_H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    hook = clean(script.get("hook", ""))
    if hook:
        f = fit_font(hook, W - 140, 60)
        tw = f.getlength(hook)
        dr.rounded_rectangle([W / 2 - tw / 2 - 26, 0, W / 2 + tw / 2 + 26, 90], 20, fill=ACCENT + (255,))
        dr.text((W / 2, 45), hook, font=f, fill=(20, 20, 20), anchor="mm")
    return img


def text_shadow(dr, xy, text, font, fill):
    x, y = xy
    for dx, dy in ((2, 2), (-2, 2), (2, -2), (-2, -2), (0, 3)):
        dr.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 200), anchor="mm")
    dr.text((x, y), text, font=font, fill=fill, anchor="mm")


def render(script, timing, wav, out_mp4, cfg, bg_dir=None):
    """Gameplay phủ kín màn hình; mỗi lúc một thẻ Threads, đổi thẻ đúng lúc giọng đọc tới câu đó."""
    v = cfg["video"]
    W, H, fps = v["width"], v["height"], v["fps"]
    bg = pick_background(bg_dir)
    cards = make_cards(script)
    _, line_group = groups_of(script)
    static = overlay_static(W, script, cfg["channel_name"])
    n = len(cards)
    starts = [max(0.0, t["start"] - 0.1) for t in timing["lines"]][:n]
    starts[0] = 0.0
    CARD_TOP = 130                     # trong vùng phủ, dưới hook
    wm_font, note_font = F("segoeuib.ttf", 40), FT["small"]
    max_card_h = REGION_H - CARD_TOP - 120

    def fit(card):
        if card.height <= max_card_h:
            return card
        s = max_card_h / card.height
        return card.resize((int(card.width * s), max_card_h), Image.LANCZOS)

    # cùng một nhóm dùng chung một tỉ lệ thu nhỏ, để phần trên của thẻ không co lại khi thêm câu trả lời
    scale = {}
    for k, c in enumerate(cards):
        g = line_group[k]
        scale[g] = min(scale.get(g, 1.0), max_card_h / c.height if c.height > max_card_h else 1.0)
    cards = [c if scale[line_group[k]] >= 1 else c.resize((int(c.width * scale[line_group[k]]), int(c.height * scale[line_group[k]])), Image.LANCZOS)
             for k, c in enumerate(cards)]
    cards = [fit(c) for c in cards]

    def frame_grow(k, a):
        """Câu trả lời mới trong cùng thẻ: giữ thẻ cũ, phần mới hiện dần bên dưới."""
        img = static.copy()
        prev, c = cards[k - 1], cards[k].copy()
        x = (W - c.width) // 2
        img.alpha_composite(prev, ((W - prev.width) // 2, CARD_TOP))
        c.putalpha(c.getchannel("A").point(lambda p: int(p * a)))
        img.alpha_composite(c, (x, CARD_TOP))
        dr = ImageDraw.Draw(img)
        yb = CARD_TOP + prev.height + (cards[k].height - prev.height) * a + 46
        text_shadow(dr, (W / 2, yb), "@" + clean(channel_handle(cfg)), wm_font, (255, 255, 255, 170))
        return img.tobytes()

    def frame_for(k, a):
        if a < 1 and k > 0 and line_group[k] == line_group[k - 1]:
            return frame_grow(k, a)
        img = static.copy()
        c = cards[k]
        if a < 1:
            s = 0.9 + 0.1 * a
            c = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.BILINEAR)
            alpha = c.getchannel("A").point(lambda p: int(p * a))
            c.putalpha(alpha)
        x = (W - c.width) // 2
        y = CARD_TOP + (cards[k].height - c.height) // 2
        img.alpha_composite(c, (x, y))
        dr = ImageDraw.Draw(img)
        yb = CARD_TOP + cards[k].height + 46
        text_shadow(dr, (W / 2, yb), "@" + clean(channel_handle(cfg)), wm_font, (255, 255, 255, 170))
        return img.tobytes()

    total = timing["total"]
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if bg:
        dur = probe_duration(bg)
        start = random.uniform(0, max(0.0, dur - total - 1)) if dur > total + 1 else 0
        cmd += ["-stream_loop", "-1", "-ss", f"{start:.2f}", "-i", bg]
        bgf = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1[bg]"
    else:   # chưa có video nền: nền tối chuyển màu nhẹ
        cmd += ["-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0=0x1b1b2f:c1=0x162447:speed=0.01:r={fps}"]
        bgf = f"[0:v]setsar=1[bg]"
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{REGION_H}", "-r", str(fps), "-i", "-", "-i", wav]
    filters = [bgf, f"[bg][1:v]overlay=0:{REGION_Y}:format=auto[v]"]
    amap = "2:a"
    bgm = v.get("bgm")
    if bgm and os.path.exists(bgm):
        cmd += ["-stream_loop", "-1", "-i", bgm]
        filters.append(f"[3:a]volume={v['bgm_volume']}[m];[2:a][m]amix=inputs=2:duration=first:normalize=0[a]")
        amap = "[a]"
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", amap, "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    TR, cache = 0.22, {}
    try:
        for f in range(int(total * fps)):
            t = f / fps
            k = max(i for i in range(n) if starts[i] <= t)
            dt = t - starts[k]
            if dt < TR:
                buf = frame_for(k, ease(dt / TR))
            else:
                if k not in cache:
                    cache = {k: frame_for(k, 1.0)}
                buf = cache[k]
            proc.stdin.write(buf)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    err = proc.stderr.read().decode("utf-8", "replace")
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg lỗi: " + err[-800:])
    subprocess.run(creationflags=NO_WINDOW, args=["ffmpeg", "-v", "error", "-y", "-ss", f"{min(total - 0.5, starts[min(1, n - 1)] + 1):.2f}", "-i", out_mp4,
                    "-frames:v", "1", "-q:v", "3", os.path.splitext(out_mp4)[0] + "_thumb.jpg"])
    return dict(background=os.path.basename(bg) if bg else None)


def channel_handle(cfg):
    return cfg.get("channel_handle") or re.sub(r"\s+", "", cfg["channel_name"]).lower()
