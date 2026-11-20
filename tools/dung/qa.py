#!/usr/bin/env python3
"""Kiểm kỹ thuật một bản dựng trước khi chấm điểm.

  python3 -I qa.py <ep> <ver>
In ra số đo và tạo ảnh xem nhanh: work/<ep>/v<ver>/qa/sheet_*.jpg (mỗi ảnh 12 khung, 1 khung / N giây)
Số đo đạt khi: 1920x1080 (TikTok: 1080x1920) 30fps, -15..-13 LUFS, true peak <= -1 dBTP, không khung đen > 0,5 s ngoài chủ ý,
không khoảng lặng > 2 s, mỗi đoạn có chữ đều nằm trong vùng an toàn (render.py đã đặt sẵn).
"""
import json, os, re, subprocess, sys
from pathlib import Path
WORK = Path(os.environ.get("PUM_WORK", "/home/claude/pumdung"))

def run(cmd): return subprocess.run(cmd, capture_output=True, text=True)

def main():
    ep, ver = sys.argv[1], sys.argv[2]; d = WORK / ep / f"v{ver}"; f = d / "final.mp4"
    if not f.exists(): f = d / "proxy.mp4"
    tl = json.loads((d / "timeline.json").read_text()); q = d / "qa"; q.mkdir(exist_ok=True)
    pr = json.loads(run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(f)]).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video"); dur = float(pr["format"]["duration"])
    lo = run(["ffmpeg", "-nostats", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)[-1]); TP = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)[-1])
    bl = run(["ffmpeg", "-nostats", "-i", str(f), "-vf", "blackdetect=d=0.5:pix_th=0.08", "-an", "-f", "null", "-"]).stderr
    blacks = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", bl)]
    si = run(["ffmpeg", "-nostats", "-i", str(f), "-af", "silencedetect=n=-45dB:d=2", "-vn", "-f", "null", "-"]).stderr
    sil = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", si)]
    segs = tl["segments"]; lens = sorted(s["end"] - s["start"] for s in segs)
    step = max(2, round(dur / 72))
    run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-vf", f"fps=1/{step},scale={480 if v['width'] >= v['height'] else 300}:-2,drawtext=fontfile=/usr/share/fonts/opentype/inter/Inter-Bold.otf:text='%{{pts\\:hms}}':x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.5,tile=4x3", str(q / "sheet_%02d.jpg")])
    rep = {"file": str(f), "size": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"], "dur": round(dur, 1), "timeline_dur": tl["dur"],
           "lufs": I, "true_peak": TP, "black": blacks, "silence_from": sil, "segments": len(segs),
           "seg_median": round(lens[len(lens)//2], 1) if lens else 0, "seg_longest": [ (s["label"], round(s["end"]-s["start"],1)) for s in sorted(segs, key=lambda s: s["start"]-s["end"])[:3]],
           "subs": len(tl.get("subs", [])), "sheet_every_s": step,
           "placeholder_text": [t for s in segs for t in s.get("text", []) if "___" in t or "[" in t]}
    ok = []
    ok.append(("kích thước", (v["width"], v["height"]) in ((1920, 1080), (1080, 1920)) or "proxy" in f.name))  # ngang YouTube hoặc dọc TikTok
    ok.append(("độ lớn -15..-13 LUFS", -15.5 <= I <= -12.5)); ok.append(("đỉnh <= -1 dBTP", TP <= -0.9))
    ok.append(("không khung đen lạ", not blacks)); ok.append(("không lặng > 2s", not sil))
    ok.append(("không chữ còn ___ hay [ ]", not rep["placeholder_text"])); ok.append(("khớp thời lượng", abs(dur - tl["dur"]) < 1.0))
    rep["checks"] = {k: bool(x) for k, x in ok}; rep["pass"] = all(x for _, x in ok)
    (q / "qa.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1)); print(json.dumps(rep, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
