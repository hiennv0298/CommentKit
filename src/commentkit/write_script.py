"""Viết kịch bản bình luận hài bằng AI (Claude CLI, OpenAI hoặc Gemini, xem llm.py).
- write_script_from_images: đọc ảnh chụp màn hình Threads (bài + bình luận) rồi viết lại.
- write_script_original: tự sáng tác một bài + bình luận theo chủ đề (không cần ảnh)."""
import json, random, re

from .llm import generate, check as llm_check, AuthError, LLMError  # noqa: F401

RULES = """KÊNH: YouTube Shorts tiếng Việt "{channel}". Mỗi video là một màn hình chat kiểu Threads (tên người dùng đã ẩn): \
một bài đăng, rồi các "nhân vật" vào bình luận hài, mỗi nhân vật một giọng đọc AI.

QUY TẮC KỊCH BẢN
- Bài đăng 1-4 câu, có tình huống rõ và cú hài/twist.
- Viết {n_min}-{n_max} bình luận hài, có nhịp tung hứng (bình luận sau có thể đáp bình luận trước). \
Mỗi bình luận khoảng 12-30 từ, bình luận cuối là cú chốt hài nhất.
- Mỗi bình luận gán một nhân vật (dùng đúng key), nói đúng tính cách. Không nhân vật nào quá 2 lần:
{characters}
  Bài đăng luôn do "nguoi_dang" đọc ("nguoi_dang" cũng có thể trả lời trong bình luận).
- Trả lời lồng (như Threads): bình luận nào là câu TRẢ LỜI cho một bình luận khác thì đặt NGAY SAU bình luận đó \
và thêm "reply_to": <số thứ tự bình luận được trả lời trong mảng comments, từ 0>. Người đăng bài trả lời thì dùng \
"who": "nguoi_dang" và đúng handle của bài đăng. Có 1-3 cặp hỏi-đáp như vậy thì video tự nhiên hơn; \
bình luận thường thì bỏ trường "reply_to".
- KHÔNG emoji, KHÔNG hashtag trong bình luận.
- Người đăng và người bình luận trên Threads phần lớn là Gen Z: khoảng MỘT NỬA số câu (bài đăng và bình luận) viết kiểu Gen Z Việt Nam: teencode, viết tắt, chữ thường, đôi chỗ không dấu, vd "k/ko" (không), "đc/dc" (được), "j" (gì), "vs" (với), "ng" (người), "mn" (mọi người), "ny" (người yêu), "cx" (cũng), "r" (rồi), "trc" (trước), "bt" (biết), "z/v" (vậy), "nma" (nhưng mà), "ik" (đi), "khum" (không), "ừa", "ủa alo", "j z tr". Nửa còn lại viết bình thường, đúng chính tả, có dấu đầy đủ, nhất là nhân vật lớn tuổi (ông chú, phát thanh viên). Đừng nhồi teencode tới mức khó đọc: người xem phải đọc hiểu ngay. KHÔNG dùng từ tục hay viết tắt tục (vcl, vl, vkl, đm, dm, cc...).
- Trường "tts" là câu cho máy đọc, LUÔN viết đầy đủ, đúng chính tả, có dấu, dù "text" là teencode (vd text "ko bt nma thấy cx dc" -> tts "không biết nhưng mà thấy cũng được"); số viết thành chữ, bỏ ký tự lạ.
- Tên hiển thị là handle giả đã che, vd "h***.92", "m***_ng". Handle phải BỊA NGẪU NHIÊN: KHÔNG lấy chữ cái đầu, đuôi hay số từ tên thật trong ảnh.
- Lượt thích/bình luận dạng "12,4K", "980".
- ĐỘ DÀI: video phải dài {sec_min}-{sec_max} giây, tức là tổng số chữ (âm tiết) của trường "tts" ở bài đăng và \nmọi bình luận cộng lại phải khoảng {syl_min}-{syl_max} chữ. Đếm lại trước khi trả lời; thiếu thì thêm bình luận hài \nhoặc viết bình luận dài hơn một chút, đừng cắt ngắn.
- Tránh: tai nạn, bệnh tật, tang lễ, chính trị, tôn giáo, tình dục, bạo lực, miệt thị vùng miền/ngoại hình, \
nội dung khiến một người thật bị nhận ra và xấu hổ. Nếu không đạt thì trả {{"skip": true, "reason": "..."}}.

Trả về DUY NHẤT một JSON hợp lệ, không giải thích:
{{
  "pick_id": "{pick_hint}",
  "hook": "<câu hook 3-7 từ hiện trên đầu video>",
  "summary": "<1 câu tóm tắt ý chính, để chống trùng lần sau>",
  {extra}"post": {{"handle": "h***.92", "time": "3 giờ", "text": "...", "tts": "...", "likes": "12,4K", "replies": "1,1K"}},
  "comments": [{{"who": "ba_thim", "handle": "...", "text": "...", "tts": "...", "likes": "2,3K"{comment_image}}},
               {{"who": "nguoi_dang", "handle": "<handle của bài đăng>", "text": "...", "tts": "...", "likes": "120", "reply_to": 0}}],
  "yt": {{"title": "<= 70 ký tự, 1-2 hashtag cuối", "description": "<2-3 câu + {disclaimer}>", "tags": ["..."]}}
}}
"""

IMAGES_TASK = """NHIỆM VỤ: Các ảnh chụp màn hình Threads thuộc CÙNG MỘT bài. Tự xác định ảnh nào là BÀI GỐC \
(ảnh có tên người đăng, nội dung chính, lượt thích/bình luận của bài; thường là ảnh đầu) và ảnh nào là BÌNH LUẬN \
(các câu trả lời bên dưới bài). Nếu các ảnh là những bài khác nhau không liên quan thì chọn bài hài nhất làm bài gốc \
và chỉ dùng bình luận của bài đó. Nếu ảnh không phải bài mạng xã hội hoặc không đọc được chữ thì skip.
- Viết lại nội dung bài gốc bằng lời của bạn: giữ ý, giữ cái hài, bỏ tên riêng, địa chỉ, số điện thoại, tên công ty.
- Bình luận thật chỉ là cảm hứng: giữ ý những câu hay nhất nhưng VIẾT LẠI bằng câu chữ khác hẳn (không giữ nguyên quá 4 từ liền nhau của câu gốc), làm cho hài hơn; thêm ít nhất một nửa số bình luận là của riêng bạn.
- Lượt xem/thích thật trong ảnh có thể dùng lại (làm tròn).
- Ảnh có trả lời của trả lời (thụt vào, nối bằng đường kẻ, thường có chữ "Author"/"Tác giả") thì giữ đúng cấu trúc đó \
bằng "reply_to" (câu chữ vẫn viết lại).
- Hình/meme: tool tự cắt hình thật từ ảnh chụp. Chỉ ra hình bằng {{"index": <số thứ tự ảnh chụp chứa hình, từ 0>, \
"nth": <hình thứ mấy trong ảnh chụp đó, đếm từ trên xuống, từ 0>}}.
  + Bài gốc có hình thì điền "post_image" như trên, không có thì "post_image": null.
  + Bình luận thật có hình/meme (vd ảnh mèo, ảnh chế) mà cái hài nằm ở hình thì giữ bình luận đó và thêm \
"image": {{"index": ..., "nth": ...}} vào bình luận ấy; viết chữ của bình luận ăn khớp với hình. Bình luận không có hình thì bỏ trường "image".
  + Viết sao cho người xem hiểu cái hài khi nhìn hình.

"""

COMPOSE_TASK = """NHIỆM VỤ: TỰ SÁNG TÁC một bài đăng kiểu Threads hoàn toàn mới (hư cấu), chủ đề: "{topic}".
- Bài phải đời thường, người Việt trẻ đọc là thấy "đúng tôi", có cú twist bất ngờ ở cuối.
- Giọng văn như người thật đăng mạng: ngôi thứ nhất, hơi than thở hoặc kể khổ, câu ngắn.
- Bình luận phải có ít nhất 2 câu chơi chữ hoặc bắt trend, và 1 câu "phũ" nhẹ nhàng.
- KHÔNG được trùng ý với các bài đã làm dưới đây:
{history}

"""

def syllable_target(cfg):
    """Số chữ cần cho độ dài mong muốn: đo thực tế VieNeu đọc ~4,15 âm tiết/giây ở tốc độ 1.0 (x tốc độ đọc),
    trừ ~4,5 giây lặng đầu/cuối và khoảng nghỉ giữa các câu."""
    lo, hi = cfg["video"]["target_sec"]
    rate = 4.15 * float(cfg.get("tts", {}).get("speed", 1.0))
    return {"syl_min": int((lo - 4.5) * rate), "syl_max": int((hi - 4.5) * rate)}


def syllables(data):
    return sum(len(str(x.get("tts") or x.get("text") or "").split()) for x in [data.get("post") or {}] + list(data.get("comments") or []))


EXTEND_TASK = """Kịch bản JSON dưới đây quá ngắn: {have} chữ, cần khoảng {syl_min}-{syl_max} chữ (tính theo trường "tts") để video dài {sec_min}-{sec_max} giây. Giữ nguyên bài đăng và các bình luận đang có (giữ "reply_to", "image"), THÊM vài bình luận hài mới cho đủ độ dài, đúng mọi quy tắc ở trên, bình luận cuối vẫn là cú chốt hài nhất. Trả về DUY NHẤT JSON đầy đủ.

{script}
"""


def _ensure_length(data, cfg, provider, base_prompt, raw):
    """Kịch bản ngắn hơn ~85% mức tối thiểu thì nhờ AI viết thêm bình luận (một lần)."""
    if data.get("skip"):
        return data
    t = syllable_target(cfg)
    have = syllables(data)
    if have >= 0.85 * t["syl_min"]:
        return data
    lo, hi = cfg["video"]["target_sec"]
    ask = base_prompt + "\n\n" + EXTEND_TASK.format(have=have, sec_min=lo, sec_max=hi, **t,
                                                      script=json.dumps(data, ensure_ascii=False))
    try:
        raw2 = generate(ask, cfg, provider)
        longer = _validate(_extract_json(raw2), cfg, raw2)
    except LLMError:
        return data
    return longer if syllables(longer) > have and not longer.get("skip") else data


def _rules(cfg, pick_hint, extra="", disclaimer="ghi chú: nội dung dựng lại, tên người dùng đã ẩn, giọng đọc AI", comment_image=""):
    v = cfg["video"]
    chars = "\n".join(f'  - {k}: {c["label"]}' for k, c in cfg["characters"].items())
    return RULES.format(channel=cfg["channel_name"], characters=chars, pick_hint=pick_hint, extra=extra, comment_image=comment_image,
                        disclaimer=disclaimer, n_min=max(4, v["max_comments"] - 2), n_max=v["max_comments"],
                        sec_min=v["target_sec"][0], sec_max=v["target_sec"][1], **syllable_target(cfg))


def _extract_json(s):
    s = s.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.S)
    if m:
        s = m.group(1)
    else:
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            s = s[a: b + 1]
    try:
        return json.loads(s)
    except ValueError:
        raise LLMError("Kết quả không phải JSON hợp lệ: " + s[:300]) from None


def _validate(data, cfg, raw):
    if data.get("skip"):
        return data
    valid = set(cfg["characters"])
    kept, new_index = [], {}
    for i, c in enumerate(data.get("comments", [])):
        if isinstance(c, dict) and c.get("who") in valid and c.get("text"):
            new_index[i] = len(kept)
            kept.append(c)
    post_handle = (data.get("post") or {}).get("handle")
    for c in kept:   # đánh số lại reply_to sau khi bỏ bình luận hỏng; trả lời phải đứng sau bình luận cha
        rt = c.pop("reply_to", None)
        if isinstance(rt, int) and rt in new_index and new_index[rt] < kept.index(c):
            c["reply_to"] = new_index[rt]
        if c.get("who") == "nguoi_dang":
            c["author"] = True
            if post_handle:
                c["handle"] = post_handle
    data["comments"] = kept
    if not data.get("post", {}).get("text") or len(data["comments"]) < 3:
        raise LLMError("Kịch bản thiếu nội dung: " + raw[:300])
    return data


def check_llm(cfg, provider):
    return llm_check(cfg, provider)


POST_HINT = """NGƯỜI DÙNG ĐÃ CHỈ RÕ: ảnh số {i} (tên file có chữ "post") là BÀI GỐC. Dùng đúng nội dung ảnh đó làm \
chủ đề câu chuyện, không chọn bài khác; các ảnh còn lại là bình luận của bài này. Nếu ảnh đó có hình/meme thì đó là \
hình của bài: "post_image": {{"index": {i}, "nth": <hình thứ mấy trong ảnh đó>}}.

"""

PRIVATE_TASK = """NHIỆM VỤ: Các ảnh đính kèm (đánh số từ 0) là hình/meme sẽ được đăng CÔNG KHAI trong một video. \
Tìm mọi chỗ trong ảnh có THÔNG TIN CÁ NHÂN làm lộ danh tính người thật: tên người, tên tài khoản hoặc @username, \
số điện thoại, email, địa chỉ nhà, biển số xe, tên trường/công ty gắn với một người cụ thể.
KHÔNG tính: chữ chú thích meme, câu thoại, tên người nổi tiếng hoặc nhân vật hư cấu, logo thương hiệu, chữ chung chung.
Trả về DUY NHẤT một JSON hợp lệ, không giải thích:
{"images": [{"index": 0, "boxes": [[x0, y0, x1, y1]], "what": ["tên người"]}]}
Toạ độ tính theo phần nghìn (0-1000): x theo chiều rộng, y theo chiều cao ảnh, khung ôm trọn phần chữ cần che. \
Ảnh không có gì cần che thì "boxes": []."""


def find_private(images, cfg, provider="claude"):
    """Dò thông tin cá nhân trong các hình sẽ hiện trong video. Trả về {index ảnh: [[x0, y0, x1, y1], ...]}."""
    raw = generate(PRIVATE_TASK, cfg, provider, images=images)
    data = _extract_json(raw)
    out = {}
    for it in data.get("images") or []:
        if isinstance(it, dict) and isinstance(it.get("index"), int):
            boxes = [b for b in it.get("boxes") or [] if isinstance(b, (list, tuple)) and len(b) >= 4]
            if boxes:
                out[it["index"]] = boxes
    return out


def write_script_from_images(images, cfg, job_name="job", provider="claude", post_index=None):
    hint = POST_HINT.format(i=post_index) if post_index is not None else ""
    prompt = hint + IMAGES_TASK.format() + _rules(cfg, job_name, extra='"post_image": null,\n  ', comment_image=', "image": {"index": 1, "nth": 0}')
    raw = generate(prompt, cfg, provider, images=images)
    data = _validate(_extract_json(raw), cfg, raw)
    return _ensure_length(data, cfg, provider, _rules(cfg, job_name), raw)


def write_script_original(cfg, history, provider="claude", topic=None):
    topics = cfg.get("compose", {}).get("topics") or ["đi làm"]
    topic = topic or random.choice(topics)
    hist = "\n".join(f"- {h}" for h in history[-60:]) or "- (chưa có)"
    prompt = COMPOSE_TASK.format(topic=topic, history=hist) + _rules(
        cfg, "compose", disclaimer="ghi chú: truyện hư cấu, giọng đọc AI")
    raw = generate(prompt, cfg, provider)
    data = _ensure_length(_validate(_extract_json(raw), cfg, raw), cfg, provider, prompt, raw)
    data["topic"] = topic
    data.pop("post_image", None)
    return data
