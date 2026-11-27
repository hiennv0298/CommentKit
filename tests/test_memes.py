from PIL import Image

from commentkit import memes, pipeline as P

FAKE = [{"id": "181913649", "name": "Drake Hotline Bling", "url": "https://i.imgflip.com/30b1gx.jpg", "box_count": 2},
        {"id": "97984", "name": "Disaster Girl", "url": "https://i.imgflip.com/23ls.jpg", "box_count": 2},
        {"id": "112126428", "name": "Distracted Boyfriend", "url": "https://i.imgflip.com/1ur9b0.jpg", "box_count": 3},
        {"id": "555", "name": "Five Boxes", "url": "https://i.imgflip.com/x.jpg", "box_count": 5}]


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("COMMENTKIT_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(memes, "_imgflip", lambda: FAKE)
    monkeypatch.setattr(memes, "_image", lambda m: Image.open(m["path"]).convert("RGB") if m["source"] == "local"
                        else Image.new("RGB", (600, 600), (240, 200, 60)))
    Image.new("RGB", (400, 300), (90, 160, 90)).save(memes.user_dir() / "meo-ngac_nhien.jpg")


def test_catalog_keeps_reaction_memes_drake_and_mine(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    cat = {m["id"]: m for m in memes.catalog()}
    assert set(cat) == {"local:meo-ngac_nhien.jpg", "181913649", "97984"}       # bỏ meme nhiều ô
    assert cat["local:meo-ngac_nhien.jpg"]["name"] == "meo ngac nhien" and cat["181913649"]["kind"] == "panels"
    text = memes.catalog_text(list(cat.values()), used=["97984"])
    assert "97984 | Disaster Girl | chú thích phía trên [vừa dùng, tránh]" in text and "chữ vào 2 ô" in text


def test_render_caption_and_panels(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    a = Image.open(memes.render("local:meo-ngac_nhien.jpg", tmp_path / "a.png", caption="Khi sếp nhắn lúc 11 giờ đêm"))
    assert a.width == 820 and a.height > 820 * 300 / 400 and a.getpixel((5, 5)) == (255, 255, 255)   # có thanh chữ trắng
    b = Image.open(memes.render("181913649", tmp_path / "b.png", panels=["Mặc cả", "Siêu thị"]))
    assert b.size == (820, 820)
    assert memes.render("khong-co", tmp_path / "c.png") is None


def test_attach_memes_to_comments(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    script = {"post": {"text": "p"}, "comments": [
        {"who": "genz", "text": "a", "meme": {"id": "181913649", "panels": ["x", "y"]}},
        {"who": "ba_thim", "text": "b"},
        {"who": "ong_chu", "text": "c", "meme": {"id": "khong-co", "caption": "z"}}]}
    used = P.attach_memes(script, log=lambda *a: None)
    assert used == ["181913649"]
    assert script["comments"][0]["image"].endswith(".png") and "meme" not in script["comments"][0]
    assert "image" not in script["comments"][1] and "image" not in script["comments"][2]
