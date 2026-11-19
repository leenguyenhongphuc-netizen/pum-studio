"""Tiền xử lý từng đoạn của edl trước khi dựng: làm đẹp Pum (beauty.py, preset của skill pum-lam-dep-video),
màu tổng thể, che mặt người khác và biển số xe. Ghi /home/claude/pumdung/testlate/prep/<id>.mp4 (giữ tiếng gốc),
xuất edl mới trỏ "path" vào file đã xử lý. Có bộ nhớ đệm theo (clip, in, out, preset) nên chạy lại chỉ làm đoạn đổi.
python3 -I prep.py edl_in.json edl_out.json [--only id1,id2] [--jobs 2]"""
import json, sys, subprocess, pathlib, hashlib, os, time
import numpy as np, cv2

sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
M = pathlib.Path("/home/claude/models")
OUT = pathlib.Path("/home/claude/pumdung/testlate/prep"); OUT.mkdir(exist_ok=True)
CL = json.load(open("/home/claude/pumdung/testlate/match.json"))["clips"]
PRE = json.load(open("/home/claude/pum-studio/tools/dung/presets/beauty_pum.json"))
FOOD = ("Tô bánh canh", "Cận tô", "Cận mâm", "Hết sườn vì dậy trễ (cảnh chèn)", "Mâm 6 món (cảnh chèn)", "Từng món (cảnh chèn)",
        "Thịt ba chỉ nướng (cảnh chèn)", "Rang hạt", "Rót nước", "Hạt cũng cần nghỉ (cảnh chèn)")


NOBLUR = ("Kịp rồi", "Mây giống gì", "Mây khủng long", "Câu hỏi cuối")  # cảnh trời, cây: máy hay nhận nhầm bóng cây thành mặt
def noblur(sg): return sg["label"].startswith(NOBLUR + ("Phía sau nhà",)) or str(sg.get("clip", "")).startswith("1Y-NTM")

def preset_for(sg):
    p = json.loads(json.dumps(PRE))
    if sg["label"] == "Phía sau nhà":  # cảnh này bị ám xanh: ấm lại cho khớp cảnh nhà dài
        p["color"]["warmth"] = 0.35; p["color"]["tint"] = 0.35; p["color"]["exposure"] = 0.1
    if sg["label"] in FOOD:  # món ăn: màu nhẹ, không hồng, không ấm thêm
        p["color"] = {"exposure": 0.04, "contrast": 0.98, "saturation": 1.02, "warmth": 0.0, "tint": 0.04, "glow": 0.05, "lift": 0.01}
    return p


def worker(job):
    import beauty as Bm
    sg, src, a, b, w, h = job
    P = preset_for(sg)
    W, H = (1920, 1080) if w >= h else (int(round(1080 * w / h / 2) * 2), 1080)
    B = Bm.Beauty(P, video=True)
    det = cv2.FaceDetectorYN.create(str(M / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.5, 0.3, 5000)
    import onnxruntime as ort
    lp = ort.InferenceSession(str(M / "lp_s.onnx"), providers=["CPUExecutionProvider"]); LPS = 640

    def plates(img, conf=0.28):
        Hh, Ww = img.shape[:2]; r = LPS / max(Hh, Ww); nw, nh = int(Ww * r), int(Hh * r)
        pad = np.full((LPS, LPS, 3), 114, np.uint8); pad[:nh, :nw] = cv2.resize(img, (nw, nh))
        x = pad[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        o = lp.run(None, {"images": x})[0][0]; m = o[4] > conf
        if not m.any(): return []
        cx, cy, bw, bh, sc = o[:, m]; bx = np.stack([cx - bw / 2, cy - bh / 2, bw, bh], 1) / r
        keep = cv2.dnn.NMSBoxes(bx.tolist(), sc.tolist(), conf, 0.45)
        return [bx[i] for i in np.array(keep).flatten()]

    def blur_box(img, x, y, bw, bh, pad=0.3, ellipse=True):
        Hh, Ww = img.shape[:2]
        x0 = int(max(0, x - bw * pad)); y0 = int(max(0, y - bh * pad)); x1 = int(min(Ww, x + bw * (1 + pad))); y1 = int(min(Hh, y + bh * (1 + pad)))
        if x1 - x0 < 4 or y1 - y0 < 4: return
        roi = img[y0:y1, x0:x1]
        small = cv2.resize(roi, (max(1, (x1 - x0) // 14), max(1, (y1 - y0) // 14)), interpolation=cv2.INTER_AREA)
        k = max(15, (max(x1 - x0, y1 - y0) // 3) | 1)
        bl = cv2.GaussianBlur(cv2.resize(small, (x1 - x0, y1 - y0)), (k, k), 0)
        if ellipse:
            mm = np.zeros(roi.shape[:2], np.uint8); cv2.ellipse(mm, ((x1 - x0) // 2, (y1 - y0) // 2), ((x1 - x0) // 2, (y1 - y0) // 2), 0, 0, 360, 255, -1)
            mm = cv2.GaussianBlur(mm, (21, 21), 0)[..., None] / 255.0
            roi[:] = (bl * mm + roi * (1 - mm)).astype(np.uint8)
        else: roi[:] = bl

    GUIDE = {"1yLnUP9JTatrw9QIYnkx2plVDNwdspaWr"}  # đoạn anh hướng dẫn nói: không coi là Pum tự quay
    selfie = sg.get("voice") == "noi" and sg.get("audio") == "src" and sg["clip"] not in GUIDE and not sg["label"].startswith(("Robusta", "Mùa cà phê", "Pha xong", "Vị khói", "Tự pha"))
    out = OUT / f'{sg["id"]}.mp4'; tmpv = OUT / f'{sg["id"]}.v.mp4'
    fs = W * H * 3
    def reader():
        return subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src, "-vf", f"scale={W}:{H}:flags=lanczos,fps=30", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    rec = cv2.FaceRecognizerSF.create(str(M / "face_recognition_sface_2021dec.onnx"), ""); REF = np.load(M / "pum_ref.npy")
    # ---- lượt 1: dò mặt, biển số; gom mặt thành vệt theo thời gian; quyết định ai là Pum theo cả vệt ----
    dets = []; pls = []; n = 0
    if not noblur(sg):
        rd = reader()
        while True:
            buf = rd.stdout.read(fs)
            if len(buf) < fs: break
            if n % 2 == 0:
                img = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
                det.setInputSize((W, H)); _, f = det.detect(img)
                for r in ([] if f is None else f):
                    if r[2] < 10 or r[14] < (0.6 if r[2] > 60 else 0.7): continue
                    sim = None
                    if r[2] >= 36:
                        e = rec.feature(rec.alignCrop(img, r)).flatten(); e /= np.linalg.norm(e) + 1e-9; sim = float((REF @ e).max())
                    dets.append([n, float(r[0]), float(r[1]), float(r[2]), float(r[3]), sim])
                if n % 4 == 0:
                    for x0, y0, bw, bh in plates(img, 0.45):
                        if 1.3 <= bw / max(bh, 1) <= 6.5 and bw >= 18: pls.append([n, x0, y0, bw, bh])
            n += 1
        rd.stdout.close(); rd.wait()
    # vệt mặt
    tracks = []
    for d in sorted(dets):
        cx, cy = d[1] + d[3] / 2, d[2] + d[4] / 2; bestt = None
        for t in tracks:
            l = t[-1]
            if 0 < d[0] - l[0] <= 8 and abs(cx - (l[1] + l[3] / 2)) < 0.7 * max(d[3], l[3]) and abs(cy - (l[2] + l[4] / 2)) < 0.7 * max(d[4], l[4]) and 0.5 < d[3] / l[3] < 2:
                bestt = t; break
        (bestt.append(d) if bestt else tracks.append([d]))
    big_per_frame = {}
    for d in dets: big_per_frame[d[0]] = max(big_per_frame.get(d[0], 0), d[3])
    pum_tracks, blur_tracks = [], []
    for t in tracks:
        sims = [d[5] for d in t if d[5] is not None]; mw = float(np.mean([d[3] for d in t]))
        largest = np.mean([d[3] >= 0.7 * big_per_frame[d[0]] for d in t]) > 0.6
        edge = np.mean([d[1] < 4 or d[2] < 4 or d[1] + d[3] > W - 4 for d in t]) > 0.5
        if sims and (max(sims) >= 0.30 or np.median(sims) >= 0.22): pum_tracks.append(t)
        elif selfie and largest and mw > 0.05 * W: pum_tracks.append(t)
        elif edge and mw > 0.06 * W: pum_tracks.append(t)
        elif sims and max(sims) < 0.16 and len(sims) >= 2: blur_tracks.append(t)
        elif mw < 0.035 * W: blur_tracks.append(t)          # mặt nhỏ phía xa: người lạ
        elif len(t) >= 3 and not selfie: blur_tracks.append(t)
        else: pum_tracks.append(t)                         # không chắc: không che (che nhầm Pum tệ hơn)
    def interp(t):  # khung -> hộp, nội suy giữa các lần dò, kéo dài 3 khung hai đầu
        out = {}
        for d0, d1 in zip(t, t[1:] + [t[-1]]):
            for k in range(d0[0], max(d0[0] + 2, d1[0])):
                u = (k - d0[0]) / max(1, d1[0] - d0[0]); out[k] = [d0[i] + (d1[i] - d0[i]) * u for i in (1, 2, 3, 4)]
        for k in range(t[0][0] - 3, t[0][0]): out[k] = t[0][1:5]
        for k in range(t[-1][0] + 1, t[-1][0] + 4): out[k] = t[-1][1:5]
        return out
    fblur = {}
    for t in blur_tracks:
        for k, bx in interp(t).items(): fblur.setdefault(k, []).append(("face", bx))
    pumbox = {}
    for t in pum_tracks:
        for k, bx in interp(t).items(): pumbox.setdefault(k, []).append(bx)
    for p_ in pls:
        k0, x0, y0, bw, bh = p_
        onpum = any(px - pw * 1.3 < x0 + bw / 2 < px + pw * 2.3 and y0 > py for px, py, pw, ph in pumbox.get(k0, []))
        if onpum: continue
        for k in range(k0 - 2, k0 + 5): fblur.setdefault(k, []).append(("plate", [x0, y0, bw, bh]))
    # ---- lượt 2: làm đẹp + che ----
    rd = reader()
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
                           "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", str(tmpv)], stdin=subprocess.PIPE)
    n = 0; st = {"frames": 0, "pum": 0, "stranger": 0, "plate": 0, "tracks": len(tracks), "blur_tracks": len(blur_tracks)}
    while True:
        buf = rd.stdout.read(fs)
        if len(buf) < fs: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        out_img = B.apply(img)
        if B.prev is not None: st["pum"] += 1
        for kind, (x, y, bw, bh) in fblur.get(n, []):
            blur_box(out_img, x, y, bw, bh, pad=0.4 if kind == "plate" else 0.35, ellipse=kind == "face")
        st["stranger"] += any(k_ == "face" for k_, _ in fblur.get(n, [])); st["plate"] += any(k_ == "plate" for k_, _ in fblur.get(n, []))
        wr.stdin.write(out_img.tobytes()); n += 1
    wr.stdin.close(); wr.wait(); rd.wait(); st["frames"] = n
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmpv), "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src, "-map", "0:v", "-map", "1:a?",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", str(out)], check=True)
    tmpv.unlink()
    return sg["id"], st


def main():
    ein, eout = sys.argv[1], sys.argv[2]
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 1
    E = json.load(open(ein)); rp = OUT / "report.json"; rep = json.load(open(rp)) if rp.exists() else {}
    todo = []
    for sg in E["segments"]:
        c = CL[sg["clip"]]; src = c["path"]
        key = hashlib.sha1(json.dumps([sg["clip"], sg["in"], sg["out"], preset_for(sg), "v4"] + (["noblur"] if noblur(sg) else []), sort_keys=True).encode()).hexdigest()[:12]
        sg["_key"] = key; sg["_src"] = src
        r0 = rep.get(sg["id"], {})
        if (only and sg["id"] not in only) or (rep.get(sg["id"], {}).get("key") == key and (OUT / f'{sg["id"]}.mp4').exists()): continue
        todo.append((sg, src, float(sg["in"]), float(sg["out"]), c.get("w") or 1920, c.get("h") or 1080))
    print("cần xử lý", len(todo), "đoạn", flush=True); t0 = time.time()
    if jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(jobs) as ex:
            for k, (sid, st) in enumerate(ex.map(worker, todo)):
                sg = next(x for x in E["segments"] if x["id"] == sid); st["key"] = sg["_key"]; st["src"] = [sg["clip"], sg["in"], sg["out"]]; rep[sid] = st
                json.dump(rep, open(rp, "w"), indent=0); print(f"[{k+1}/{len(todo)}] {sid} {sg['label']} {st} {time.time()-t0:.0f}s", flush=True)
    else:
        for k, j in enumerate(todo):
            sid, st = worker(j); st["key"] = j[0]["_key"]; st["src"] = [j[0]["clip"], j[0]["in"], j[0]["out"]]; rep[sid] = st
            json.dump(rep, open(rp, "w"), indent=0); print(f"[{k+1}/{len(todo)}] {sid} {j[0]['label']} {st} {time.time()-t0:.0f}s", flush=True)
    for sg in E["segments"]:
        sg.pop("_key", None); sg.pop("_src", None)
        if only and sg["id"] not in only: continue
        sg["src_clip"] = sg["clip"]; sg["src_in"] = sg["in"]; sg["src_out"] = sg["out"]
        sg["path"] = str(OUT / f'{sg["id"]}.mp4'); sg["out"] = round(float(sg["out"]) - float(sg["in"]), 3); sg["in"] = 0.0
    json.dump(E, open(eout, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
