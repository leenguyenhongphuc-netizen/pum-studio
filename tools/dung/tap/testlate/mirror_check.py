"""Dò cảnh bị ngược gương: OCR khung gốc và khung lật ngang, so độ tin cậy chữ đọc được."""
import sys, json, subprocess, io, re
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
def grab(path, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=1920:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return np.array(Image.open(io.BytesIO(raw)).convert("RGB"))
def score(img):
    r, _ = ocr(img)
    s = 0.0; txt = []
    for box, t, c in (r or []):
        n = len(re.findall(r"[A-Za-zÀ-ỹ0-9]", t))
        if n >= 3: s += float(c) * n; txt.append(t)
    return s, txt
if __name__ == "__main__":
    E = json.load(open(sys.argv[1])); ids = sys.argv[2].split(",") if len(sys.argv) > 2 else None
    out = {}
    for sg in E["segments"]:
        if ids and sg["id"] not in ids: continue
        d = float(sg["out"]) - float(sg["in"]); a = float(sg["in"])
        S0 = S1 = 0.0; T0 = []; T1 = []
        for q in (0.2, 0.5, 0.8):
            img = grab(sg["path"], a + q * d)
            s0, t0 = score(img); s1, t1 = score(img[:, ::-1].copy())
            S0 += s0; S1 += s1; T0 += t0; T1 += t1
        out[sg["id"]] = [round(S0, 1), round(S1, 1), T0[:4], T1[:4]]
        print(sg["id"], sg.get("label"), round(S0, 1), round(S1, 1), "FLIP?" if S1 > S0 * 1.3 and S1 > 8 else "", T0[:3], "|", T1[:3], flush=True)
    json.dump(out, open("/home/claude/bmt/ocr/mirror.json", "w"), ensure_ascii=False)
