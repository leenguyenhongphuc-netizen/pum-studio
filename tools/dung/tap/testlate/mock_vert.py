"""Xem nhanh bố cục khung dọc (không dựng video): lấy 1 khung của đoạn, cắt 9:16 theo mặt Pum như render.py,
dán chữ (card) + phụ đề (ASS) + vạch vùng an toàn TikTok, ghép thành ảnh tờ.
python3 mock_vert.py tt.json out.jpg [id1,id2,...]"""
import sys, json, subprocess, os, tempfile
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
import render as R
from PIL import Image, ImageDraw, ImageFont

E = json.load(open(sys.argv[1])); outp = sys.argv[2]
ids = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else None
W, H = 1080, 1920; fx = R.fonts(); tmp = tempfile.mkdtemp()
tiles = []
for i, sg in enumerate(E["segments"]):
    if ids and sg["id"] not in ids: continue
    src = sg.get("path")
    if not src: continue
    a, b = float(sg["in"]), float(sg["out"])
    vw, vh = [int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")[:2]]
    texts = sg.get("text", [])
    tt = (texts[0]["start"] + 0.7) if texts else (b - a) / 2
    tt = min(tt, b - a - 0.05)
    if vh > vw:  # clip dọc: lấp đầy
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    else:
        cx = R.vcx(src, a, b, vw, vh, sg)
        vf = f"scale=-2:{H},crop={W}:{H}:x='min(max(0,iw*{cx:.4f}-{W}/2),iw-{W})':y=0"
    fr = f"{tmp}/f{i}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a + tt:.2f}", "-i", src, "-frames:v", "1", "-vf", vf, fr], check=True)
    im = Image.open(fr).convert("RGBA"); placed = []
    cims = [R.card(x["text"], x.get("style", "tape"), W, H, fx, x.get("pos")) for x in texts]
    PRI = {"label": 0, "tape": 1, "postcard": 2, "price": 3}
    if vh <= vw:
        for j in sorted(range(len(texts)), key=lambda j: PRI.get(texts[j].get("style", "tape"), 9)):
            x = texts[j]
            if x.get("style", "tape") in PRI: cims[j] = R.place_v(cims[j], src, a, 1.0, float(x["start"]), float(x["end"]), W, H, vf, placed)
            placed.append((float(x["start"]), float(x["end"]), cims[j].getbbox() or (0, 0, 0, 0)))
    for x, cim in zip(texts, cims):
        if x["start"] - 0.01 <= tt <= x["end"] + 0.01: im.alpha_composite(cim)
    subs = [[0, 5, t] for s0, s1, t in sg.get("subs", []) if s0 <= tt <= s1][:1]
    if subs:
        ap = f"{tmp}/s{i}.ass"; R.build_ass(subs, W, H, ap)
        im.convert("RGB").save(fr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", fr, "-vf", f"ass='{ap}'", fr + ".png"], check=True)
        im = Image.open(fr + ".png").convert("RGBA")
    d = ImageDraw.Draw(im)
    for y in (0.075 * H, 0.80 * H): d.line([(0, y), (W, y)], fill=(0, 255, 0, 255), width=4)
    d.rectangle([W * 0.865, H * 0.40, W - 2, H * 0.80], outline=(0, 255, 0, 255), width=4)
    d.text((10, 10), f"{sg['id']} {sg.get('label','')[:22]} t={tt:.1f}", fill=(255, 255, 0, 255), font=ImageFont.truetype(fx["nunito"], 40) if isinstance(fx.get("nunito"), str) else None)
    tiles.append(im.convert("RGB").resize((360, 640)))
cols = 6; rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 364, rows * 644), (30, 30, 30))
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * 364, (k // cols) * 644))
sheet.save(outp, quality=88); print(outp, len(tiles))
