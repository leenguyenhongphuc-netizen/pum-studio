#!/usr/bin/env python3
"""Dựng bằng Concat từ cùng bản dựng edl.json mà render.py dùng.

  python3 -I concat_build.py <ep> <edl.json> [--no-export]
Ra: work/<ep>/v<ver>/concat/<tên dự án>/  (dự án Concat mở được bằng app Concat trên máy tính hoặc Android)
    work/<ep>/v<ver>/concat_final.mp4    (bản xuất 1080p của Concat)
    work/<ep>/v<ver>/concat_project.zip  (gói dự án gửi cho Pum để tự chỉnh tay trong Concat)
Khác render.py: lời nói được lọc ồn và làm rõ giọng (concat.denoise, concat.enhance-voice), chuyển cảnh lấy từ thư viện
Concat khi không có hiệu ứng thương hiệu, cả tập là một dự án chỉnh tay được. Nhạc tự hạ khi có lời bằng cách hạ
âm lượng từng đoạn nhạc nằm dưới đoạn có lời (Concat chưa có nén theo lời).
"""
import json, os, sys, shutil, hashlib, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
from concat_mcp import Concat
import render as R
from pumdung import probe
P_probe = lambda f: (probe(f) or {}).get("dur", 0)

WORK = Path(os.environ.get("PUM_WORK", "/home/claude/pumdung"))
# Concat làm mất dấu chồng (Ủ, Ẩ…) khi để nghiêng, nên chữ trong dự án Concat để đứng
BRAND = {"tape": dict(fontFamily="Be Vietnam Pro", fontWeight=900, italic=False, color="#392630", background="#FFD0E3", fontSize=0.06, shadow=False),
         "postcard": dict(fontFamily="Playfair Display", fontWeight=700, italic=False, color="#392630", background="#FFFDFC", fontSize=0.05, shadow=True),
         "label": dict(fontFamily="Nunito", fontWeight=900, color="#392630", background="#FFD0E3", fontSize=0.036, textCase="upper", backgroundRadius=0.03, shadow=False),
         "price": dict(fontFamily="Nunito", fontWeight=900, color="#B83268", background="#FFFFFF", fontSize=0.042, backgroundRadius=0.03, shadow=True),
         "big": dict(fontFamily="Be Vietnam Pro", fontWeight=900, italic=False, color="#FFFFFF", strokeColor="#392630", strokeWidth=0.007, fontSize=0.11, shadow=False),
         "question": dict(fontFamily="Nunito", fontWeight=900, color="#B83268", background="#FFFFFF", fontSize=0.048, backgroundRadius=0.026, shadow=True)}
PLACE = {"tape": (-0.22, -0.30, -2), "postcard": (-0.24, 0.24, 3), "label": (-0.33, -0.43, 0), "price": (0.28, -0.36, -2), "big": (0, 0, 0), "question": (-0.08, 0.12, 0)}
SUB = dict(fontFamily="Be Vietnam Pro", fontWeight=800, color="#FFFFFF", strokeColor="#392630", strokeWidth=0.004, fontSize=0.05, shadow=True, background="")
TRANS = {"chop_kem": "concat.fade-white", "bang_hong": "concat.slide", "trang_giay": "concat.dissolve", "tim": "concat.iris"}

def main():
    ep, edl_p = sys.argv[1], Path(sys.argv[2]); export = "--no-export" not in sys.argv
    E = json.loads(edl_p.read_text()); d = WORK / str(ep); ver = E.get("ver", 1); out = d / f"v{ver}"
    m = json.loads((d / "match.json").read_text()); clips = dict(m["clips"])
    for p, i in m.get("unassigned", {}).items(): clips["u:" + hashlib.sha1(p.encode()).hexdigest()[:8]] = {"path": p, **i}
    scan = json.loads((d / "scan.json").read_text()) if (d / "scan.json").exists() else {}
    loc = out / "concat"; name = f"Pum_{ep}_v{ver}"
    if (loc / name).exists(): shutil.rmtree(loc / name)
    loc.mkdir(parents=True, exist_ok=True); P = str(loc / name)
    with Concat() as c:
        c.call("project_create", {"location": str(loc), "name": name})
        media = {}
        def mid(path):
            if path not in media: media[path] = c.call("media_import", {"path": P, "file": str(path)})["createdId"]
            return media[path]
        tracks = [x["id"] for x in c.call("timeline_read", {"path": P})["timeline"]["tracks"]]
        while len(tracks) < 6: tracks.append(c.call("track_add", {"path": P})["createdId"])
        V, VO, MUS, SFX, OVL = tracks[0], tracks[1], tracks[2], tracks[3], tracks[4]
        def place(path, track, at, a, b, dur):
            """đặt đoạn [a,b] của file lên lane tại giây at"""
            cid = c.call("clip_add", {"path": P, "mediaId": mid(path), "trackId": track, "start": at})["createdId"]
            if a > 0.001: c.call("clip_trim", {"path": P, "clipId": cid, "edge": "start", "delta": a})
            if b < dur - 0.001: c.call("clip_trim", {"path": P, "clipId": cid, "edge": "end", "delta": b - dur})
            if a > 0.001: c.call("clips_move", {"path": P, "moves": [{"clipId": cid, "start": at, "trackId": track}]})
            return cid
        t = 0.0; talk = []; subs = []
        for i, sg in enumerate(E["segments"]):
            src = sg.get("path") or clips[sg["clip"]]["path"]; info = clips.get(sg.get("clip"), {})
            a, b, sp = float(sg["in"]), float(sg["out"]), float(sg.get("speed", 1))
            cid = place(src, V, t, a, b, info.get("dur") or P_probe(src))
            patch = {}
            mode = sg.get("audio", "src")
            if mode == "mute": patch["muted"] = True
            else: patch["volume"] = {"src": 1.0, "low": 0.28, "amb": 0.45}.get(mode, 1.0) * float(sg.get("vol", 1))
            if mode == "src" and sg.get("sub"): patch["filters"] = [{"id": "concat.denoise", "params": {}}, {"id": "concat.enhance-voice", "params": {}}]
            vw, vh = info.get("w") or 1920, info.get("h") or 1080
            if sg.get("fit") == "blur" or (not sg.get("fit") and vh > vw): patch["background"] = {"kind": "blur", "amount": 0.6}
            tr = sg.get("trans")
            if tr and i: patch["transitionIn"] = {"id": TRANS.get(tr, "concat.dissolve"), "duration": 0.5}
            c.call("clip_update", {"path": P, "clipId": cid, "patch": patch})
            if sp != 1: c.call("clip_speed", {"path": P, "clipId": cid, "speed": sp})
            dur = (b - a) / sp
            if sg.get("vo"):
                vo = sg["vo"]; vp = vo.get("path") or clips[vo["clip"]]["path"]
                vid = place(vp, VO, t + float(vo.get("at", 0.2)), float(vo["in"]), float(vo["out"]), clips.get(vo.get("clip"), {}).get("dur", float(vo["out"])))
                c.call("clip_update", {"path": P, "clipId": vid, "patch": {"volume": float(vo.get("vol", 1.15)), "filters": [{"id": "concat.denoise", "params": {}}, {"id": "concat.enhance-voice", "params": {}}]}})
            if mode == "src" or sg.get("vo"): talk.append((t, t + dur))
            for x in sg.get("text", []):
                st = dict(BRAND[x.get("style", "tape")], content=x["text"])
                ox, oy, rot = PLACE[x.get("style", "tape")]
                tid = c.call("title_add", {"path": P, "start": t + float(x.get("start", 0)), "duration": float(x.get("end", dur)) - float(x.get("start", 0)), "style": st, "offsetY": oy, "above": True})["createdId"]
                c.call("clip_transform", {"path": P, "clipId": tid, "offsetX": ox, "rotation": rot})
                c.call("clip_update", {"path": P, "clipId": tid, "patch": {"fadeIn": 0.15, "fadeOut": 0.15}})
                if x.get("style") == "question" and (REPO / "brand/hello.png").exists():
                    mp = place(REPO / "brand/hello.png", OVL, t + float(x.get("start", 0)), 0, float(x.get("end", dur)) - float(x.get("start", 0)), 5)
                    c.call("clip_transform", {"path": P, "clipId": mp, "scale": 0.32, "offsetX": 0.3, "offsetY": 0.1})
            subs += R.seg_subs(sg, scan, t); t += dur
        total = t
        if subs:
            c.call("captions_add", {"path": P, "captions": [{"start": round(a, 2), "end": round(b, 2), "text": s} for a, b, s in subs if b - a > 0.15], "style": SUB, "offsetY": 0.38})
        credits = []
        for mc in E.get("music", []):
            mp3, info = R.music_file(mc["track"]); credits.append(info["title"])
            st, en, fr, vol = float(mc["start"]), float(mc["end"]), float(mc.get("from", 0)), float(mc.get("vol", 0.16))
            # chia nhạc theo các đoạn có lời để hạ nhạc ở đó
            cuts = sorted({st, en, *[x for seg in talk for x in seg if st < x < en]}); pos = fr
            for k in range(len(cuts) - 1):
                a2, b2 = cuts[k], cuts[k + 1]
                if b2 - a2 < 0.05: continue
                speak = any(s0 <= a2 + 0.01 and b2 - 0.01 <= s1 for s0, s1 in talk)
                mcid = place(mp3, MUS, a2, pos, pos + (b2 - a2), 600)
                c.call("clip_update", {"path": P, "clipId": mcid, "patch": {"volume": vol * (0.45 if speak else 1.0) * 2.2,
                       "fadeIn": float(mc.get("fadein", 1.2)) if k == 0 else 0.25, "fadeOut": float(mc.get("fadeout", 2)) if k == len(cuts) - 2 else 0.25}})
                pos += b2 - a2
        for s in E.get("sfx", []):
            w = R.sfx_file(s["name"]); scid = c.call("clip_add", {"path": P, "mediaId": mid(w), "trackId": SFX, "start": float(s["at"])})["createdId"]
            c.call("clip_update", {"path": P, "clipId": scid, "patch": {"volume": float(s.get("vol", 0.5))}})
        c.call("project_save", {"path": P})
        print(f"dự án Concat: {P} ({total:.1f}s)")
        if export:
            t0 = time.time(); job = c.call("export_start", {"path": P, "output": str(out / "concat_final.mp4"), "crf": 20, "preset": "veryfast"})["job"]
            while True:
                s = c.call("export_wait", {"job": job, "timeoutSeconds": 600})
                if s.get("state") != "running": break
            print("xuất:", s.get("state"), f"{time.time()-t0:.0f}s", s.get("error", ""))
            # chuẩn độ lớn YouTube (-14 LUFS) bằng ffmpeg, giữ nguyên hình
            raw = out / "concat_raw.mp4"; (out / "concat_final.mp4").rename(raw)
            R.sh(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out / "concat_final.mp4")]); raw.unlink()
    (loc / name / "DOC_TRUOC.txt").write_text("Dự án Concat của Pum. Mở bằng app Concat (máy tính hoặc Android): File › Open, chọn thư mục này.\n"
        "Dự án chỉ ghi đường dẫn tới clip gốc, không chứa clip. Nếu Concat báo thiếu clip, chỉ cho nó thư mục chứa clip gốc trên máy (cùng tên file Pum đã gắn trong app).\n")
    shutil.make_archive(str(out / "concat_project"), "zip", str(loc), name)
    (out / "concat_credits.txt").write_text("\n\n".join(json.loads((HERE / "music.json").read_text())["credit"].replace("{title}", x) for x in dict.fromkeys(credits)))
    print("gói dự án:", out / "concat_project.zip")

if __name__ == "__main__":
    main()
