"""Tự cắt hình/meme (của bài gốc hoặc của bình luận) ra khỏi ảnh chụp màn hình Threads.
1. Mặt nạ "khác nền": lệch màu nền > ngưỡng ở BẤT KỲ kênh màu nào (để màu kem/nhạt không bị coi là nền trắng).
2. Tìm "lõi": đoạn hàng dài nhất có độ phủ cao (>55% bề ngang), cho phép hở ngắn. Từ lõi suy ra biên trái/phải.
3. Nới lõi lên/xuống: hàng nào còn ảnh ở mép trái/phải, hoặc phủ >20% trong khoảng biên, thì vẫn thuộc hình
   (hình có thể có mảng trắng lớn, vd nhân vật trắng trong meme).
4. Một ảnh chụp có thể có nhiều hình (bài gốc có hình, bình luận cũng có hình): tìm xong hình nào thì xoá nó khỏi
   mặt nạ rồi tìm tiếp. detect_photos trả các hình theo thứ tự từ trên xuống."""
from PIL import Image, ImageChops


def _mask(im):
    W, H = im.size
    bg = im.getpixel((min(6, W - 1), H // 2))
    d = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    r, g, b = d.split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b).point(lambda v: 255 if v > 22 else 0)
    return m, W, H


def _find(px, W, H, rows, cov, min_h):
    """Hộp (x0, y0, x1, y1) của hình lớn nhất còn lại trên mặt nạ, hoặc None."""
    # lõi: đoạn dài nhất có phủ > 0.55, cho phép hở tối đa 6 hàng
    best, start, gap = (0, -1), None, 0
    for y, c in enumerate(rows):
        if c > 0.55:
            start = y if start is None else start
            gap = 0
            if y - start > best[1] - best[0]:
                best = (start, y)
        elif start is not None:
            gap += 1
            if gap > 6:
                start, gap = None, 0
    y0, y1 = best
    if y1 - y0 < 40:
        return None
    # biên trái/phải: chỉ dựa vào những hàng phủ kín nhất trong lõi (hàng có mảng trắng lớn sẽ làm hụt biên)
    peak = max(rows[y0:y1 + 1])
    ref = [y for y in range(y0, y1 + 1) if rows[y] >= 0.92 * peak][::2] or list(range(y0, y1, 3))
    cols = [sum(1 for y in ref if px[x, y]) / len(ref) for x in range(W)]
    # đoạn cột liền mạch dài nhất (bỏ đường viền khung bài nằm tách riêng)
    bx, s, g = (0, -1), None, 0
    for x, c in enumerate(cols):
        if c > 0.6:
            s = x if s is None else s
            g = 0
            if x - s > bx[1] - bx[0]:
                bx = (s, x)
        elif s is not None:
            g += 1
            if g > 3:
                s, g = None, 0
    x0, x1 = bx
    if x1 - x0 < 120:
        return None

    def inside(y):
        edge = px[x0 + 3, y] or px[x1 - 3, y]
        return edge or cov(y, x0, x1) > 0.2

    def extend(y, step, limit):
        last, gap = y, 0
        while 0 <= y + step < H and gap <= 10 and abs(y - limit) > 0:
            y += step
            if inside(y):
                last, gap = y, 0
            else:
                gap += 1
        return last

    top = extend(y0, -1, 0)
    bot = extend(y1, 1, H - 1)
    if bot - top < min_h:
        return (x0, top, x1, bot, False)
    # tính lại biên trái/phải trên cả chiều cao hình, ngưỡng thấp: cột nào >25% hàng có ảnh là thuộc hình
    ys = list(range(top, bot + 1, 3))
    cols2 = [sum(1 for y in ys if px[x, y]) / len(ys) for x in range(W)]
    run, s, g = (x0, x1), None, 0
    for x, c in enumerate(cols2):
        if c > 0.25:
            s = x if s is None else s
            g = 0
            if x - s > run[1] - run[0]:
                run = (s, x)
        elif s is not None:
            g += 1
            if g > 3:
                s, g = None, 0
    if run[0] <= x0 + 10 and run[1] >= x1 - 10:      # chỉ nới rộng, không thu hẹp
        x0, x1 = run
    return (x0, top, x1, bot, True)


def detect_photos(path, min_h=120, max_n=4):
    """Mọi hình trong ảnh chụp, từ trên xuống dưới: [Image, ...]."""
    im = Image.open(path).convert("RGB")
    m, W, H = _mask(im)
    px = m.load()

    def cov(y, x0=0, x1=None, step=3):
        x1 = W if x1 is None else x1
        n = max(1, (x1 - x0) // step)
        return sum(1 for x in range(x0, x1, step) if px[x, y]) / n

    rows = [cov(y) for y in range(H)]
    found = []
    for _ in range(max_n + 3):           # vài lần thử thêm cho những mảng không đủ cao để là hình
        box = _find(px, W, H, rows, cov, min_h)
        if box is None:
            break
        x0, top, x1, bot, ok = box
        if ok:
            found.append((x0, top, x1, bot))
            if len(found) >= max_n:
                break
        m.paste(0, (0, max(0, top - 2), W, min(H, bot + 3)))   # xoá vùng này khỏi mặt nạ rồi tìm tiếp
        for y in range(max(0, top - 2), min(H, bot + 3)):
            rows[y] = 0.0
    pad = 3   # bỏ viền bo góc
    return [im.crop((x0 + pad, top + pad, x1 - pad + 1, bot - pad + 1)) for x0, top, x1, bot in sorted(found, key=lambda b: b[1])]


def detect_photo(path, min_h=120):
    """Hình lớn nhất trong ảnh chụp (hoặc None)."""
    photos = detect_photos(path, min_h)
    return max(photos, key=lambda p: p.width * p.height) if photos else None
