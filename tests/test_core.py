import json
import os
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from commentkit import __version__, pipeline as P, voice
from commentkit.crop import detect_photo
from commentkit.llm import LLMError, _env, set_env
from commentkit.paths import home
from commentkit.write_script import _extract_json, _rules, _validate

ROOT = Path(__file__).resolve().parent.parent


def test_home_is_the_test_folder():
    assert str(home()) == os.environ["COMMENTKIT_HOME"]
    assert P.ROOT == os.environ["COMMENTKIT_HOME"]


def test_config_defaults_and_local_override():
    cfg = P.load_cfg()
    assert cfg["tts"]["python"] == str(voice.managed_python())   # mặc định để trống -> bản CommentKit tự cài
    assert cfg["tts"]["hf_home"] == str(voice.default_hf_home())
    assert "nguoi_dang" in cfg["characters"] and cfg["compose"]["topics"]
    P.save_local_cfg({"tts": {"speed": 1.1}, "openai": {"model": "gpt-test"}})
    try:
        cfg = P.load_cfg()
        assert cfg["tts"]["speed"] == 1.1 and cfg["tts"]["gap_sec"] == 0.3   # gộp vào, không thay cả mục
        assert cfg["openai"]["model"] == "gpt-test"
    finally:
        os.remove(P.LOCAL_CFG)


def test_env_file_roundtrip():
    set_env("GEMINI_API_KEY", "abc123")
    try:
        os.environ.pop("GEMINI_API_KEY")
        assert _env("GEMINI_API_KEY") == "abc123"
    finally:
        os.remove(home() / ".env")


def _png(path, size=(300, 500), color=(255, 255, 255)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    old = time.time() - 60
    os.utime(path, (old, old))


def test_jobs_mark_and_retry(tmp_path):
    inbox = tmp_path / "inbox"
    _png(inbox / "a.png")
    _png(inbox / "post" / "01.png")
    _png(inbox / "post" / "02.jpg")
    os.utime(inbox / "post", (time.time() - 60,) * 2)
    _png(inbox / "_done" / "old" / "x.png")
    jobs = {j["name"]: j for j in P.list_jobs(str(inbox))}
    assert set(jobs) == {"a.png", "post"}
    assert len(jobs["post"]["images"]) == 2 and all(j["ready"] for j in jobs.values())

    P.mark(jobs["post"], str(inbox), "_failed", {"error": "boom"})
    assert not (inbox / "post").exists()
    failed = P.list_marked(str(inbox), "_failed")
    assert failed[0]["error"] == "boom" and len(failed[0]["images"]) == 2
    P.retry_failed(str(inbox), failed[0]["name"])
    assert len(P.list_jobs(str(inbox))) == 2
    assert not P.list_marked(str(inbox), "_failed")


def test_fresh_files_wait_until_copied(tmp_path):
    Image.new("RGB", (10, 10)).save(tmp_path / "new.png")
    assert P.list_jobs(str(tmp_path))[0]["ready"] is False


def test_extract_and_validate_script():
    cfg = P.load_cfg()
    comments = ",".join('{"who": "%s", "text": "t"}' % w for w in ("genz", "ba_thim", "nobody", "thanh_bua"))
    raw = '```json\n{"post": {"text": "x"}, "comments": [' + comments + "]}\n```"
    data = _validate(_extract_json(raw), cfg, raw)
    assert [c["who"] for c in data["comments"]] == ["genz", "ba_thim", "thanh_bua"]   # nhân vật lạ bị bỏ
    with pytest.raises(LLMError):
        _validate({"post": {"text": "x"}, "comments": []}, cfg, "")
    with pytest.raises(LLMError):
        _extract_json("not json")
    assert _validate({"skip": True, "reason": "r"}, cfg, "")["skip"]


def test_prompt_lists_the_cast_and_masks_names():
    text = _rules(P.load_cfg(), "job")
    assert "BỊA NGẪU NHIÊN" in text and "nguoi_dang" in text and "ong_chu" in text
    assert "{{" not in text and "}}" not in text   # ngoặc nhọn của template đã được thay


def test_crop_finds_the_meme(tmp_path):
    im = Image.new("RGB", (800, 1400), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for y in range(40, 200, 30):                               # chữ của bài
        d.rectangle((40, y, 600, y + 12), fill=(20, 20, 20))
    d.rectangle((60, 260, 700, 760), fill=(70, 140, 200))      # hình
    d.ellipse((200, 350, 400, 550), fill=(250, 250, 250))       # mảng trắng lớn trong hình
    for y in range(820, 1000, 30):                             # bình luận
        d.rectangle((40, y, 500, y + 12), fill=(20, 20, 20))
    p = tmp_path / "shot.png"
    im.save(p)
    photo = detect_photo(str(p))
    assert photo is not None
    w, h = photo.size
    assert 600 <= w <= 645 and 470 <= h <= 505


def test_render_cards_from_sample_script():
    from commentkit.render import CARD_W, make_cards

    script = json.load(open(ROOT / "samples" / "demo_script.json", encoding="utf-8"))
    cards = make_cards(script)
    assert len(cards) == len(script["comments"]) + 1
    assert all(c.mode == "RGBA" and c.width == CARD_W for c in cards)


def test_voice_status_without_install():
    st = voice.status(P.load_cfg())
    assert st["ok"] is False and st["managed"] is True


def test_version_matches_pyproject_and_changelog():
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in toml
    assert f"## {__version__}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
