"""Đo rung do làm đẹp: so độ thay đổi giữa hai khung liền nhau ở vùng mặt/người, bản prep so với bản gốc.
Tỉ lệ ~1,0 là không thêm rung; > 1,15 là làm đẹp gây giật. python3 jitter.py edl_v6.json s18,s21,..."""
import json, subprocess, sys, numpy as np
E = json.load(open(sys.argv[1])); ids = sys.argv[2].split(",")
I = {}
CL = json.load(open("/home/claude/pumdung/testlate/match.json"))["clips"]
BIG = "1yLnUP9JTatrw9QIYnkx2plVDNwdspaWr"
def frames(src, a, dur, crop):
    vf = f"scale=480:270,crop={crop},format=gray"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-i", src, "-t", f"{dur:.3f}", "-vf", vf, "-f", "rawvideo", "-"], capture_output=True).stdout
    w, h = [int(x) for x in crop.split(":")[:2]]
    return np.frombuffer(raw, np.uint8)[: (len(raw) // (w * h)) * w * h].reshape(-1, h, w).astype(float)
for sid in ids:
    s = next(x for x in E["segments"] if x["id"] == sid)
    src = f"/home/claude/bmt/raw/{BIG}.mp4" if s["clip"] == BIG else CL[s["clip"]]["path"]
    d = min(6.0, s["out"] - s["in"]); crop = "240:200:120:20"  # vùng giữa khung (mặt, thân trên ở selfie)
    r = frames(src, s["in"], d, crop); p = frames(f"/home/claude/pumdung/testlate/prep/{sid}.mp4", 0, d, crop)
    n = min(len(r), len(p))
    dr = np.abs(np.diff(r[:n], axis=0)).mean((1, 2)); dp = np.abs(np.diff(p[:n], axis=0)).mean((1, 2))
    # rung = phần thay đổi thêm, tính ở khung đứng yên nhất (nơi rung dễ thấy nhất)
    q = dr < np.percentile(dr, 40)
    print(f"{sid:6s} {s['label'][:28]:28s} gốc {dr.mean():.2f} prep {dp.mean():.2f} tỉ lệ {dp.mean()/max(dr.mean(),1e-6):.2f}  khung tĩnh {dp[q].mean()/max(dr[q].mean(),1e-6):.2f}")
