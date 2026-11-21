#!/usr/bin/env python3
"""Dựng video từ bản dựng (edl.json) do AI viết.

  python3 -I render.py <ep> <edl.json> [--proxy-only]
Ra: work/<ep>/v<ver>/final.mp4 (1080p), proxy.mp4 (480p để Pum xem trong app), timeline.json, credits.txt
"""
import json, os, re, subprocess, sys, math, shutil, hashlib, urllib.request, urllib.parse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent; REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
WORK = Path(os.environ.get("PUM_WORK", "/home/claude/pumdung"))
CACHE = Path(os.environ.get("PUM_CACHE", "/home/claude/cache"))
FPS = 30; SR = 48000
COL = {"rose": "#E85C91", "blush": "#FADCE8", "cream": "#FFF8F5", "berry": "#B83268", "cocoa": "#392630",
       "muted": "#806C75", "tape": "#FFD0E3", "paper": "#FFFDFC", "white": "#FFFFFF"}

def sh(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(" ".join(map(str, cmd))[:600]); print(r.stderr[-2500:]); raise SystemExit("ffmpeg lỗi")
    return r

# ---------- phông chữ ----------
FONT_SRC = {
    "BeVietnamPro-ExtraBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/BeVietnamPro-ExtraBold.ttf",
    "Nunito.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/nunito/Nunito%5Bwght%5D.ttf",
    "PlayfairDisplay-Italic.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf",
    "BeVietnamPro-BlackItalic.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/bevietnampro/BeVietnamPro-BlackItalic.ttf",
}
def fonts():
    d = CACHE / "fonts"; d.mkdir(parents=True, exist_ok=True)
    for n, u in FONT_SRC.items():
        if not (d / n).exists():
            (d / n).write_bytes(urllib.request.urlopen(u, timeout=60).read())
    home = Path.home() / ".fonts"; home.mkdir(exist_ok=True)
    for f in d.glob("*.ttf"):
        if not (home / f.name).exists(): shutil.copy(f, home / f.name)
    subprocess.run(["fc-cache", "-f"], capture_output=True)
    # Inter có sẵn trên máy thiếu dấu tiếng Việt chồng (Ủ, ẩ…), nên chữ nghiêng đậm dùng Be Vietnam Pro Black Italic
    return {"sub": str(d / "BeVietnamPro-ExtraBold.ttf"), "nunito": str(d / "Nunito.ttf"), "play": str(d / "PlayfairDisplay-Italic.ttf"), "inter": str(d / "BeVietnamPro-BlackItalic.ttf")}

def F(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    if wght:
        try: f.set_variation_by_axes([wght])
        except Exception: pass
    return f

# ---------- nhạc ----------
def music_file(tid):
    lib = json.loads((HERE / "music.json").read_text()); t = next((x for x in lib["tracks"] if x["id"] == tid), None)
    if not t: raise SystemExit(f"nhạc {tid} không có trong music.json (chỉ dùng nhạc đã kiểm giấy phép)")
    d = CACHE / "music"; d.mkdir(parents=True, exist_ok=True); p = d / f"{tid}.mp3"
    if not p.exists():
        u = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/" + urllib.parse.quote(t["file"])
        p.write_bytes(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read())
    return p, t

# ---------- hiệu ứng âm thanh tự tạo (không bản quyền) ----------
def sfx_file(name):
    d = CACHE / "sfx"; d.mkdir(parents=True, exist_ok=True); p = d / f"{name}.wav"
    if p.exists(): return p
    sr = SR; rng = np.random.default_rng(7)
    def env(n, a=0.004, r=0.2):
        t = np.arange(n) / sr; e = np.minimum(1, t / a) * np.exp(-t / r); return e
    if name == "pop":
        n = int(0.14 * sr); t = np.arange(n) / sr; f = 900 * np.exp(-t * 18) + 380
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, 0.002, 0.035)
    elif name == "whoosh":
        n = int(0.55 * sr); x = rng.standard_normal(n); t = np.arange(n) / sr
        k = np.sin(np.pi * t / t[-1]) ** 2
        # lọc thông thấp trượt
        y = np.zeros(n); a = 0.0
        for i in range(n):
            c = 0.02 + 0.25 * k[i]; a = a + c * (x[i] - a); y[i] = a
        y = y * k * 2.2
    elif name == "ding":
        n = int(1.1 * sr); t = np.arange(n) / sr
        y = sum(w * np.sin(2 * np.pi * f * t) for f, w in [(1320, 1), (2640, .35), (3960, .15)]) * env(n, 0.003, 0.28) * .5
    elif name == "boop":
        n = int(0.22 * sr); t = np.arange(n) / sr; f = 520 + 260 * t / t[-1]
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, 0.004, 0.08) * .8
    elif name == "tick":
        n = int(0.05 * sr); y = rng.standard_normal(n) * env(n, 0.0005, 0.006) * .6
    elif name == "sparkle":  # chuông lấp lánh đi lên
        n = int(0.9 * sr); t = np.arange(n) / sr; y = np.zeros(n)
        for k, f in enumerate([1568, 1976, 2349, 3136]):
            st = int(k * 0.07 * sr); tt = t[: n - st]
            y[st:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.22) * (0.8 - k * .1)
        y *= 0.6
    elif name == "boing":  # lò xo
        n = int(0.5 * sr); t = np.arange(n) / sr; f = 180 + 140 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 3) + 120 * t
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, 0.003, 0.2)
    elif name == "sad":  # hai nốt đi xuống
        n = int(0.7 * sr); t = np.arange(n) / sr; f = np.where(t < 0.3, 440, 330) * (1 - 0.05 * t)
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.where(t < 0.3, env(n, 0.01, 0.25), np.roll(env(n, 0.01, 0.3), int(0.3 * sr))) * .7
    elif name == "swoosh":  # vụt nhanh cho băng chữ
        n = int(0.3 * sr); x = rng.standard_normal(n); t = np.arange(n) / sr; k = np.sin(np.pi * t / t[-1]) ** 3
        y = np.zeros(n); a = 0.0
        for i in range(n):
            c = 0.05 + 0.45 * k[i]; a = a + c * (x[i] - a); y[i] = a
        y = y * k * 2
    elif name == "click":  # màn trập máy ảnh
        n = int(0.16 * sr); y = rng.standard_normal(n) * (env(n, 0.0005, 0.01) + np.roll(env(n, 0.0005, 0.012), int(0.06 * sr)) * .8) * .7
    elif name == "slide":  # còi trượt đi xuống, theo mặt trời lặn
        n = int(1.3 * sr); t = np.arange(n) / sr; f = 1500 * np.exp(-t * 1.25) + 260
        vib = 1 + 0.012 * np.sin(2 * np.pi * 6 * t)
        y = (np.sin(2 * np.pi * np.cumsum(f * vib) / sr) + .25 * np.sin(4 * np.pi * np.cumsum(f * vib) / sr)) * np.minimum(1, t / 0.05) * np.minimum(1, (t[-1] - t) / 0.25) * .6
    elif name == "drip":  # giọt nước
        n = int(0.32 * sr); t = np.arange(n) / sr; f = 700 + 1300 * (t / t[-1]) ** 0.6
        y = np.sin(2 * np.pi * np.cumsum(f) / sr) * env(n, 0.002, 0.06)
    elif name == "ticktock":  # tích tắc
        n = int(1.3 * sr); y = np.zeros(n)
        for k in range(4):
            st = int(k * 0.3 * sr); m = int(0.05 * sr); tt = np.arange(m) / sr; fq = 2400 if k % 2 == 0 else 1700
            y[st:st + m] += np.sin(2 * np.pi * fq * tt) * np.exp(-tt / 0.008) + rng.standard_normal(m) * np.exp(-tt / 0.004) * .3
    elif name == "puff":  # phụt mây
        n = int(0.45 * sr); x = rng.standard_normal(n); t = np.arange(n) / sr; k = np.exp(-t / 0.12) * np.minimum(1, t / 0.02)
        y = np.zeros(n); a = 0.0
        for i in range(n): a = a + 0.06 * (x[i] - a); y[i] = a
        y = y * k * 3
    elif name == "flutter":  # cánh bướm vỗ
        n = int(0.6 * sr); x = rng.standard_normal(n); t = np.arange(n) / sr
        y = x * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * t)) ** 4 * np.minimum(1, t / 0.05) * np.exp(-t / 0.35) * .5
    else: raise SystemExit("sfx lạ: " + name)
    y = (y / (np.abs(y).max() + 1e-9) * 0.7 * 32767).astype(np.int16)
    import wave
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y.tobytes())
    return p

# ---------- chữ trên hình ----------
def _greedy(draw, words, font, maxw):
    lines = []; cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def soft_hide(src, out, tag, bx, by, bw, bh, fw, fh, s0, s1):
    """Làm mờ mềm một ô (biển số, mặt người lạ): mờ Gauss trên vùng nới rộng, viền mờ dần nên không thành mảng phẳng."""
    m = max(8, min(bw, bh) // 3) // 2 * 2
    ex, ey = max(0, bx - m), max(0, by - m); ex2, ey2 = min(fw, bx + bw + m), min(fh, by + bh + m)
    ew, eh = (ex2 - ex) // 2 * 2, (ey2 - ey) // 2 * 2
    ix0, iy0, ix1, iy1 = bx - ex, by - ey, bx - ex + bw, by - ey + bh
    sig = max(6, max(bw, bh) / 10)
    al = f"255*clip(1-hypot(max(max({ix0}-X\\,X-{ix1})\\,0)\\,max(max({iy0}-Y\\,Y-{iy1})\\,0))/{m}\\,0\\,1)"
    return (f"[{src}]format=yuv420p,split[{tag}a][{tag}b];[{tag}b]crop={ew}:{eh}:{ex}:{ey},gblur=sigma={sig:.1f}:steps=3,split[{tag}c][{tag}d];"
            f"[{tag}d]extractplanes=y,geq=lum={al}[{tag}m];[{tag}c]format=yuva420p[{tag}e];[{tag}e][{tag}m]alphamerge[{tag}f];"
            f"[{tag}a][{tag}f]overlay={ex}:{ey}:enable='between(t,{s0:.2f},{s1:.2f})'[{out}]")
KEEP_TOGETHER = {x.lower() for x in "Buôn Ma Thuột|Buôn Mê|Ea Kao|đồng bào|mọi người|hoàng hôn|cố gắng|cà phê|nhà dài|nhà sàn|Akô Dhông|Trần Nhật Duật|Hồ Tùng Mậu|Bà Già|bánh canh|Mì Hường|hoành thánh|người Nhật|lên farm|trang trại|phụ nữ|đàn ông|tre nứa|ba chỉ|ca cao|lá chè|tự pha|quả chín|chín đỏ|hồ Ea Kao|đi tìm".split("|")}
KEEP_SUB = {x.lower() for x in "Buôn Ma Thuột|Buôn Mê Thuột|Buôn Ma|Ma Thuột|Buôn Mê|Ea Kao|hồ Ea Kao|đồng bào|cơm đồng bào|hoàng hôn|cà phê|nhà sàn|nhà dài|Sài Gòn|Akô Dhông|Trần Nhật Duật|Hồ Tùng Mậu|Mì Hường|hoành thánh|bánh canh|người Nhật|Nhật Bản|trang trại|ca cao|tre nứa|Ama H'Rin|Robusta|Arabica|giờ rồi|9 giờ|6 đến 8 tháng|cà phê chín".split("|")}
def wrap(draw, text, font, maxw):
    """Xuống dòng cân: giữ số dòng tối thiểu nhưng chia đều để không còn một chữ lẻ ở dòng cuối. Hỗ trợ \\n ép xuống dòng."""
    out = []
    for para in text.split("\n"):
        words = para.split(); k = 0  # không xuống dòng giữa tên riêng, từ ghép ("Buôn Ma Thuột", "hoàng hôn")
        while k < len(words):
            for n_ in (3, 2):
                if k + n_ <= len(words) and " ".join(w.strip(",.!?:…").lower() for w in words[k:k + n_]) in KEEP_TOGETHER:
                    words[k:k + n_] = [" ".join(words[k:k + n_])]; break
            k += 1
        if not words: continue
        lines = _greedy(draw, words, font, maxw); n = len(lines)
        if n > 1:
            lo, hi = 0.0, float(maxw)
            for _ in range(18):
                mid = (lo + hi) / 2
                if len(_greedy(draw, words, font, mid)) <= n: hi = mid
                else: lo = mid
            lines = _greedy(draw, words, font, hi)
        out += lines
    return out

def card(text, style, W, H, fx, where=None):
    """Trả về ảnh RGBA cỡ W×H có đúng một mảng chữ theo kiểu thương hiệu."""
    V = H > W  # khung dọc 9:16 (TikTok): chữ to theo bề ngang 1080, đặt trong vùng an toàn của app
    S = W / 1080 if V else W / 1920
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d0 = ImageDraw.Draw(im)
    def block(lines, font, pad, bg, fg, radius, angle, stroke=0, sc=None, lh=1.18):
        asc, desc = font.getmetrics(); lhpx = int((asc + desc) * lh)
        tw = max(d0.textlength(l, font=font) for l in lines)
        bw, bh = int(tw + pad[0] * 2), int(lhpx * len(lines) + pad[1] * 2)
        b = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(b)
        if bg:
            sh_ = Image.new("RGBA", b.size, (0, 0, 0, 0)); ImageDraw.Draw(sh_).rounded_rectangle([20, 26, 20 + bw, 26 + bh], radius, fill=(57, 38, 48, 60))
            b = Image.alpha_composite(b, sh_.filter(ImageFilter.GaussianBlur(6))); d = ImageDraw.Draw(b)
            d.rounded_rectangle([20, 20, 20 + bw, 20 + bh], radius, fill=bg)
        y = 20 + pad[1]
        for l in lines:
            x = 20 + pad[0] + (tw - d.textlength(l, font=font)) / 2
            d.text((x, y), l, font=font, fill=fg, stroke_width=stroke, stroke_fill=sc); y += lhpx
        return b.rotate(angle, resample=Image.BICUBIC, expand=True)
    st = style
    def vbreak(t_, f_, maxw):
        if V and "\n" not in t_ and " · " in t_ and d0.textlength(t_, font=f_) > maxw: return t_.replace(" · ", " ·\n", 1)
        return t_
    if st == "tape":
        f = F(fx["inter"], int((78 if V else 84) * S)); lines = wrap(d0, vbreak(text, f, W * 0.70), f, W * (0.70 if V else 0.66))
        b = block(lines, f, (int(42 * S), int(20 * S)), COL["tape"], COL["cocoa"], int(8 * S), 2)
        if V: pos = (int(W * 0.06), int(H * 0.115))
        else: pos = (int(W * 0.06), int(H * 0.10)) if where != "tr" else (int(W * 0.94) - b.width + 40, int(H * 0.08))
    elif st == "postcard":
        f = F(fx["play"], int(64 * S), 700); lines = wrap(d0, vbreak(text, f, W * 0.70), f, W * (0.70 if V else 0.55))
        b = block(lines, f, (int(36 * S), int(22 * S)), COL["paper"], COL["cocoa"], int(10 * S), -3)
        if V: pos = (int(W * 0.06), int(H * 0.20))
        else: pos = (int(W * 0.06), int(H * 0.70) - (len(lines) - 1) * int(60 * S)) if where != "top" else (int(W * 0.06), int(H * 0.10))
    elif st == "label":
        f = F(fx["nunito"], int((52 if V else 60) * S), 900); lines = wrap(d0, vbreak(text.upper(), f, W * 0.74), f, W * 0.74) if V else [text.upper()]
        b = block(lines, f, (int(34 * S), int(13 * S)), COL["tape"], COL["cocoa"], int(40 * S), 0)
        pos = (int(W * 0.06), int(H * (0.085 if V else 0.08)))
    elif st == "price":
        f = F(fx["nunito"], int(46 * S), 900); lines = [text]
        b = block(lines, f, (int(30 * S), int(12 * S)), COL["white"], COL["berry"], int(40 * S), -2)
        pos = (int(W * 0.70), int(H * 0.12))
    elif st == "big":
        f = F(fx["inter"], int(120 * S)); lines = wrap(d0, text, f, W * 0.8)
        b = block(lines, f, (0, 0), None, COL["white"], 0, 0, stroke=int(8 * S), sc=COL["cocoa"], lh=1.05)
        pos = ((W - b.width) // 2, (H - b.height) // 2)
    elif st == "question":
        f = F(fx["nunito"], int(60 * S), 900); lines = wrap(d0, text, f, W * (0.62 if V else 0.55))
        b = block(lines, f, (int(44 * S), int(30 * S)), COL["white"], COL["berry"], int(28 * S), 0)
        qy = 0.40 if V else 0.62
        pos = ((W - b.width) // 2 - int(90 * S), int(H * qy) - b.height // 2)
        mini = REPO / "brand" / "hello.png"
        if mini.exists():
            m = Image.open(mini).convert("RGBA"); mh = int(330 * S); m = m.resize((int(m.width * mh / m.height), mh))
            im.alpha_composite(m, (min(W - m.width - int(40 * S), pos[0] + b.width - int(30 * S)), int(H * qy) - mh // 2 + (int(mh * 0.75) if V else 0)))
    else: raise SystemExit("kiểu chữ lạ: " + st)
    if isinstance(where, (int, float)) and not isinstance(where, bool): pos = (pos[0], int(H * float(where)))  # "pos": 0.165 = đặt ở 16,5% chiều cao
    im.alpha_composite(b, (max(0, pos[0] - 20), max(0, pos[1] - 20)))
    return im

# ---------- phụ đề (ASS) ----------
def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"
def keep_nbsp(t):
    """phụ đề: nối tên riêng và từ ghép bằng khoảng trắng không ngắt để libass không xuống dòng giữa chúng ("Buôn Ma | Thuột")"""
    for ph in sorted(KEEP_TOGETHER | KEEP_SUB, key=len, reverse=True):
        t = re.sub(r"(?i)(?<![\w])" + r"\s+".join(map(re.escape, ph.split())) + r"(?![\w])", lambda m: m.group(0).replace(" ", "\u00a0"), t)
    return t

def build_ass(subs, W, H, path):
    S = H / 1080
    V = H > W
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pum,Be Vietnam Pro ExtraBold,{62 if V else int(62*S)},&H00FFFFFF,&H00FFFFFF,&H00302639,&H64302639,0,0,0,0,100,100,0,0,1,{5.0 if V else round(4.5*S, 1)},{1.6 if V else round(1.5*S, 1)},2,{70 if V else int(160*S)},{170 if V else int(160*S)},{int(H*0.205) if V else int(64*S)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    subs = sorted(subs, key=lambda z: z[0]); cl = []
    for k, (a, b, t) in enumerate(subs):  # không để hai dòng phụ đề chồng nhau
        if k + 1 < len(subs): b = min(b, subs[k + 1][0] - 0.02)
        cl.append((a, b, t))
    ev = [f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Pum,,0,0,0,,{keep_nbsp(t).replace(chr(10), chr(92)+'N')}" for a, b, t in cl if b - a > 0.15 and t.strip()]
    Path(path).write_text(head + "\n".join(ev) + "\n", encoding="utf-8")

def chunk_words(words, maxc=42, maxdur=3.2):
    """gom chữ thành dòng phụ đề ≤ maxc ký tự, ngắt ở dấu câu"""
    out = []; cur = [];
    for w in words:
        cur.append(w); txt = "".join(x[2] for x in cur).strip()
        if len(txt) >= maxc or re.search(r"[.!?,…]$", w[2].strip()) and len(txt) > 16 or cur[-1][1] - cur[0][0] > maxdur:
            out.append((cur[0][0], cur[-1][1], txt)); cur = []
    if cur: out.append((cur[0][0], cur[-1][1], "".join(x[2] for x in cur).strip()))
    return out

# ---------- dựng một đoạn ----------
_FD = None
def face_box(src, t, W, H, pre="", chain=None):
    """mặt lớn nhất ở giây t (để đặt doodle cạnh mặt, không đè mặt)"""
    global _FD
    try:
        import cv2
        if _FD is None:
            _FD = cv2.FaceDetectorYN.create("/home/claude/models/face_detection_yunet_2023mar.onnx", "", (320, 320), 0.6, 0.3, 50)
        if callable(chain): chain = chain(t)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t + 0.3:.2f}", "-i", src, "-frames:v", "1", "-vf", chain or f"{pre}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
        if img is None: return None
        _FD.setInputSize((img.shape[1], img.shape[0])); _, f = _FD.detect(img)
        if f is None: return None
        r = max(f, key=lambda r: r[2] * r[3]); return tuple(float(v) for v in r[:4]) if r[2] > min(W, H) * 0.05 else None
    except Exception:
        return None

def doodle_pos(face, W, H, size, j, has_text, used=(), boxes=()):
    """chọn chỗ đặt doodle: không đè mặt (nới 25%), không đè băng chữ góc trái trên, không xuống vùng phụ đề;
    ưu tiên chỗ xa mặt vừa phải, đổi bên giữa các doodle trong cùng cảnh"""
    V = H > W
    C = ([(0.66, 0.24), (0.06, 0.26), (0.64, 0.36), (0.05, 0.40), (0.06, 0.50), (0.62, 0.10), (0.36, 0.30)] if V else
         [(0.80, 0.09), (0.62, 0.08), (0.84, 0.36), (0.05, 0.38), (0.06, 0.10), (0.30, 0.08), (0.70, 0.50), (0.12, 0.52)])
    best = None
    for cx, cy in C:
        x, y = cx * W, cy * H
        if has_text and cx < 0.5 and cy < 0.32 and not V: continue
        if y + size > H * (0.60 if V else 0.70): continue  # trên phụ đề (và trên vùng nút của TikTok)
        if V and x + size > W * 0.86 and y + size > H * 0.40: continue  # cột nút bên phải của TikTok
        if any(abs(x - ux) < size * 0.9 and abs(y - uy) < size * 0.9 for ux, uy in used): continue
        if any(x < bx1 + 20 and x + size > bx0 - 20 and y < by1 + 20 and y + size > by0 - 20 for bx0, by0, bx1, by1 in boxes): continue  # không chạm chữ
        if face:
            fx_, fy_, fw, fh = face; ex, ey = fw * 0.25, fh * 0.25
            ox = max(0, min(x + size, fx_ + fw + ex) - max(x, fx_ - ex)); oy = max(0, min(y + size, fy_ + fh + ey) - max(y, fy_ - ey))
            if ox * oy > 0: continue
            dx = max(fx_ - ex - (x + size), x - (fx_ + fw + ex), 0); dy = max(fy_ - ey - (y + size), y - (fy_ + fh + ey), 0)
            d = (dx * dx + dy * dy) ** 0.5; sc = -abs(d - W * 0.12)  # gần mặt vừa đủ, không dính mặt
        else:
            sc = -C.index((cx, cy)) * 10
        if best is None or sc > best[0]: best = (sc, x, y)
    if best is None: return None if V else (int(W * 0.80), int(H * 0.09))  # khung dọc: không còn chỗ trống thì bỏ doodle, không đè mặt
    return int(best[1]), int(best[2])

SEG_VER = "s1"
VSEG_VER = "v5"  # chỉ khung dọc: đổi khi sửa cách cắt cửa sổ 9:16 / đặt chữ né mặt (không làm mất kho đoạn của bản ngang)
DOODLE_VER = "d2"  # đổi khi sửa cách đặt/vẽ doodle: chỉ dựng lại các đoạn có doodle  # đổi khi sửa cách dựng một đoạn (seg_render, doodle, chữ) để không dùng lại bản cũ

def vcx(src, a, b, vw, vh, sg):
    """tâm cửa sổ 9:16 (tỉ lệ bề ngang khung nguồn): theo mặt lớn nhất ở 3 thời điểm; bị giới hạn trong vùng crop nếu có"""
    if sg.get("cx") is not None and sg.get("cx") != "auto": return float(sg["cx"])
    hw = (vh * 9 / 16) / 2 / vw  # nửa bề ngang cửa sổ, tỉ lệ theo khung nguồn
    xs = []
    try:
        import cv2
        global _FD
        if _FD is None:
            _FD = cv2.FaceDetectorYN.create("/home/claude/models/face_detection_yunet_2023mar.onnx", "", (320, 320), 0.6, 0.3, 50)
        for q in (0.2, 0.5, 0.8):
            t = a + (b - a) * q
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=960:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
            if img is None: continue
            _FD.setInputSize((img.shape[1], img.shape[0])); _, f = _FD.detect(img)
            if f is None: continue
            r = max(f, key=lambda r: r[2] * r[3])
            if r[2] > img.shape[1] * 0.04: xs.append((r[0] + r[2] / 2) / img.shape[1])
    except Exception: pass
    c = float(np.median(xs)) if xs else 0.5
    if sg.get("crop"):
        x0, _, w0, _ = [float(v) for v in sg["crop"]]
        lo, hi = x0 + hw, x0 + w0 - hw
        c = min(max(c, lo), hi) if lo <= hi else x0 + w0 / 2
    return min(max(c, hw), 1 - hw)

_REC = None; _REF = None
def _faces_pum(img):
    """mọi mặt trong ảnh: (x0, x1 theo tỉ lệ bề ngang, bề ngang px, điểm dò, độ giống Pum theo ảnh mẫu hoặc None)"""
    global _FD, _REC, _REF
    import cv2
    if _FD is None:
        _FD = cv2.FaceDetectorYN.create("/home/claude/models/face_detection_yunet_2023mar.onnx", "", (320, 320), 0.6, 0.3, 50)
    if _REC is None:
        _REC = cv2.FaceRecognizerSF.create("/home/claude/models/face_recognition_sface_2021dec.onnx", ""); _REF = np.load("/home/claude/models/pum_ref.npy")
    _FD.setInputSize((img.shape[1], img.shape[0])); _, f = _FD.detect(img)
    out = []
    for r in ([] if f is None else f):
        if r[2] < img.shape[1] * 0.035: continue
        sim = None
        if r[2] >= 36:
            try:
                e = _REC.feature(_REC.alignCrop(img, r)).flatten(); e /= np.linalg.norm(e) + 1e-9; sim = float((_REF @ e).max())
            except Exception: sim = None
        out.append((float(r[0]) / img.shape[1], float(r[0] + r[2]) / img.shape[1], float(r[2]), float(r[14]), sim))
    return out

def vtrack(src, a, b, vw, vh, sg):
    """khung dọc từ cảnh ngang: tâm cửa sổ 9:16 theo mặt Pum (nhận ra Pum bằng ảnh mẫu, không bám tượng hay người lạ).
    Trả về các mốc [(giây trong đoạn, tâm theo tỉ lệ bề ngang)]: 1 mốc = đứng yên (Pum nằm gọn trong khung cả đoạn);
    nhiều mốc = lia theo khi Pum ra gần mép khung. Vùng "crop" của đoạn (bỏ người đi cùng) là giới hạn của cửa sổ."""
    hw = (vh * 9 / 16) / 2 / vw; lo, hi = hw, 1 - hw
    if sg.get("crop"):
        x0, _, w0, _ = [float(v) for v in sg["crop"]]
        if x0 + hw <= x0 + w0 - hw: lo, hi = max(lo, x0 + hw), min(hi, x0 + w0 - hw)
        else: lo = hi = min(max(x0 + w0 / 2, hw), 1 - hw)
    cl = lambda c: min(max(c, lo), hi)
    if sg.get("cx") is not None and sg.get("cx") != "auto": return [(0.0, cl(float(sg["cx"])))]
    n = max(4, min(24, int((b - a) / 0.6) + 1)); smp = []
    try:
        import cv2
        for q in np.linspace(0.03, 0.97, n):
            t = a + (b - a) * q
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf", "scale=960:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), 1)
            if img is not None: smp.append((t - a, _faces_pum(img)))
    except Exception: pass
    pts = [(t, f[0], f[1]) for t, fs in smp for f in [max((f for f in fs if f[4] is not None and f[4] >= 0.28), key=lambda f: f[4], default=None)] if f]
    if not pts:  # không nhận ra Pum: chỉ bám mặt người ở gần máy (to, rõ: anh hướng dẫn, Pum nghiêng mặt); tượng, người xa thì để giữa khung
        pts = [(t, g[0], g[1]) for t, fs in smp for g in [max(fs, key=lambda f: f[2], default=None)] if g and g[3] >= 0.8 and g[1] - g[0] >= 0.08]
    if not pts: return [(0.0, cl((lo + hi) / 2 if sg.get("crop") else 0.5))]
    L = min(p[1] for p in pts); Rr = max(p[2] for p in pts)
    if Rr - L <= 2 * hw * 0.9: return [(0.0, cl((L + Rr) / 2))]
    m = hw * 0.15; c = cl((pts[0][1] + pts[0][2]) / 2); keys = [(0.0, c)]; tp = 0.0
    for t, x0, x1 in pts:
        c0 = c
        if x0 < c - hw + m: c = cl(x0 + hw - m)
        elif x1 > c + hw - m: c = cl(x1 - hw + m)
        if abs(c - c0) > 1e-3:
            if keys[-1][0] < tp - 1e-3: keys.append((round(tp, 3), c0))  # giữ yên tới mẫu trước rồi mới lia
            keys.append((round(max(t, keys[-1][0] + 0.2), 3), c))
        tp = t
    return keys

def c_at(keys, tr):
    if tr <= keys[0][0]: return keys[0][1]
    for (t0, c0), (t1, c1) in zip(keys, keys[1:]):
        if tr < t1: return c0 + (c1 - c0) * (tr - t0) / max(t1 - t0, 1e-3)
    return keys[-1][1]

def vfit(keys, W, H, z=1.0, vy=1.0):
    """bộ lọc khung dọc: phóng theo chiều cao rồi cắt cửa sổ 9:16; tâm lia tuyến tính giữa các mốc (t tính từ đầu đoạn)"""
    if len(keys) == 1: ce = f"{keys[0][1]:.4f}"
    else:
        ce = f"{keys[-1][1]:.4f}"
        for (t0, c0), (t1, c1) in reversed(list(zip(keys, keys[1:]))):
            ce = f"if(lt(t,{t1:.3f}),{c0:.4f}+({c1 - c0:.4f})*(t-{t0:.3f})/{max(t1 - t0, 0.01):.3f},{ce})"
        ce = f"if(lt(t,{keys[0][0]:.3f}),{keys[0][1]:.4f},{ce})"
    if z > 1.001:  # phóng thêm rồi lấy phần dưới (vy=1): đẩy mặt Pum lên cao, phụ đề khỏi đè miệng
        Hz = int(H * z) // 2 * 2
        return f"scale=-2:{Hz},crop={W}:{H}:x='min(max(0,iw*({ce})-{W}/2),iw-{W})':y={int((Hz - H) * vy)}"
    return f"scale=-2:{H},crop={W}:{H}:x='min(max(0,iw*({ce})-{W}/2),iw-{W})':y=0"

def seg_key(sg, clips, W=1920, H=1080):
    """khoá nội dung của một đoạn đã dựng: json đoạn + file nguồn (inode, cỡ, giờ sửa) + mã của render.py/doodle.py"""
    src = sg.get("path") or clips[sg["clip"]]["path"]; st = os.stat(src)
    return hashlib.sha1(json.dumps(sg, sort_keys=True, ensure_ascii=False).encode() + f"{st.st_ino}:{st.st_size}:{st.st_mtime}".encode() + SEG_VER.encode() + (DOODLE_VER.encode() if sg.get("doodles") else b"") + f"{W}x{H}".encode() + (VSEG_VER.encode() if H > W else b"")).hexdigest()[:16]

def seg_cached(i, sg, clips, W, H, fx, tmp, d):
    """dựng lại chỉ những đoạn đổi; đoạn không đổi lấy từ kho segcache (hardlink)"""
    C = d / "segcache"; C.mkdir(exist_ok=True); k = seg_key(sg, clips, W, H)
    out = tmp / f"seg{i:03d}.mp4"; outa = tmp / f"seg{i:03d}.wav"
    if (C / f"{k}.mp4").exists() and (C / f"{k}.wav").exists():
        for x, y in ((C / f"{k}.mp4", out), (C / f"{k}.wav", outa)):
            if y.exists(): y.unlink()
            os.link(x, y)
        NF = max(1, int(round((float(sg["out"]) - float(sg["in"])) / float(sg.get("speed", 1)) * FPS)))
        return out, NF / FPS
    for y in (out, outa):
        if y.exists(): y.unlink()  # file cũ có thể là hardlink vào kho: không ghi đè lên nó
    f, dur = seg_render(i, sg, clips, W, H, fx, tmp)
    for x, y in ((out, C / f"{k}.mp4"), (outa, C / f"{k}.wav")):
        if y.exists(): y.unlink()
        os.link(x, y)
    return f, dur

def place_v(cim, src, a, sp, s0, s1, W, H, chain, placed):
    """khung dọc: nếu mảng chữ đè mặt Pum (nới 10–12%) hoặc đè chữ khác cùng lúc, dời theo chiều dọc tới chỗ trống gần nhất
    trong vùng an toàn (dưới 7,5% trên cùng, trên vùng phụ đề ~62%)"""
    bb = cim.getbbox()
    if not bb: return cim
    faces = [f_ for f_ in (face_box(src, a + q * sp, W, H, "", chain) for q in (s0 + 0.15, (s0 + s1) / 2, max(s0, s1 - 0.15))) if f_]
    h_ = bb[3] - bb[1]
    def bad(y0):
        x0, x1, y1 = bb[0], bb[2], y0 + h_
        for fx0, fy0, fw, fh in faces:  # vùng giữ: từ chân mày tới cằm (chữ được phép nằm trên tóc, trán, mũ)
            if fw < W * 0.05: continue
            if x0 < fx0 + fw * 1.08 and x1 > fx0 - fw * 0.08 and y0 < fy0 + fh * 1.08 and y1 > fy0 + fh * 0.22: return True
        if x1 > W * 0.865 and y1 > H * 0.40 and y0 < H * 0.80: return True  # dải nút bên phải của TikTok
        if y1 > H * 0.70: return True  # dải phụ đề (0,71–0,80 chiều cao)
        for p0, p1, pb in placed:
            if p0 < s1 and p1 > s0 and x0 < pb[2] + 12 and x1 > pb[0] - 12 and y0 < pb[3] + 12 and y1 > pb[1] - 12: return True
        return False
    if not bad(bb[1]): return cim
    ys = sorted(range(int(H * 0.075), int(H * 0.635) - h_, 6), key=lambda y: abs(y - bb[1]))
    for y in ys:
        if not bad(y):
            out = Image.new("RGBA", (W, H), (0, 0, 0, 0)); out.paste(cim, (0, y - bb[1]), cim); return out
    # không chỗ nào trống hẳn: chọn chỗ đè mặt ít nhất (vùng chân mày tới cằm), ưu tiên dưới cằm
    def hit(y0):
        x0, x1, y1 = bb[0], bb[2], y0 + h_; a_ = 0.0
        for fx0, fy0, fw, fh in faces:
            if fw < W * 0.05: continue
            ox = max(0, min(x1, fx0 + fw) - max(x0, fx0)); oy = max(0, min(y1, fy0 + fh) - max(y0, fy0 + fh * 0.22)); a_ += ox * oy
        for p0, p1, pb in placed:
            if p0 < s1 and p1 > s0: a_ += 4 * max(0, min(x1, pb[2]) - max(x0, pb[0])) * max(0, min(y1, pb[3]) - max(y0, pb[1]))
        return a_
    if ys:
        y = min(ys, key=lambda y: (hit(y), -y)); PLACE_MISS.append((round(hit(bb[1])), round(hit(y))))
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0)); out.paste(cim, (0, y - bb[1]), cim); return out
    return cim
PLACE_MISS = []

def seg_render(i, sg, clips, W, H, fx, tmp):
    src = sg.get("path") or clips[sg["clip"]]["path"]; info = clips.get(sg.get("clip"), {})
    a, b = float(sg["in"]), float(sg["out"]); sp = float(sg.get("speed", 1))
    NF = max(1, int(round((b - a) / sp * FPS))); dur = NF / FPS  # đúng số khung: hình và tiếng mỗi đoạn dài bằng nhau tuyệt đối
    vw, vh = info.get("w") or 1920, info.get("h") or 1080
    if sg.get("path") and Path(sg["path"]).exists():  # bản đã prep: lấy đúng cỡ khung
        try:
            vw, vh = [int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", sg["path"]], capture_output=True, text=True).stdout.strip().split(",")[:2]]
        except Exception: pass
    # clip dọc trong video ngang: nền mờ; clip ngang trong video dọc (TikTok): cắt cửa sổ 9:16 theo Pum (vtrack)
    fit = sg.get("fit") or ("blur" if vh > vw and W > H else "fill")
    z = sg.get("zoom")
    vf = []
    pre = ""
    if H > W and fit == "fill" and vw > vh:
        # khung dọc từ cảnh ngang: cửa sổ 9:16 đặt theo mặt Pum; vùng "crop" (bỏ người đi cùng) thành giới hạn cửa sổ
        vkeys = vtrack(src, a, b, vw, vh, sg)
        if sg.get("hflip"): vkeys = [(t_, 1 - c_) for t_, c_ in vkeys]  # tâm đo trên hình chưa lật
        vf.append(vfit(vkeys, W, H, float(sg.get("vzoom", 1)), float(sg.get("vy", 1))))
        vchain = lambda ta: ("hflip," if sg.get("hflip") else "") + vfit([(0.0, c_at(vkeys, ta + 0.3 - a))], W, H, float(sg.get("vzoom", 1)), float(sg.get("vy", 1)))  # khung tĩnh đúng lúc ta (cho dò mặt 1 khung)
    elif sg.get("crop"):  # cắt khung (bỏ mép có người đi cùng): [x, y, w, h] tỉ lệ 0..1 của khung gốc
        cx, cy, cw, ch_ = [float(v) for v in sg["crop"]]
        pre = f"crop=trunc(iw*{cw}/2)*2:trunc(ih*{ch_}/2)*2:trunc(iw*{cx}):trunc(ih*{cy}),"
        vf.append(pre[:-1])
    if H > W and fit == "fill" and vw > vh: pass
    elif fit == "blur":
        vf.append(f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=28,eq=brightness=-0.06[bg];[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0")
    else:
        vf.append(f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
    if z:
        z0, z1 = z if isinstance(z, list) else (1.0, 1.06)
        vf.append(f"scale={int(W*1.12)}:{int(H*1.12)},zoompan=z='{z0}+({z1}-{z0})*on/{max(1,int(dur*FPS))}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}")
    if sp != 1: vf.append(f"setpts=PTS/{sp}")
    vf.append(f"fps={FPS},format=yuv420p")
    if sg.get("look") == "warm": vf.insert(-1, "eq=saturation=1.08:gamma=1.02")
    if sg.get("bright"): vf.insert(-1, f"eq=brightness={float(sg['bright']):.2f}")
    inputs = ["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src]
    # che trên khung nguồn (trước khi cắt khung ngang/dọc): "hide_src":[{"box":[x,y,w,h] tỉ lệ 0..1 của khung nguồn, "start", "end"}]
    # dùng cho biển số lọt lưới máy dò (ví dụ biển nằm sát mép khung): đúng chỗ ở cả bản ngang lẫn bản dọc
    src0 = "0:v"; pre_fc = []
    for j, h in enumerate(sg.get("hide_src", [])):
        x, y, w, hh = h["box"]; bx, by = int(x * vw) // 2 * 2, int(y * vh) // 2 * 2
        bw, bh = max(16, int(w * vw) // 2 * 2), max(16, int(hh * vh) // 2 * 2)
        s0, s1 = float(h.get("start", 0)), float(h.get("end", 1e6))
        pre_fc.append(soft_hide(src0, f"q{j}", f"q{j}", bx, by, bw, bh, vw, vh, s0, s1)); src0 = f"q{j}"
    if sg.get("hflip"):
        vf.insert(0, "hflip")
        if not (H > W and fit == "fill" and vw > vh): pre = "hflip," + pre
    fc = pre_fc + [f"[{src0}]{','.join(vf)}[v0]"]; last = "v0"; k = 1
    tboxes = []  # (bắt đầu, kết thúc, hộp chữ) để doodle né
    # che người đi cùng, biển số xe: "hide":[{"box":[x,y,w,h] (tỉ lệ 0..1 của khung ra), "start":giây, "end":giây}]
    for j, h in enumerate(sg.get("hide", [])):
        x, y, w, hh = h["box"]; bx, by = int(x * W) // 2 * 2, int(y * H) // 2 * 2
        bw, bh = max(16, int(w * W) // 2 * 2), max(16, int(hh * H) // 2 * 2)
        s0, s1 = float(h.get("start", 0)), float(h.get("end", dur))
        fc.append(soft_hide(last, f"h{j}", f"h{j}", bx, by, bw, bh, W, H, s0, s1)); last = f"h{j}"
    T_ = sg.get("text", [])
    cims = [card(t["text"], t.get("style", "tape"), W, H, fx, t.get("pos")) for t in T_]
    if H > W and fit == "fill" and vw > vh:  # khung dọc: đặt chữ né mặt Pum; băng chữ được ưu tiên chỗ trước nhãn
        PRI = {"label": 0, "tape": 1, "postcard": 2, "price": 3}; placed = []  # nhãn nhỏ giữ chỗ trên cùng; băng chữ tìm chỗ trống gần nhất
        for j in sorted(range(len(T_)), key=lambda j: PRI.get(T_[j].get("style", "tape"), 9)):
            t = T_[j]
            if t.get("style", "tape") in PRI and not t.get("fixed"):
                cims[j] = place_v(cims[j], src, a, sp, float(t.get("start", 0)), float(t.get("end", dur)), W, H, vchain, placed)
            placed.append((float(t.get("start", 0)), float(t.get("end", dur)), cims[j].getbbox() or (0, 0, 0, 0)))
    for j, t in enumerate(T_):
        png = tmp / f"t{i}_{j}.png"; cim = cims[j]
        cim.save(png)
        tboxes.append((float(t.get("start", 0)), float(t.get("end", dur)), cim.getbbox() or (0, 0, 0, 0)))
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png)]
        s0, s1 = float(t.get("start", 0)), float(t.get("end", dur))
        # chữ nối từ đoạn trước / sang đoạn sau (cont_in/cont_out): không hiện lại, không nảy, không mờ đi ở chỗ nối
        fins = [] if t.get("cont_in") else [f"fade=t=in:st={s0:.2f}:d=0.18:alpha=1"]
        fouts = [] if t.get("cont_out") else [f"fade=t=out:st={max(s0,s1-0.18):.2f}:d=0.18:alpha=1"]
        fade = ",".join(fins + fouts) or "null"
        bounce = "0" if t.get("cont_in") else f"-34*exp(-(t-{s0:.2f})*7)*cos((t-{s0:.2f})*21)"  # bật nảy khi hiện
        fc.append(f"[{k}:v]format=rgba,{fade}[o{k}]"); fc.append(f"[{last}][o{k}]overlay=x=0:y='{bounce}':enable='between(t,{s0:.2f},{s1:.2f})'[v{k}]"); last = f"v{k}"; k += 1
    # doodle vẽ tay: 3 khung rung luân phiên, bật nảy, đặt cạnh mặt Pum (né chữ góc trái trên)
    if sg.get("doodles"):
        from doodle import anim as _anim
        used = []
        for j, dd in enumerate(sg["doodles"]):
            s0, s1 = float(dd["start"]), min(float(dd["end"]), dur - 0.05); size = int(min(W, H) * dd.get("size", 0.21))
            if s1 - s0 < 0.4: continue
            chain_ = vchain if (H > W and fit == "fill" and vw > vh) else None
            fs = [f_ for f_ in (face_box(src, a + q_ * sp, W, H, pre, chain_) for q_ in (s0, (s0 + s1) / 2)) if f_] if fit != "blur" else []
            face = (min(f_[0] for f_ in fs), min(f_[1] for f_ in fs), max(f_[0] + f_[2] for f_ in fs) - min(f_[0] for f_ in fs),
                    max(f_[1] + f_[3] for f_ in fs) - min(f_[1] for f_ in fs)) if fs else None
            txt_on = any(float(t.get("start", 0)) < s1 and float(t.get("end", dur)) > s0 and t.get("style") in ("tape", "label") or t.get("pos") == "top" for t in sg.get("text", []))
            bx_ = [b_ for t0_, t1_, b_ in tboxes if t0_ < s1 and t1_ > s0]
            pos_ = doodle_pos(face, W, H, size, j, txt_on, used, bx_)
            if pos_ is None: continue
            x, y = pos_; used.append((x, y))
            frames, C = _anim(dd["kind"], size, s1 - s0)
            for q, im in enumerate(frames): im.save(tmp / f"d{i}_{j}_{q:03d}.png")
            ox, oy = x - (C - size) // 2, y - (C - size) // 2
            inputs += ["-framerate", "15", "-start_number", "0", "-i", str(tmp / f"d{i}_{j}_%03d.png")]
            fc.append(f"[{k}:v]format=rgba,fps={FPS},setpts=PTS-STARTPTS+{s0:.3f}/TB[dd{k}]")
            fc.append(f"[{last}][dd{k}]overlay=x={ox}:y={oy}:eof_action=pass:enable='between(t,{s0:.2f},{s1:.2f})'[v{k}]"); last = f"v{k}"; k += 1
    # âm thanh
    mode = sg.get("audio", "src"); vol = float(sg.get("vol", 1.0))
    has_a = info.get("audio", True)
    if mode == "mute" or not has_a:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]; fc.append(f"[{k}:a]anull[a0]"); k += 1
    else:
        g = {"src": 1.0, "low": 0.28, "amb": 0.45}.get(mode, 1.0) * vol
        at = f",atempo={sp}" if sp != 1 and 0.5 <= sp <= 2 else ""
        fd = float(sg.get("fade", 0.06))
        clean = (",highpass=f=85,arnndn=m=/home/claude/models/sh.rnnn:mix=0.88,afftdn=nr=8:nf=-38:tn=1,equalizer=f=3200:t=q:w=1.2:g=2,acompressor=threshold=-22dB:ratio=2.5:attack=6:release=140:makeup=2,atrim=start=0.032,asetpts=PTS-STARTPTS"
                 if mode == "src" and Path("/home/claude/models/sh.rnnn").exists() and sg.get("voice") == "noi" else "")
        fc.append(f"[0:a]aresample={SR},aformat=channel_layouts=stereo{at}{clean},volume={g:.3f},afade=t=in:d={fd:.3f},afade=t=out:st={max(0,dur-fd-0.02):.3f}:d={fd+0.02:.3f}[a0]")
    alast = "a0"
    vo = sg.get("vo")
    if vo:
        vsrc = vo.get("path") or clips[vo["clip"]]["path"]
        inputs += ["-ss", f"{float(vo['in']):.3f}", "-to", f"{float(vo['out']):.3f}", "-i", vsrc]
        ms = int(float(vo.get("at", 0.2)) * 1000)
        dn = ",arnndn=m=/home/claude/models/sh.rnnn:mix=0.88,afftdn=nr=8:nf=-38:tn=1,equalizer=f=3200:t=q:w=1.2:g=2,atrim=start=0.032,asetpts=PTS-STARTPTS" if vo.get("speech") and Path("/home/claude/models/sh.rnnn").exists() else ""
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=stereo,highpass=f=85{dn},acompressor=threshold=-20dB:ratio=3:attack=5:release=120,volume={float(vo.get('vol',1.15)):.2f},adelay={ms}|{ms}[vo]")
        fc.append(f"[{alast}][vo]amix=inputs=2:normalize=0:duration=first[am]"); alast = "am"; k += 1
    fc.append(f"[{alast}]aresample={SR},apad,atrim=end_sample={NF * SR // FPS},asetpts=N/SR/TB[aout]")
    fc.append(f"[{last}]fps={FPS},tpad=stop_mode=clone:stop_duration=0.5,trim=end_frame={NF},setpts=N/{FPS}/TB[vfin]")
    out = tmp / f"seg{i:03d}.mp4"; outa = tmp / f"seg{i:03d}.wav"
    # lọc ồn (arnndn + afftdn) làm tiếng trễ ~32 ms: đã bù bằng atrim ở trên.
    # hình (không tiếng) và tiếng (PCM, đúng số mẫu) ghi riêng: ghép AAC nhiều đoạn làm tiếng trễ dần ~0,03 s mỗi chỗ nối
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
        "-map", "[vfin]", "-frames:v", str(NF), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", os.environ.get("PUM_SEG_CRF", "15"), "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
        "-map", "[aout]", "-vn", "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2", str(outa)])
    return out, dur

def seg_subs(sg, scan, t0):
    """phụ đề lấy từ lời thật trong clip (hoặc lời lồng tiếng), đổi sang giờ của video"""
    if sg.get("subs") is not None:
        return [(t0 + s, t0 + e, txt) for s, e, txt in sg["subs"]]
    if not sg.get("sub"): return []
    out = []; sp = float(sg.get("speed", 1))
    def take(cid, a, b, off):
        s = scan.get(cid) or {}
        words = [w for g in s.get("speech", []) for w in g.get("words", []) if w[0] >= a - 0.05 and w[1] <= b + 0.05]
        for s0, s1, txt in chunk_words(words):
            out.append((t0 + off + (s0 - a) / sp, t0 + off + (s1 - a) / sp, txt))
    if sg.get("vo"): v = sg["vo"]; take(v.get("clip"), float(v["in"]), float(v["out"]), float(v.get("at", 0.2)))
    elif sg.get("audio", "src") == "src": take(sg.get("clip"), float(sg["in"]), float(sg["out"]), 0)
    return out

def vcodec_final(total):
    """Bản cuối: mặc định H.264 crf 16. PUM_SEND_MB=400: H.265 (hvc1, xem được trên iPhone) canh đúng dung lượng để gửi trong chat."""
    mb = os.environ.get("PUM_SEND_MB")
    if not mb:
        return ["-c:v", "libx264", "-preset", os.environ.get("PUM_PRESET", "medium"), "-crf", os.environ.get("PUM_CRF", "16")]
    kbps = int(float(mb) * 8 * 1024 * 0.96 / max(1.0, total) - 192)
    return ["-c:v", "libx265", "-preset", os.environ.get("PUM_PRESET", "fast"), "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.6)}k", "-bufsize", f"{kbps * 2}k",
            "-x265-params", "log-level=error:aq-mode=3", "-tag:v", "hvc1"]

def main():
    ep, edl_p = sys.argv[1], Path(sys.argv[2]); proxy_only = "--proxy-only" in sys.argv
    E = json.loads(edl_p.read_text()); d = WORK / str(ep); ver = E.get("ver", 1)
    out = d / f"v{ver}"; tmp = out / "tmp"; tmp.mkdir(parents=True, exist_ok=True)
    W, H = E.get("size", [1920, 1080]); fx = fonts()
    m = json.loads((d / "match.json").read_text()); clips = dict(m["clips"])
    for p, i in m.get("unassigned", {}).items(): clips["u:" + hashlib.sha1(p.encode()).hexdigest()[:8]] = {"path": p, **i}
    scan = json.loads((d / "scan.json").read_text()) if (d / "scan.json").exists() else {}
    segs = E["segments"]; files = []; tl = []; subs = []; t = 0.0; nom = []; tn = 0.0
    for i, sg in enumerate(segs):
        f, dur = seg_cached(i, sg, clips, W, H, fx, tmp, d); files.append(f)
        nom.append((tn, t)); tn += (float(sg["out"]) - float(sg["in"])) / float(sg.get("speed", 1))
        tl.append({"id": sg.get("id", f"s{i+1}"), "label": sg.get("label", ""), "chapter": sg.get("chapter", ""), "start": round(t, 2), "end": round(t + dur, 2),
                   "clip": sg.get("clip"), "in": sg["in"], "out": sg["out"], "kind": sg.get("kind", ""), "text": [x["text"] for x in sg.get("text", [])], "vo": bool(sg.get("vo")),
                   "voice": sg.get("voice", ""), "say": sg.get("say", ""), "voReq": sg.get("voReq")})
        subs += seg_subs(sg, scan, t); t += dur
        print(f"  đoạn {i+1}/{len(segs)} {sg.get('label','')[:40]} {dur:.1f}s")
    total = t
    (tmp / "list.txt").write_text("".join(f"file '{f}'\n" for f in files))
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(tmp / "base.mp4")])
    (tmp / "alist.txt").write_text("".join(f"file '{str(f)[:-4]}.wav'\n" for f in files))
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "alist.txt"), "-c", "copy", str(tmp / "base.wav")])
    def remap(x):  # giờ trong edl (cộng dồn danh nghĩa) -> giờ thật sau khi làm tròn khung
        k = max([j for j, (a_, _) in enumerate(nom) if a_ <= x + 1e-6], default=0); return nom[k][1] + (x - nom[k][0])
    build_ass(subs, W, H, tmp / "subs.ass")
    # chuyển cảnh thương hiệu (webm nền trong) đặt tại điểm nối
    vin = ["-i", str(tmp / "base.mp4")]; fc = []; last = "0:v"; k = 1
    for i, sg in enumerate(segs):
        tr = sg.get("trans")
        if not tr or i == 0: continue
        wf = REPO / "fx" / ("youtube" if W > H else "tiktok") / f"chuyen_canh_{tr}.webm"
        if not wf.exists(): continue
        at = max(0, tl[i]["start"] - 0.8)  # chuyển cảnh 0,8 s, xong 0,25 s sau chỗ nối: không đè lúc Pum bắt đầu nói
        vin += ["-itsoffset", f"{at:.3f}", "-c:v", "libvpx-vp9", "-i", str(wf)]
        fc.append(f"[{k}:v]scale={W}:{H},format=rgba,setpts=(PTS-STARTPTS)/1.25+{at:.3f}/TB[tr{k}]"); fc.append(f"[{last}][tr{k}]overlay=0:0:eof_action=pass[x{k}]"); last = f"x{k}"; k += 1
    assp = str(tmp / "subs.ass").replace(":", "\\:")
    fc.append(f"[{last}]ass='{assp}'[vout]")
    # âm: tiếng gốc + nhạc (tự hạ khi có lời) + hiệu ứng
    # tiếng trộn ở một lượt riêng (mix.wav) rồi mới ghép với hình: trộn chung một lượt với hình làm loudnorm bị cắt đuôi ~3,7 s câm
    ain = []; a_fc = []; ai = 1
    mus = []; credits = []
    for c in E.get("music", []):
        p, info = music_file(c["track"]); credits.append(info["title"])
        st, en = remap(float(c["start"])), remap(float(c["end"])); fr = float(c.get("from", 0)); dur = en - st
        ain += ["-stream_loop", "-1", "-i", str(p)]  # lặp bài nếu đoạn dài hơn bài hoặc bắt đầu giữa bài
        fi, fo = float(c.get("fadein", 1.2)), float(c.get("fadeout", 2.0))
        a_fc.append(f"[{ai}:a]atrim={fr:.2f}:{fr+dur:.2f},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=stereo,volume={float(c.get('vol',0.16)):.3f},afade=t=in:d={fi},afade=t=out:st={max(0,dur-fo):.2f}:d={fo},adelay={int(st*1000)}|{int(st*1000)}[m{ai}]")
        mus.append(f"[m{ai}]"); ai += 1
    sfx = []
    for s in E.get("sfx", []):
        p = sfx_file(s["name"]); ain += ["-i", str(p)]
        ms = int(remap(float(s["at"])) * 1000)
        a_fc.append(f"[{ai}:a]aresample={SR},aformat=channel_layouts=stereo,volume={float(s.get('vol',0.5)):.2f},adelay={ms}|{ms}[f{ai}]"); sfx.append(f"[f{ai}]"); ai += 1
    a_fc.append(f"[0:a]apad,atrim=0:{total+4:.2f},asplit=2[dia][key]")  # dư 4 s: loudnorm giữ 3 s nhìn trước, không để đuôi bị câm
    mix = ["[dia]"]
    if mus:
        a_fc.append(f"{''.join(mus)}amix=inputs={len(mus)}:normalize=0:duration=longest,apad,atrim=0:{total+4:.2f}[mus]")
        a_fc.append("[mus][key]sidechaincompress=threshold=0.05:ratio=3.5:attack=30:release=500:makeup=1[duck]"); mix.append("[duck]")
    else: a_fc.append("[key]anullsink")
    mix += sfx
    a_fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-14:TP=-2:LRA=11,aresample={SR}[aout]")
    mixw = tmp / "mix.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(tmp / "base.wav"), *ain, "-filter_complex", ";".join(a_fc), "-map", "[aout]", "-c:a", "pcm_s16le", str(mixw)])
    vin2 = [*vin, "-i", str(mixw)]; amap = f"{k}:a"
    final = out / "final.mp4"; proxy = out / "proxy.mp4"
    if not proxy_only:
        sh(["ffmpeg", "-y", "-v", "error", *vin2, "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", amap,
            *vcodec_final(total), "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k" if os.environ.get("PUM_SEND_MB") else "256k", "-t", f"{total:.2f}", str(final)])
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-vf", "scale=854:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(proxy)])
    else:
        sh(["ffmpeg", "-y", "-v", "error", *vin2, "-filter_complex", ";".join(fc).replace("[vout]", "[vbig]") + ";[vbig]scale=854:-2[vout]", "-map", "[vout]", "-map", amap,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-r", str(FPS), "-movflags", "+faststart", "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-t", f"{total:.2f}", str(proxy)])
    # ảnh nhỏ mỗi đoạn để app vẽ dải thời gian
    for x in tl:
        mid = (x["start"] + x["end"]) / 2
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(proxy), "-frames:v", "1", "-vf", "scale=160:-2", "-q:v", "6", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
        import base64; x["thumb"] = "data:image/jpeg;base64," + base64.b64encode(r.stdout).decode() if r.stdout else ""
    lib = json.loads((HERE / "music.json").read_text())
    cred = "\n\n".join(lib["credit"].replace("{title}", c) for c in dict.fromkeys(credits))
    (out / "credits.txt").write_text(cred)
    (out / "timeline.json").write_text(json.dumps({"ep": ep, "ver": ver, "dur": round(total, 2), "segments": tl, "subs": [[round(a, 2), round(b, 2), s] for a, b, s in subs], "music": [dict(c, title=music_file(c["track"])[1]["title"]) for c in E.get("music", [])], "credits": cred}, ensure_ascii=False))
    print(f"xong v{ver}: {total:.1f}s → {out}")

if __name__ == "__main__":
    main()
