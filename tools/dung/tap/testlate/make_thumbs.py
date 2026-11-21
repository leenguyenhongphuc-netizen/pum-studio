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

def hides(sg, tr, vw, vh):
    """các ô che nguồn (hide_src) đang hiệu lực ở giây tr của đoạn, dạng chuỗi filter_complex"""
    fc, last = [], "0:v"
    for j, h in enumerate(sg.get("hide_src", [])):
        if not (float(h.get("start", 0)) <= tr <= float(h.get("end", 1e6))): continue
        x, y, w, hh = h["box"]; bx, by = int(x * vw) // 2 * 2, int(y * vh) // 2 * 2
        bw, bh = max(16, int(w * vw) // 2 * 2), max(16, int(hh * vh) // 2 * 2)
        fc.append(R.soft_hide(last, f"q{j}", f"q{j}", bx, by, bw, bh, vw, vh, 0, 1e6)); last = f"q{j}"
    return fc, last

def grab(src, t, vf="scale=1920:1080", hd=None):
    if hd and hd[0]:
        fc, last = hd; flt = ["-filter_complex", ";".join(fc) + f";[{last}]{vf}[out]", "-map", "[out]"]
    else: flt = ["-vf", vf]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1"] + flt + ["-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
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
import os
E = {s["label"]: s for s in json.load(open(os.environ.get("THUMB_EDL", str(D / "edl_v8m.json"))))["segments"]}
TT = Path(os.environ.get("TT_DIR", str(D / "tt")))
_s = E["Nếm thử"]; fr = grab(_s["path"], 0.7, ("hflip," if _s.get("hflip") else "") + "scale=1920:1080", hides(_s, 0.7, 3840, 2160)).resize((1280, 720), Image.LANCZOS)
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
    T = json.load(open(TT / f"tt{n}.json")); tp = next(x["text"] for x in T["segments"][0]["text"] if x["style"] == "tape")
    COVER = {4: ("s59", 0.5), 6: ("hook1_s117", 1.0)}  # hook không có Pum trên hình: lấy khung có Pum
    sg = next((x for x in T["segments"] if x["id"] == COVER[n][0]), T["segments"][0]) if n in COVER else T["segments"][0]
    src = sg["path"]; a, b = float(sg["in"]), float(sg["out"])
    vw, vh = map(int, subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")[:2])
    keys = R.vtrack(src, a, b, vw, vh, sg)
    t = a + (COVER[n][1] if n in COVER and sg["id"] == COVER[n][0] else min(0.6, (b - a) / 2))
    fr = grab(src, t, ("hflip," if sg.get("hflip") else "") + R.vfit([(0.0, R.c_at(keys, t - a))], 1080, 1920), hides(sg, t - a, vw, vh)).convert("RGBA")
    lab = R.card(f"Phần {n}/7 · Đi đâu thử đó", "label", 1080, 1920, fx, 0.135)
    tap = R.card(tp, "tape", 1080, 1920, fx, 0.56)  # đáy băng chữ phải trên vùng caption TikTok (20% dưới)
    fr.alpha_composite(lab); fr.alpha_composite(tap)
    fr.convert("RGB").save(OUT / f"tiktok_{n}_cover.jpg", quality=92)
print("xong", sorted(p.name for p in OUT.iterdir()))
