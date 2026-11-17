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
    else: raise SystemExit("sfx lạ: " + name)
    y = (y / (np.abs(y).max() + 1e-9) * 0.7 * 32767).astype(np.int16)
    import wave
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y.tobytes())
    return p

# ---------- chữ trên hình ----------
def wrap(draw, text, font, maxw):
    words = text.split(); lines = []; cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def card(text, style, W, H, fx):
    """Trả về ảnh RGBA cỡ W×H có đúng một mảng chữ theo kiểu thương hiệu."""
    S = W / 1920
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
    if st == "tape":
        f = F(fx["inter"], int(66 * S)); lines = wrap(d0, text, f, W * 0.62)
        b = block(lines, f, (int(34 * S), int(16 * S)), COL["tape"], COL["cocoa"], int(6 * S), 2)
        pos = (int(W * 0.06), int(H * 0.10))
    elif st == "postcard":
        f = F(fx["play"], int(54 * S), 700); lines = wrap(d0, text, f, W * 0.5)
        b = block(lines, f, (int(36 * S), int(22 * S)), COL["paper"], COL["cocoa"], int(10 * S), -3)
        pos = (int(W * 0.06), int(H * 0.70) - (len(lines) - 1) * int(60 * S))
    elif st == "label":
        f = F(fx["nunito"], int(40 * S), 900); lines = [text.upper()]
        b = block(lines, f, (int(28 * S), int(10 * S)), COL["tape"], COL["cocoa"], int(40 * S), 0)
        pos = (int(W * 0.06), int(H * 0.08))
    elif st == "price":
        f = F(fx["nunito"], int(46 * S), 900); lines = [text]
        b = block(lines, f, (int(30 * S), int(12 * S)), COL["white"], COL["berry"], int(40 * S), -2)
        pos = (int(W * 0.70), int(H * 0.12))
    elif st == "big":
        f = F(fx["inter"], int(120 * S)); lines = wrap(d0, text, f, W * 0.8)
        b = block(lines, f, (0, 0), None, COL["white"], 0, 0, stroke=int(8 * S), sc=COL["cocoa"], lh=1.05)
        pos = ((W - b.width) // 2, (H - b.height) // 2)
    elif st == "question":
        f = F(fx["nunito"], int(52 * S), 900); lines = wrap(d0, text, f, W * 0.55)
        b = block(lines, f, (int(44 * S), int(30 * S)), COL["white"], COL["berry"], int(28 * S), 0)
        pos = ((W - b.width) // 2 - int(90 * S), int(H * 0.62) - b.height // 2)
        mini = REPO / "brand" / "hello.png"
        if mini.exists():
            m = Image.open(mini).convert("RGBA"); mh = int(330 * S); m = m.resize((int(m.width * mh / m.height), mh))
            im.alpha_composite(m, (min(W - m.width - int(40 * S), pos[0] + b.width - int(30 * S)), int(H * 0.62) - mh // 2))
    else: raise SystemExit("kiểu chữ lạ: " + st)
    im.alpha_composite(b, (max(0, pos[0] - 20), max(0, pos[1] - 20)))
    return im

# ---------- phụ đề (ASS) ----------
def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"
def build_ass(subs, W, H, path):
    S = H / 1080
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pum,Be Vietnam Pro ExtraBold,{int(54*S)},&H00FFFFFF,&H00FFFFFF,&H00302639,&H64302639,0,0,0,0,100,100,0,0,1,{4.5*S:.1f},{1.5*S:.1f},2,{int(160*S)},{int(160*S)},{int(64*S)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Pum,,0,0,0,,{t.replace(chr(10), chr(92)+'N')}" for a, b, t in subs if b - a > 0.15 and t.strip()]
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
def seg_render(i, sg, clips, W, H, fx, tmp):
    src = sg.get("path") or clips[sg["clip"]]["path"]; info = clips.get(sg.get("clip"), {})
    a, b = float(sg["in"]), float(sg["out"]); sp = float(sg.get("speed", 1)); dur = (b - a) / sp
    vw, vh = info.get("w") or 1920, info.get("h") or 1080
    fit = sg.get("fit") or ("blur" if vh > vw else "fill")
    z = sg.get("zoom")
    vf = []
    if fit == "blur":
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
    fc = [f"[0:v]{','.join(vf)}[v0]"]; last = "v0"; k = 1
    for j, t in enumerate(sg.get("text", [])):
        png = tmp / f"t{i}_{j}.png"; card(t["text"], t.get("style", "tape"), W, H, fx).save(png)
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(png)]
        s0, s1 = float(t.get("start", 0)), float(t.get("end", dur))
        fade = f"fade=t=in:st={s0:.2f}:d=0.18:alpha=1,fade=t=out:st={max(s0,s1-0.18):.2f}:d=0.18:alpha=1"
        fc.append(f"[{k}:v]format=rgba,{fade}[o{k}]"); fc.append(f"[{last}][o{k}]overlay=0:0:enable='between(t,{s0:.2f},{s1:.2f})'[v{k}]"); last = f"v{k}"; k += 1
    # âm thanh
    mode = sg.get("audio", "src"); vol = float(sg.get("vol", 1.0))
    has_a = info.get("audio", True)
    if mode == "mute" or not has_a:
        inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]; fc.append(f"[{k}:a]anull[a0]"); k += 1
    else:
        g = {"src": 1.0, "low": 0.28, "amb": 0.45}.get(mode, 1.0) * vol
        at = f",atempo={sp}" if sp != 1 and 0.5 <= sp <= 2 else ""
        fc.append(f"[0:a]aresample={SR},aformat=channel_layouts=stereo{at},volume={g:.3f},afade=t=in:d=0.06,afade=t=out:st={max(0,dur-0.08):.3f}:d=0.08[a0]")
    alast = "a0"
    vo = sg.get("vo")
    if vo:
        vsrc = vo.get("path") or clips[vo["clip"]]["path"]
        inputs += ["-ss", f"{float(vo['in']):.3f}", "-to", f"{float(vo['out']):.3f}", "-i", vsrc]
        ms = int(float(vo.get("at", 0.2)) * 1000)
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=stereo,highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,volume={float(vo.get('vol',1.15)):.2f},adelay={ms}|{ms}[vo]")
        fc.append(f"[{alast}][vo]amix=inputs=2:normalize=0:duration=first[am]"); alast = "am"; k += 1
    fc.append(f"[{alast}]apad,atrim=0:{dur:.3f}[aout]")
    out = tmp / f"seg{i:03d}.mp4"
    sh(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{last}]", "-map", "[aout]",
        "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2", str(out)])
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

def main():
    ep, edl_p = sys.argv[1], Path(sys.argv[2]); proxy_only = "--proxy-only" in sys.argv
    E = json.loads(edl_p.read_text()); d = WORK / str(ep); ver = E.get("ver", 1)
    out = d / f"v{ver}"; tmp = out / "tmp"; tmp.mkdir(parents=True, exist_ok=True)
    W, H = E.get("size", [1920, 1080]); fx = fonts()
    m = json.loads((d / "match.json").read_text()); clips = dict(m["clips"])
    for p, i in m.get("unassigned", {}).items(): clips["u:" + hashlib.sha1(p.encode()).hexdigest()[:8]] = {"path": p, **i}
    scan = json.loads((d / "scan.json").read_text()) if (d / "scan.json").exists() else {}
    segs = E["segments"]; files = []; tl = []; subs = []; t = 0.0
    for i, sg in enumerate(segs):
        f, dur = seg_render(i, sg, clips, W, H, fx, tmp); files.append(f)
        tl.append({"id": sg.get("id", f"s{i+1}"), "label": sg.get("label", ""), "chapter": sg.get("chapter", ""), "start": round(t, 2), "end": round(t + dur, 2),
                   "clip": sg.get("clip"), "in": sg["in"], "out": sg["out"], "kind": sg.get("kind", ""), "text": [x["text"] for x in sg.get("text", [])], "vo": bool(sg.get("vo"))})
        subs += seg_subs(sg, scan, t); t += dur
        print(f"  đoạn {i+1}/{len(segs)} {sg.get('label','')[:40]} {dur:.1f}s")
    total = t
    (tmp / "list.txt").write_text("".join(f"file '{f}'\n" for f in files))
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(tmp / "base.mp4")])
    build_ass(subs, W, H, tmp / "subs.ass")
    # chuyển cảnh thương hiệu (webm nền trong) đặt tại điểm nối
    vin = ["-i", str(tmp / "base.mp4")]; fc = []; last = "0:v"; k = 1
    for i, sg in enumerate(segs):
        tr = sg.get("trans")
        if not tr or i == 0: continue
        wf = REPO / "fx" / ("youtube" if W > H else "tiktok") / f"chuyen_canh_{tr}.webm"
        if not wf.exists(): continue
        at = max(0, tl[i]["start"] - 0.35)
        vin += ["-itsoffset", f"{at:.3f}", "-c:v", "libvpx-vp9", "-i", str(wf)]
        fc.append(f"[{k}:v]scale={W}:{H},format=rgba,setpts=PTS-STARTPTS+{at:.3f}/TB[tr{k}]"); fc.append(f"[{last}][tr{k}]overlay=0:0:eof_action=pass[x{k}]"); last = f"x{k}"; k += 1
    assp = str(tmp / "subs.ass").replace(":", "\\:")
    fc.append(f"[{last}]ass='{assp}'[vout]")
    # âm: tiếng gốc + nhạc (tự hạ khi có lời) + hiệu ứng
    ain = []; a_fc = []; ai = k
    mus = []; credits = []
    for c in E.get("music", []):
        p, info = music_file(c["track"]); credits.append(info["title"])
        st, en = float(c["start"]), float(c["end"]); fr = float(c.get("from", 0)); dur = en - st
        ain += ["-i", str(p)]
        fi, fo = float(c.get("fadein", 1.2)), float(c.get("fadeout", 2.0))
        a_fc.append(f"[{ai}:a]atrim={fr:.2f}:{fr+dur:.2f},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=stereo,volume={float(c.get('vol',0.16)):.3f},afade=t=in:d={fi},afade=t=out:st={max(0,dur-fo):.2f}:d={fo},adelay={int(st*1000)}|{int(st*1000)}[m{ai}]")
        mus.append(f"[m{ai}]"); ai += 1
    sfx = []
    for s in E.get("sfx", []):
        p = sfx_file(s["name"]); ain += ["-i", str(p)]
        ms = int(float(s["at"]) * 1000)
        a_fc.append(f"[{ai}:a]aresample={SR},aformat=channel_layouts=stereo,volume={float(s.get('vol',0.5)):.2f},adelay={ms}|{ms}[f{ai}]"); sfx.append(f"[f{ai}]"); ai += 1
    a_fc.append("[0:a]asplit=2[dia][key]")
    mix = ["[dia]"]
    if mus:
        a_fc.append(f"{''.join(mus)}amix=inputs={len(mus)}:normalize=0:duration=longest,apad,atrim=0:{total:.2f}[mus]")
        a_fc.append("[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=25:release=450:makeup=1[duck]"); mix.append("[duck]")
    else: a_fc.append("[key]anullsink")
    mix += sfx
    a_fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample={SR}[aout]")
    full = fc + a_fc
    final = out / "final.mp4"; proxy = out / "proxy.mp4"
    if not proxy_only:
        sh(["ffmpeg", "-y", "-v", "error", *vin, *ain, "-filter_complex", ";".join(full), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", str(final)])
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-vf", "scale=854:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
            "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(proxy)])
    else:
        sh(["ffmpeg", "-y", "-v", "error", *vin, *ain, "-filter_complex", ";".join(full).replace("[vout]", "[vbig]") + ";[vbig]scale=854:-2[vout]", "-map", "[vout]", "-map", "[aout]",
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
