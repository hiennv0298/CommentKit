"""Một chỗ duy nhất gọi mô hình ngôn ngữ. provider:
- "claude": Claude Code CLI (claude -p), đọc ảnh bằng công cụ Read.
- "openai": OpenAI Chat Completions (ChatGPT), ảnh gửi kèm dạng base64. Key: OPENAI_API_KEY trong .env.
- "gemini": Google Gemini API, ảnh gửi kèm trực tiếp. Key: GEMINI_API_KEY trong .env."""
import base64, mimetypes, os, shutil, subprocess, time
import requests

from .paths import NO_WINDOW, home

ROOT = str(home())   # .env nằm trong thư mục dữ liệu (xem paths.home)


class LLMError(RuntimeError):
    pass


class AuthError(LLMError):
    pass


def _env(name):
    v = os.environ.get(name)
    if v:
        return v
    try:
        for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
            k, _, val = line.strip().partition("=")
            if k.strip() == name:
                return val.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def set_env(name, value):
    """Ghi/ghi đè một biến trong .env (dùng khi nhập key trên UI)."""
    p = os.path.join(ROOT, ".env")
    lines = []
    if os.path.exists(p):
        lines = [l for l in open(p, encoding="utf-8").read().splitlines() if not l.strip().startswith(name + "=")]
    lines.append(f"{name}={value.strip()}")
    open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    os.environ[name] = value.strip()


def has_openai_key():
    return bool(_env("OPENAI_API_KEY"))


# ---------- Claude CLI ----------
def _claude(prompt, cfg, images):
    c = cfg["claude"]
    exe = shutil.which(c["cmd"]) or shutil.which(c["cmd"] + ".cmd")
    if not exe:
        raise LLMError("Không tìm thấy lệnh claude trong PATH (cài Claude Code, hoặc chọn Gemini/ChatGPT trong Cài đặt)")
    cmd = [exe, "-p", "--output-format", "text"]
    if images:
        prompt = ("Dùng công cụ Read đọc lần lượt các ảnh sau (theo thứ tự, ảnh đầu là số 0):\n"
                  + "\n".join(f"- {os.path.abspath(p)}" for p in images) + "\n\n" + prompt)
        cmd += ["--allowedTools", "Read"]
        for d in sorted({os.path.dirname(os.path.abspath(p)) for p in images}):
            cmd += ["--add-dir", d]
    if c.get("model"):
        cmd += ["--model", c["model"]]
    r = subprocess.run(cmd, input=prompt, creationflags=NO_WINDOW, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=c.get("timeout_sec", 240))
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        if "authenticate" in out.lower() or "login" in out.lower():
            raise AuthError("Claude CLI chưa đăng nhập: mở terminal chạy `claude` rồi `/login`.")
        raise LLMError(f"claude lỗi ({r.returncode}): {out.strip()[:500]}")
    return r.stdout


# ---------- OpenAI ----------
def _data_url(path):
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def _openai(prompt, cfg, images):
    key = _env("OPENAI_API_KEY")
    if not key:
        raise AuthError("Chưa có OPENAI_API_KEY: nhập key trong Cài đặt của UI (hoặc file .env).")
    o = cfg.get("openai", {})
    content = [{"type": "text", "text": prompt}]
    if images:
        content[0]["text"] = "Các ảnh đính kèm theo thứ tự (ảnh đầu là số 0).\n\n" + prompt
        content += [{"type": "image_url", "image_url": {"url": _data_url(p), "detail": "high"}} for p in images]
    body = {
        "model": o.get("model", "gpt-4o"),
        "messages": [
            {"role": "system", "content": "Bạn là biên kịch hài tiếng Việt. Chỉ trả về một JSON hợp lệ."},
            {"role": "user", "content": content},
        ],
        "response_format": {"type": "json_object"},
    }
    if o.get("temperature") is not None:
        body["temperature"] = o["temperature"]
    base = o.get("base_url", "https://api.openai.com/v1").rstrip("/")
    try:
        r = requests.post(f"{base}/chat/completions", json=body, timeout=o.get("timeout_sec", 180),
                          headers={"Authorization": f"Bearer {key}"})
    except requests.RequestException as e:
        raise LLMError(f"OpenAI không kết nối được: {e}")
    if r.status_code == 429 and ("insufficient_quota" in r.text or "credit" in r.text):
        raise AuthError("Tài khoản OpenAI hết credit: nạp thêm ở platform.openai.com → Settings → Billing.")
    if r.status_code in (401, 403):
        raise AuthError(f"OpenAI từ chối key ({r.status_code}): {r.text[:200]}")
    if r.status_code != 200:
        raise LLMError(f"OpenAI lỗi {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


# ---------- Google Gemini ----------
def _gemini(prompt, cfg, images):
    key = _env("GEMINI_API_KEY")
    if not key:
        raise AuthError("Chưa có GEMINI_API_KEY: lấy key miễn phí ở aistudio.google.com rồi nhập trong Cài đặt.")
    g = cfg.get("gemini", {})
    parts = [{"text": ("Các ảnh đính kèm theo thứ tự (ảnh đầu là số 0).\n\n" if images else "") + prompt}]
    for p in images:
        parts.append({"inline_data": {"mime_type": mimetypes.guess_type(p)[0] or "image/png",
                                      "data": base64.b64encode(open(p, "rb").read()).decode()}})
    body = {
        "system_instruction": {"parts": [{"text": "Bạn là biên kịch hài tiếng Việt. Chỉ trả về một JSON hợp lệ."}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    if g.get("temperature") is not None:
        body["generationConfig"]["temperature"] = g["temperature"]
    # model chính trước, quá tải (503/timeout) thì lần lượt thử model dự phòng
    models = [g.get("model") or "gemini-flash-latest"]
    models += [m for m in g.get("fallback_models", ["gemini-flash-latest", "gemini-flash-lite-latest"]) if m not in models]
    last = ""
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, json=body, timeout=g.get("timeout_sec", 120), headers={"x-goog-api-key": key})
            except requests.Timeout:
                last = f"{model}: quá thời gian chờ"
                break                                   # chậm quá: sang model dự phòng
            except requests.RequestException as e:
                raise LLMError(f"Gemini không kết nối được: {e}")
            if r.status_code == 429:                    # giới hạn lượt/phút của gói miễn phí
                last = f"{model}: 429"
                if "per day" in r.text.lower() or "PerDay" in r.text:
                    raise AuthError("Gemini đã hết lượt miễn phí hôm nay, mai chạy tiếp (hoặc đổi nhà cung cấp).")
                time.sleep(20 * (attempt + 1))
                continue
            if r.status_code in (500, 502, 503, 504):  # máy chủ quá tải: chờ ngắn rồi thử lại
                last = f"{model}: {r.status_code}"
                time.sleep(8 * (attempt + 1))
                continue
            if r.status_code in (401, 403) or (r.status_code == 400 and "API_KEY" in r.text):
                raise AuthError(f"Gemini từ chối key ({r.status_code}): {r.text[:200]}")
            if r.status_code == 404:
                last = f"{model}: không còn dùng được"
                break
            if r.status_code != 200:
                raise LLMError(f"Gemini lỗi {r.status_code}: {r.text[:300]}")
            data = r.json()
            try:
                return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError):
                reason = data.get("promptFeedback", {}).get("blockReason") or data.get("candidates", [{}])[0].get("finishReason")
                raise LLMError(f"Gemini không trả nội dung (lý do: {reason})")
    raise LLMError("Gemini đang quá tải, thử lại sau (" + last + ")")


def has_gemini_key():
    return bool(_env("GEMINI_API_KEY"))


def generate(prompt, cfg, provider, images=None):
    if provider == "gemini":
        return _gemini(prompt, cfg, images or [])
    if provider == "openai":
        return _openai(prompt, cfg, images or [])
    return _claude(prompt, cfg, images or [])


def check(cfg, provider):
    try:
        out = generate('Trả về đúng JSON: {"ok": true}', cfg, provider)
        return True, out.strip()[:60]
    except Exception as e:  # noqa
        return False, str(e)
