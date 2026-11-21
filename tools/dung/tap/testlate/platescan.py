"""Dò biển số còn đọc được trên bản xuất 4K (máy dò lúc prep chạy ở 1080 nên sót biển nhỏ, ở 4K lại đọc rõ).
python3 platescan.py video.mp4 out.json [fps]"""
import sys, json, subprocess, cv2, numpy as np, onnxruntime as ort
sys.path.insert(0, "/home/claude/bmt")
from platefilt import plate_like
src, out = sys.argv[1], sys.argv[2]; fps = float(sys.argv[3]) if len(sys.argv) > 3 else 2
lp = ort.InferenceSession("/home/claude/models/lp_s.onnx", providers=["CPUExecutionProvider"]); LPS = 640
def plates(img, conf):
    Hh, Ww = img.shape[:2]; r = LPS / max(Hh, Ww); nw, nh = int(Ww * r), int(Hh * r)
    pad = np.full((LPS, LPS, 3), 114, np.uint8); pad[:nh, :nw] = cv2.resize(img, (nw, nh))
    x = pad[..., ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    o = lp.run(None, {"images": x})[0][0]; m = o[4] > conf
    if not m.any(): return []
    cx, cy, bw, bh, sc = o[:, m]; bx = np.stack([cx - bw / 2, cy - bh / 2, bw, bh], 1) / r
    keep = cv2.dnn.NMSBoxes(bx.tolist(), sc.tolist(), conf, 0.45)
    return [(bx[i], float(sc[i])) for i in np.array(keep).flatten()]
W, H = 3840, 2160
rd = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
hits = []; n = 0; TW, TH = 1280, 720
while True:
    b = rd.stdout.read(W * H * 3)
    if len(b) < W * H * 3: break
    img = np.frombuffer(b, np.uint8).reshape(H, W, 3); t = n / fps
    for oy in (0, 480, 960, 1440):
        for ox in range(0, W - TW + 1, 640):
            for (x, y, bw, bh), sc in plates(img[oy:oy + TH, ox:ox + TW], float(__import__("os").environ.get("PCONF", "0.35"))):
                x += ox; y += oy
                if bw < 40 or not (0.8 <= bw / max(bh, 1) <= 6.5) or bw * bh > 0.01 * W * H: continue
                x0, y0 = int(max(0, x)), int(max(0, y)); crop = img[y0:int(y + bh), x0:int(x + bw)]
                if crop.size == 0: continue
                sharp = cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                if sharp < float(__import__("os").environ.get("PSHARP", "60")) or (__import__("os").environ.get("PLIKE", "1") == "1" and not plate_like(img, x, y, bw, bh)): continue
                hits.append([round(t, 2), int(x), int(y), int(bw), int(bh), round(sc, 2), round(sharp)])
    n += 1
    if n % 100 == 0: print(n, len(hits), flush=True)
# gộp trùng
H2 = []
for h in sorted(hits):
    if H2 and h[0] == H2[-1][0] and abs(h[1] - H2[-1][1]) < 60 and abs(h[2] - H2[-1][2]) < 60: continue
    H2.append(h)
json.dump(H2, open(out, "w")); print("xong", n, "khung", len(H2), "biển")
