#!/usr/bin/env python3
"""Bộ công cụ dựng vlog của Pum Studio.

Chạy:  PUM_PASS=... python3 -I pumdung.py <lệnh> [tham số]
  fetch  <ep>                 lấy kịch bản + danh sách clip Pum gắn trong app  -> work/<ep>/manifest.json
  match  <ep> <thư_mục>       khớp file Pum gửi trong chat với clip đã gắn     -> work/<ep>/match.json
  scan   <ep>                 quét từng clip: lời nói, độ nét, độ sáng, âm      -> work/<ep>/scan.json
  sheet  <ep>                 ảnh xem nhanh mỗi clip để AI tự nhìn              -> work/<ep>/sheets/*.jpg
  push   <ep> <file.json> <key>   ghi một phần (board/draft/final) vào app
  status <ep> <trạng_thái> [lời nhắn]
  board  <ep> <board.json> [lời nhắn]     đưa hướng dựng lên app (bước 3)
  draft  <ep> <ver> [lời nhắn]            đưa bản nháp nhẹ + dòng thời gian lên app (bước 4)
  final  <ep> <ver> [lời nhắn]            báo đã có bản cuối (gửi file 1080p trong chat)
Không có mật khẩu trong file này: đặt biến môi trường PUM_PASS.
"""
import json, os, re, subprocess, sys, hashlib, base64, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WORK = Path(os.environ.get("PUM_WORK", "/home/claude/pumdung"))
SB = "https://lpiwmdomdzebzhmxzesn.supabase.co"
ANON = "sb_publishable_6H1om-emHz6RrLBy1guQfg_PfGyseKE"
SALT = bytes.fromhex("60370fbbacf66f1f564f02b04b4a86ad"); ITER = 310000

def die(m): print("LỖI:", m, file=sys.stderr); sys.exit(1)
def pw():
    p = os.environ.get("PUM_PASS")
    if not p: die("thiếu PUM_PASS (mật khẩu app)")
    return p

# ---------- mã hoá giống gate.js ----------
_KEY = None
def key():
    global _KEY
    if _KEY is None:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
        _KEY = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=SALT, iterations=ITER).derive(pw().encode())
    return _KEY
def dec(b):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key()).decrypt(b[:12], b[12:], None)
def enc(b):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(12); return iv + AESGCM(key()).encrypt(iv, b, None)

# ---------- Supabase (cùng RPC với app) ----------
def rpc(fn, args):
    req = urllib.request.Request(f"{SB}/rest/v1/rpc/{fn}", data=json.dumps(args).encode(),
        headers={"apikey": ANON, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode() or "null"
    return json.loads(t)
def rows():
    return [r for r in (rpc("pum_list", {"p": pw()}) or []) if not r.get("deleted")]
def put(col, id_, data):
    rpc("pum_put", {"p": pw(), "c": col, "i": id_, "d": data})
def get(col, id_):
    for r in rows():
        if r["col"] == col and r["id"] == id_: return r["data"]
    return None
def merge(col, id_, patch):
    cur = get(col, id_) or {}
    cur.update(patch); put(col, id_, cur); return cur

# ---------- kịch bản (cùng cách đọc với app.js) ----------
def parse_script(md, n):
    out = {"n": n, "title": "", "meta": {}, "sections": []}; sec = beat = None
    for raw in md.split("\n"):
        l = raw.strip()
        if not l: continue
        if l.startswith("# "): out["title"] = l[2:]; continue
        if l.startswith("## "):
            t = l[3:]; sid = f"t{n}s{len(out['sections'])}"
            dm = re.match(r"^Ngày (\d+) · (.+?)\s+—\s+(.+)$", t)
            if dm: sec = {"kind": "day", "id": sid, "title": f"Ngày {dm[1]} · {dm[3]}", "beats": []}
            elif re.match(r"^(Mở tập|Cuối tập)", t) or re.match(r"^Chương \d+", t): sec = {"kind": "part", "id": sid, "title": re.sub(r"\s*\([^)]*\)\s*$", "", t), "beats": []}
            else: sec = {"kind": "list", "id": sid, "title": t, "list": []}
            out["sections"].append(sec); beat = None; continue
        if not sec:
            m = re.match(r"^\*\*(.+?):\*\*\s*(.*)$", l)
            if m: out["meta"][m[1]] = m[2]
            continue
        if sec["kind"] == "list": sec["list"].append(re.sub(r"^- ", "", l)); continue
        bm = re.match(r"^\*\*([^*]+)\*\*$", l)
        if bm: beat = {"title": bm[1], "items": [], "key": f"{sec['id']}b{len(sec['beats'])}"}; sec["beats"].append(beat); continue
        if l.startswith("- ") and beat:
            im = re.match(r"^\*\*(.+?):\*\*\s*(.*)$", l[2:])
            beat["items"].append({"k": im[1], "v": im[2]} if im else {"k": "", "v": l[2:]})
    return out

def load_script(ep):
    return parse_script(dec((REPO / f"scripts/tap{ep}.enc").read_bytes()).decode(), ep)

# ---------- ffprobe ----------
def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height,r_frame_rate:stream_tags=rotate:stream_side_data=rotation",
                        "-of", "json", str(p)], capture_output=True, text=True)
    if r.returncode: return None
    j = json.loads(r.stdout); f = j.get("format", {}); v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = any(s.get("codec_type") == "audio" for s in j.get("streams", []))
    w = h = 0; rot = 0
    if v:
        w, h = v.get("width", 0), v.get("height", 0)
        rot = int((v.get("tags") or {}).get("rotate", 0) or 0)
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd: rot = int(sd["rotation"])
        if abs(rot) in (90, 270): w, h = h, w
    return {"dur": float(f.get("duration", 0) or 0), "size": int(f.get("size", 0) or 0), "w": w, "h": h, "video": bool(v), "audio": a}

# ---------- lệnh ----------
def wdir(ep):
    d = WORK / str(ep); d.mkdir(parents=True, exist_ok=True); return d

def cmd_fetch(ep):
    sc = load_script(ep); R = rows()
    # app lưu clip ở kho "vids" với id c_<mã cảnh>, trạng thái dựng ở e_<tập>
    clips = {r["id"][2:]: r["data"] for r in R if r["col"] == "vids" and r["id"].startswith("c_")}
    edits = next((r["data"] for r in R if r["col"] == "vids" and r["id"] == f"e_{ep}"), {})
    beatsrow = {r["id"]: r["data"] for r in R if r["col"] == "beats"}
    out = {"ep": ep, "title": sc["title"], "meta": sc["meta"], "chapters": [], "edits": edits}
    for sec in sc["sections"]:
        if sec["kind"] == "list":
            out.setdefault("lists", {})[sec["title"]] = sec["list"]; continue
        ch = {"id": sec["id"], "title": sec["title"], "beats": [], "extra": clips.get(sec["id"] + "x", {})}
        for b in sec["beats"]:
            ch["beats"].append({"key": b["key"], "title": b["title"], "items": b["items"],
                                "clips": (clips.get(b["key"]) or {}).get("clips", []),
                                "shot": bool((beatsrow.get(b["key"]) or {}).get("shot")),
                                "note": (beatsrow.get(b["key"]) or {}).get("note", "")})
        out["chapters"].append(ch)
    n = sum(len(b["clips"]) for c in out["chapters"] for b in c["beats"]) + sum(len(c["extra"].get("clips", [])) for c in out["chapters"])
    (wdir(ep) / "manifest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"kịch bản: {sc['title']}\nclip đã gắn trong app: {n}\ntrạng thái: {edits.get('status','(chưa gửi)')}")
    if edits.get("feedback"): print("góp ý của Pum:", json.dumps(edits["feedback"], ensure_ascii=False)[:800])
    if edits.get("notes"): print("ghi chú trên bản nháp:", json.dumps(edits["notes"], ensure_ascii=False)[:1500])

MEDIA = re.compile(r"\.(mp4|mov|m4v|3gp|mkv|webm|m4a|mp3|wav|aac|ogg|opus|amr)$", re.I)
def all_clips(man):
    for c in man["chapters"]:
        for b in c["beats"]:
            for x in b["clips"]: yield c, b, x
        for x in c["extra"].get("clips", []): yield c, None, x

def cmd_match(ep, folder):
    man = json.loads((wdir(ep) / "manifest.json").read_text())
    files = [p for p in Path(folder).rglob("*") if p.is_file() and MEDIA.search(p.name)]
    info = {}
    for p in files:
        pr = probe(p)
        if pr: info[str(p)] = pr
    used = set(); res = {}; miss = []
    for c, b, x in all_clips(man):
        best = None
        for p, pr in info.items():
            if p in used: continue
            score = 0
            if x.get("size") and pr["size"] == x["size"]: score += 10
            if x.get("dur") and abs(pr["dur"] - x["dur"]) < 0.35: score += 4
            if x.get("name") and Path(p).name.lower() == x["name"].lower(): score += 5
            elif x.get("name") and Path(p).stem.lower() in x["name"].lower(): score += 2
            if score >= 5 and (not best or score > best[0]): best = (score, p)
        if best: used.add(best[1]); res[x["id"]] = {"path": best[1], **info[best[1]]}
        else: miss.append({"chuong": c["title"], "canh": b["title"] if b else "ngoài kịch bản", "file": x.get("name")})
    extra = [p for p in info if p not in used]
    (wdir(ep) / "match.json").write_text(json.dumps({"clips": res, "missing": miss, "unassigned": {p: info[p] for p in extra}}, ensure_ascii=False, indent=1))
    print(f"khớp {len(res)} clip, thiếu {len(miss)}, file chưa gắn cảnh {len(extra)}")
    for m in miss: print("  thiếu:", m)
    for p in extra: print("  chưa gắn:", Path(p).name)

def cmd_drive(ep):
    """Danh sách video Pum đã tải lên Google Drive mà máy này chưa có: tải từng file bằng
    công cụ Google Drive (download_file_content, mã file ở cột drive) rồi `place` vào đúng chỗ."""
    man = json.loads((wdir(ep) / "manifest.json").read_text()); src = wdir(ep) / "src"; src.mkdir(exist_ok=True)
    todo, have, nod = [], 0, []
    for c, b, x in all_clips(man):
        if not x.get("drive"): nod.append(f'{c["title"]} · {b["title"] if b else "ngoài kịch bản"} · {x.get("name")}'); continue
        dst = src / f'{x["id"]}_{x["name"]}'
        if dst.exists() and (not x.get("size") or dst.stat().st_size == x["size"]): have += 1; continue
        todo.append({"drive": x["drive"], "dest": str(dst), "size": x.get("size"), "canh": b["title"] if b else "ngoài kịch bản"})
    (wdir(ep) / "drive_todo.json").write_text(json.dumps(todo, ensure_ascii=False, indent=1))
    print(f"đã có {have}, cần tải {len(todo)}, chưa lên Drive {len(nod)}")
    for t in todo: print(f'  tải: {t["drive"]} -> {t["dest"]} ({(t["size"] or 0)/1e6:.0f} MB)')
    for m in nod: print("  chưa lên Drive (nhờ Pum tải tiếp ở bước 1 hoặc đính kèm):", m)

def cmd_place(ep, got, drive_id):
    todo = json.loads((wdir(ep) / "drive_todo.json").read_text())
    t = next((t for t in todo if t["drive"] == drive_id), None)
    if not t: die("mã Drive không có trong drive_todo.json")
    import shutil; shutil.copyfile(got, t["dest"])
    sz = Path(t["dest"]).stat().st_size
    print("đã đặt", Path(t["dest"]).name, f"{sz/1e6:.1f} MB", "" if not t["size"] or sz == t["size"] else f"(KHÁC dung lượng gốc {t['size']})")

def cmd_vo(ep):
    """Lấy các đoạn Pum đã tự ghi âm lồng tiếng trong app (kho vids, mã v_<ep>_<đoạn>) về WORK/<ep>/vo/"""
    import base64
    d = wdir(ep) / "vo"; d.mkdir(parents=True, exist_ok=True); n = 0
    for r in rows():
        if r["col"] != "vids" or not r["id"].startswith(f"v_{ep}_"): continue
        x = r["data"] or {}; sid = r["id"][len(f"v_{ep}_"):]
        ext = "m4a" if "mp4" in (x.get("mime") or "") else "webm"
        raw = d / f"{sid}.{ext}"; raw.write_bytes(base64.b64decode(x["data"]))
        wav = d / f"{sid}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ac", "1", "-ar", "48000", str(wav)], check=True)
        n += 1; print(f"  {sid}: {x.get('dur', 0):.1f}s, bản v{x.get('v')}, {time.strftime('%d/%m %H:%M', time.localtime(x.get('at', 0)/1000))} -> {wav}")
    print(f"{n} đoạn lồng tiếng của Pum")

def _audio_stats(path, dur):
    """độ lớn âm thanh mỗi 0,5 giây (dBFS)"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True)
    import numpy as np
    a = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768
    if not len(a): return []
    n = 4000; k = len(a) // n
    if not k: return []
    rms = np.sqrt((a[:k * n].reshape(k, n) ** 2).mean(1) + 1e-12)
    return [round(float(20 * np.log10(x)), 1) for x in rms]

def _frames(path, dur, n=6, w=320):
    import numpy as np
    from PIL import Image, ImageFilter
    out = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        if not r.stdout: continue
        import io
        im = Image.open(io.BytesIO(r.stdout)).convert("L")
        a = np.asarray(im, dtype=np.float32)
        lap = np.asarray(im.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        out.append({"t": round(t, 2), "sharp": round(float(lap.var()), 1), "bright": round(float(a.mean()), 1)})
    return out

def cmd_scan(ep, model="small"):
    d = wdir(ep); m = json.loads((d / "match.json").read_text())
    scan_p = d / "scan.json"; scan = json.loads(scan_p.read_text()) if scan_p.exists() else {}
    from faster_whisper import WhisperModel
    wm = None
    items = list(m["clips"].items()) + [("u:" + hashlib.sha1(p.encode()).hexdigest()[:8], {"path": p, **i}) for p, i in m.get("unassigned", {}).items()]
    for cid, x in items:
        if cid in scan and scan[cid].get("path") == x["path"]: continue
        t0 = time.time(); s = {"path": x["path"], "dur": x["dur"], "w": x["w"], "h": x["h"], "video": x["video"]}
        if x["video"]: s["frames"] = _frames(x["path"], x["dur"])
        s["loud"] = _audio_stats(x["path"], x["dur"])
        if x.get("audio", True):
            if wm is None: wm = WhisperModel(model, device="cpu", compute_type="int8")
            import numpy as np
            r = subprocess.run(["ffmpeg", "-v", "error", "-i", x["path"], "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
            a = np.frombuffer(r.stdout, dtype=np.float32)
            segs, _ = wm.transcribe(a, language="vi", vad_filter=True, word_timestamps=True, beam_size=3)
            s["speech"] = [{"s": round(g.start, 2), "e": round(g.end, 2), "text": g.text.strip(),
                            "words": [[round(w.start, 2), round(w.end, 2), w.word] for w in (g.words or [])]} for g in segs]
        s["speech_sec"] = round(sum(g["e"] - g["s"] for g in s.get("speech", [])), 1)
        scan[cid] = s; scan_p.write_text(json.dumps(scan, ensure_ascii=False))
        print(f"{Path(x['path']).name}: {x['dur']:.1f}s, lời {s['speech_sec']}s, {time.time()-t0:.0f}s quét")
    print("xong", len(scan), "clip")

def cmd_sheet(ep):
    d = wdir(ep); scan = json.loads((d / "scan.json").read_text()); (d / "sheets").mkdir(exist_ok=True)
    for cid, s in scan.items():
        if not s.get("video"): continue
        n = 8; out = d / "sheets" / f"{cid}.jpg"
        if out.exists(): continue
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", s["path"], "-vf", f"fps={n}/{max(s['dur'],1):.2f},scale=320:-2,tile={n}x1", "-frames:v", "1", str(out)])
    print("ảnh xem nhanh ở", d / "sheets")

def cmd_push(ep, f, k):
    data = json.loads(Path(f).read_text()); merge("vids", f"e_{ep}", {k: data, k + "At": int(time.time() * 1000)}); print("đã ghi", k)

def cmd_status(ep, st, msg=""):
    merge("vids", f"e_{ep}", {"status": st, "agentMsg": msg, "agentAt": int(time.time() * 1000)}); print("trạng thái:", st)


def _git(*a): return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)
def _publish(paths, msg):
    _git("pull", "-q", "--rebase")
    _git("add", *[str(x) for x in paths])
    r = _git("commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
    p = _git("push", "-q", "origin", "main")
    if p.returncode: die("chưa đẩy lên được web: " + p.stderr[-400:])
    print("đã đẩy lên web (GitHub Pages cập nhật sau khoảng 1 phút)")

def cmd_board(ep, f, msg=""):
    bd = json.loads(Path(f).read_text()); e = get("vids", f"e_{ep}") or {}
    v = int(e.get("boardV", 0)) + 1; bd["v"] = v
    d = REPO / "drafts" / str(ep); d.mkdir(parents=True, exist_ok=True)
    (d / "board.enc").write_bytes(enc(json.dumps(bd, ensure_ascii=False).encode()))
    _publish([d / "board.enc"], f"Hướng dựng tập {ep} bản {v}")
    merge("vids", f"e_{ep}", {"boardV": v, "boardAt": int(time.time()*1000), "status": "de_xuat", "agentMsg": msg or "Xem hướng dựng ở bước 3 rồi góp ý.",
                             "feedback": {**(e.get("feedback") or {}), "approved": False}})
    print("hướng dựng bản", v)

def cmd_draft(ep, ver, msg=""):
    src = WORK / str(ep) / f"v{ver}"; d = REPO / "drafts" / str(ep); d.mkdir(parents=True, exist_ok=True)
    pv = (src / "proxy.mp4").read_bytes(); tl = json.loads((src / "timeline.json").read_text())
    if len(pv) > 95_000_000: die("bản nhẹ quá 95 MB, giảm chất lượng proxy trước")
    for old in d.glob("v*.enc"):
        m = re.match(r"v(\d+)\.", old.name)
        if m and int(m[1]) < int(ver) - 1: _git("rm", "-q", "--cached", str(old)); old.unlink()
    (d / f"v{ver}.mp4.enc").write_bytes(enc(pv)); (d / f"v{ver}.json.enc").write_bytes(enc(json.dumps(tl, ensure_ascii=False).encode()))
    _publish([d], f"Bản nháp tập {ep} v{ver}")
    merge("vids", f"e_{ep}", {"draftV": int(ver), "draftDur": tl["dur"], "draftSize": len(pv), "draftAt": int(time.time()*1000),
                             "status": "nhap", "credits": tl.get("credits", ""), "agentMsg": msg or "Có bản nháp mới ở bước 4."})
    print("bản nháp v%s: %.0fs, %.1f MB" % (ver, tl["dur"], len(pv) / 1e6))

def cmd_final(ep, ver, msg=""):
    tl = json.loads((WORK / str(ep) / f"v{ver}" / "timeline.json").read_text())
    merge("vids", f"e_{ep}", {"finalV": int(ver), "status": "xong", "credits": tl.get("credits", ""), "agentMsg": msg or "Bản cuối đã gửi trong chat Claude."}); print("đã báo bản cuối")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: print(__doc__); sys.exit()
    {"fetch": lambda: cmd_fetch(a[1]), "drive": lambda: cmd_drive(a[1]), "vo": lambda: cmd_vo(a[1]), "place": lambda: cmd_place(a[1], a[2], a[3]), "match": lambda: cmd_match(a[1], a[2]), "scan": lambda: cmd_scan(a[1], *(a[2:3])),
     "sheet": lambda: cmd_sheet(a[1]), "push": lambda: cmd_push(a[1], a[2], a[3]), "status": lambda: cmd_status(a[1], a[2], " ".join(a[3:])),
     "board": lambda: cmd_board(a[1], a[2], " ".join(a[3:])), "draft": lambda: cmd_draft(a[1], a[2], " ".join(a[3:])), "final": lambda: cmd_final(a[1], a[2], " ".join(a[3:]))}[a[0]]()
