"""Thumbnail YouTube (1280x720) và ảnh bìa TikTok (1080x1920) theo chữ ký hình ảnh của Pum.
python3 make_thumbs.py out_dir"""
import sys, json, subprocess
from pathlib import Path
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
import render as R
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
D = Path("/home/claude/pumdung/testlate"); fx = R.fonts()
COC = (57, 38, 48); TAPE = (255, 208, 227); WHITE = (255, 255, 255)

def grab(src, t, vf="scale=1920:1080"):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", vf, "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    import io; return Image.open(io.BytesIO(raw)).convert("RGB")

def tape(text, size, pad=(34, 16), angle=-2, bg=TAPE, fg=COC, font="inter"):
    f = R.F(fx[font], size) if font == "inter" else R.F(fx[font], size, 900)
    d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w = int(d0.textlength(text, font=f)); asc, desc = f.getmetrics(); h = asc + desc
    im = Image.new("RGBA", (w + pad[0] * 2 + 40, h + pad[1] * 2 + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 26, 20 + w + pad[0] * 2, 26 + h + pad[1] * 2], 10, fill=(57, 38, 48, 70))
    im = im.filter(ImageFilter.GaussianBlur(5)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([20, 20, 20 + w + pad[0] * 2, 20 + h + pad[1] * 2], 10, fill=bg)
    d.text((20 + pad[0], 20 + pad[1]), text, font=f, fill=fg)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)

def big(text, size, fill=WHITE, stroke=COC, sw=10):
    f = R.F(fx["inter"], size); d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w = int(d0.textlength(text, font=f)); asc, desc = f.getmetrics()
    im = Image.new("RGBA", (w + 4 * sw, asc + desc + 4 * sw), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 * sw, 2 * sw), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
    return im

# ---------- YouTube 1280x720 ----------
E = {s["label"]: s for s in json.load(open(D / "edl_v8m.json"))["segments"]}
fr = grab(E["Nếm thử"]["path"], 0.7).resize((1280, 720), Image.LANCZOS)
fr = ImageEnhance.Brightness(fr).enhance(1.04)
im = fr.convert("RGBA")
g = Image.new("L", (1280, 720), 0); gd = ImageDraw.Draw(g)
for x in range(700): gd.line([(x, 0), (x, 720)], fill=int(150 * (1 - x / 700) ** 1.6))
im.alpha_composite(Image.merge("RGBA", (Image.new("L", (1280, 720), 57), Image.new("L", (1280, 720), 38), Image.new("L", (1280, 720), 48), g)))
t1 = big("BUÔN MA", 108); t2 = big("THUỘT", 108)
im.alpha_composite(t1, (26, 24)); im.alpha_composite(t2, (26, 24 + t1.height - 44))
im.alpha_composite(tape("Không thích cà phê?!", 58), (30, 400))
im.alpha_composite(tape("Một ngày dậy trễ", 46, angle=1.5, bg=(255, 253, 252)), (40, 540))
im.convert("RGB").save(OUT / "youtube_thumb.jpg", quality=92)

# ---------- TikTok 1080x1920: khung đầu của hook + băng hook + nhãn phần ----------
for n in range(1, 8):
    T = json.load(open(D / "tt" / f"tt{n}.json")); sg = T["segments"][0]
    src = sg["path"]; a, b = float(sg["in"]), float(sg["out"])
    keys = R.vtrack(src, a, b, 1920, 1080, sg)
    t = a + min(0.6, (b - a) / 2)
    fr = grab(src, t, R.vfit([(0.0, R.c_at(keys, t - a))], 1080, 1920)).convert("RGBA")
    tp = next(x["text"] for x in sg["text"] if x["style"] == "tape")
    lab = R.card(f"Phần {n}/7 · Đi đâu thử đó", "label", 1080, 1920, fx, 0.135)
    tap = R.card(tp, "tape", 1080, 1920, fx, 0.63)
    fr.alpha_composite(lab); fr.alpha_composite(tap)
    fr.convert("RGB").save(OUT / f"tiktok_{n}_cover.jpg", quality=92)
print("xong", sorted(p.name for p in OUT.iterdir()))
