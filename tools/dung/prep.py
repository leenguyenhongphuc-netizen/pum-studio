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
def noblur(sg): return sg["label"].startswith(NOBLUR) or sg["id"] in ("s95", "s48")

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
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src, "-vf", f"scale={W}:{H}:flags=lanczos,fps=30", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "30", "-i", "-",
                           "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", str(tmpv)], stdin=subprocess.PIPE)
    fs = W * H * 3; n = 0; hold = []; st = {"frames": 0, "pum": 0, "stranger": 0, "plate": 0}
    while True:
        buf = rd.stdout.read(fs)
        if len(buf) < fs: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        out_img = B.apply(img)
        pum_lm = B.prev
        if pum_lm is not None: st["pum"] += 1
        if n % 2 == 0 and not noblur(sg):
            new = []; det.setInputSize((W, H)); _, f = det.detect(img)
            ff = [] if f is None else [r for r in f if r[14] >= 0.62]
            big = max([r[2] for r in ff], default=0)
            for r in ([] if f is None else f):
                if selfie and r[2] >= big * 0.7 and r[2] > 0.06 * W: continue  # đoạn Pum tự quay: mặt lớn nhất là Pum
                x, y, fw, fh = r[:4]
                if fw < 10 or r[14] < (0.62 if fw > 60 else 0.72): continue  # bỏ nhận nhầm (cốc, tường)
                if fw > 0.06 * W and (y < 4 or x < 4 or x + fw > W - 4): continue  # mặt bị cắt ở mép khung: thường là cằm Pum cầm máy, không che
                if fw > 0.12 * W and pum_lm is None:  # mặt rất to sát máy: gần như luôn là Pum quay selfie
                    if B.ref is None: continue
                    e = B.rec.feature(B.rec.alignCrop(img, r)).flatten(); e /= np.linalg.norm(e) + 1e-9
                    if float((B.ref @ e).max()) >= 0.12: continue
                if pum_lm is not None:
                    c = pum_lm.mean(0)
                    if abs(x + fw / 2 - c[0]) < fw * 0.7 and abs(y + fh / 2 - c[1]) < fh * 0.8: continue  # mặt Pum
                elif B.ref is not None and fw >= 40:
                    e = B.rec.feature(B.rec.alignCrop(img, r)).flatten(); e /= np.linalg.norm(e) + 1e-9
                    if float((B.ref @ e).max()) >= 0.24: continue
                new.append([x, y, fw, fh, 6, "face"])
            if n % 4 == 0:
                for x0, y0, bw, bh in plates(img, 0.4):
                    if pum_lm is not None:
                        fx0, fx1 = pum_lm[:, 0].min(), pum_lm[:, 0].max(); fwid = fx1 - fx0
                        if fx0 - fwid * 1.2 < x0 + bw / 2 < fx1 + fwid * 1.2 and y0 > pum_lm[:, 1].min(): continue  # trên người Pum: không che
                    new.append([x0, y0, bw, bh, 8, "plate"])
            else:
                new += [h_ for h_ in hold if h_[5] == "plate" and h_[4] > 2]
            hold = [h_ for h_ in hold if h_[4] > 0 and h_[5] == "face"] + new
        for h_ in hold:
            blur_box(out_img, h_[0], h_[1], h_[2], h_[3], pad=0.4 if h_[5] == "plate" else 0.35, ellipse=h_[5] == "face"); h_[4] -= 1
        st["stranger"] += any(h_[5] == "face" for h_ in hold); st["plate"] += any(h_[5] == "plate" for h_ in hold)
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
        key = hashlib.sha1(json.dumps([sg["clip"], sg["in"], sg["out"], preset_for(sg), "v3"] + (["noblur"] if noblur(sg) else []), sort_keys=True).encode()).hexdigest()[:12]
        sg["_key"] = key; sg["_src"] = src
        r0 = rep.get(sg["id"], {})
        if r0 and r0.get("stranger", 1) == 0 and r0.get("plate", 1) == 0 and r0.get("src") == [sg["clip"], sg["in"], sg["out"]]: sg["_key"] = r0["key"] = key  # không có gì để che: giữ bản cũ
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
