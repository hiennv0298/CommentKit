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
Mỗi bình luận tối đa ~25 từ, bình luận cuối là cú chốt hài nhất.
- Mỗi bình luận gán một nhân vật (dùng đúng key), nói đúng tính cách. Không nhân vật nào quá 2 lần:
{characters}
  Bài đăng luôn do "nguoi_dang" đọc ("nguoi_dang" cũng có thể trả lời trong bình luận).
- KHÔNG emoji, KHÔNG hashtag trong bình luận.
- Người đăng và người bình luận trên Threads phần lớn là Gen Z: khoảng MỘT NỬA số câu (bài đăng và bình luận) viết kiểu Gen Z Việt Nam: teencode, viết tắt, chữ thường, đôi chỗ không dấu, vd "k/ko" (không), "đc/dc" (được), "j" (gì), "vs" (với), "ng" (người), "mn" (mọi người), "ny" (người yêu), "cx" (cũng), "r" (rồi), "trc" (trước), "bt" (biết), "z/v" (vậy), "nma" (nhưng mà), "ik" (đi), "khum" (không), "ừa", "ủa alo", "j z tr". Nửa còn lại viết bình thường, đúng chính tả, có dấu đầy đủ, nhất là nhân vật lớn tuổi (ông chú, phát thanh viên). Đừng nhồi teencode tới mức khó đọc: người xem phải đọc hiểu ngay. KHÔNG dùng từ tục hay viết tắt tục (vcl, vl, vkl, đm, dm, cc...).
- Trường "tts" là câu cho máy đọc, LUÔN viết đầy đủ, đúng chính tả, có dấu, dù "text" là teencode (vd text "ko bt nma thấy cx dc" -> tts "không biết nhưng mà thấy cũng được"); số viết thành chữ, bỏ ký tự lạ.
- Tên hiển thị là handle giả đã che, vd "h***.92", "m***_ng". Handle phải BỊA NGẪU NHIÊN: KHÔNG lấy chữ cái đầu, đuôi hay số từ tên thật trong ảnh.
- Lượt thích/bình luận dạng "12,4K", "980".
- Tổng thời lượng đọc khoảng {sec_min}-{sec_max} giây (tiếng Việt ~4.5 âm tiết/giây).
- Tránh: tai nạn, bệnh tật, tang lễ, chính trị, tôn giáo, tình dục, bạo lực, miệt thị vùng miền/ngoại hình, \
nội dung khiến một người thật bị nhận ra và xấu hổ. Nếu không đạt thì trả {{"skip": true, "reason": "..."}}.

Trả về DUY NHẤT một JSON hợp lệ, không giải thích:
{{
  "pick_id": "{pick_hint}",
  "hook": "<câu hook 3-7 từ hiện trên đầu video>",
  "summary": "<1 câu tóm tắt ý chính, để chống trùng lần sau>",
  {extra}"post": {{"handle": "h***.92", "time": "3 giờ", "text": "...", "tts": "...", "likes": "12,4K", "replies": "1,1K"}},
  "comments": [{{"who": "ba_thim", "handle": "...", "text": "...", "tts": "...", "likes": "2,3K"{comment_image}}}],
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

def _rules(cfg, pick_hint, extra="", disclaimer="ghi chú: nội dung dựng lại, tên người dùng đã ẩn, giọng đọc AI", comment_image=""):
    v = cfg["video"]
    chars = "\n".join(f'  - {k}: {c["label"]}' for k, c in cfg["characters"].items())
    return RULES.format(channel=cfg["channel_name"], characters=chars, pick_hint=pick_hint, extra=extra, comment_image=comment_image,
                        disclaimer=disclaimer, n_min=max(4, v["max_comments"] - 2), n_max=v["max_comments"],
                        sec_min=v["target_sec"][0], sec_max=v["target_sec"][1])


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
    data["comments"] = [c for c in data.get("comments", []) if c.get("who") in valid and c.get("text")]
    if not data.get("post", {}).get("text") or len(data["comments"]) < 3:
        raise LLMError("Kịch bản thiếu nội dung: " + raw[:300])
    return data


def check_llm(cfg, provider):
    return llm_check(cfg, provider)


def write_script_from_images(images, cfg, job_name="job", provider="claude"):
    prompt = IMAGES_TASK.format() + _rules(cfg, job_name, extra='"post_image": null,\n  ', comment_image=', "image": {"index": 1, "nth": 0}')
    raw = generate(prompt, cfg, provider, images=images)
    return _validate(_extract_json(raw), cfg, raw)


def write_script_original(cfg, history, provider="claude", topic=None):
    topics = cfg.get("compose", {}).get("topics") or ["đi làm"]
    topic = topic or random.choice(topics)
    hist = "\n".join(f"- {h}" for h in history[-60:]) or "- (chưa có)"
    prompt = COMPOSE_TASK.format(topic=topic, history=hist) + _rules(
        cfg, "compose", disclaimer="ghi chú: truyện hư cấu, giọng đọc AI")
    raw = generate(prompt, cfg, provider)
    data = _validate(_extract_json(raw), cfg, raw)
    data["topic"] = topic
    data.pop("post_image", None)
    return data
