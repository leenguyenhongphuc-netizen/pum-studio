"""Thử cửa sổ dọc (vtrack) trên vài đoạn: in mốc, xuất ảnh mỗi 1 s theo đúng bộ lọc lia.
python3 vtest.py tt.json out.jpg id1,id2"""
import sys, json, subprocess, tempfile, glob
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
import render as R
from PIL import Image
E = json.load(open(sys.argv[1])); outp = sys.argv[2]; ids = sys.argv[3].split(",")
rows = []
for sg in E["segments"]:
    if sg["id"] not in ids or not sg.get("path"): continue
    src = sg["path"]; a, b = float(sg["in"]), float(sg["out"])
    vw, vh = [int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")[:2]]
    keys = R.vtrack(src, a, b, vw, vh, sg); print(sg["id"], sg["label"][:24], f"{b-a:.1f}s", "old vcx", round(R.vcx(src, a, b, vw, vh, sg), 3), "keys", [(round(t, 1), round(c, 3)) for t, c in keys], flush=True)
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", src, "-vf", R.vfit(keys, 1080, 1920) + ",fps=1,scale=216:384", f"{d}/f%03d.png"], check=True)
    fr = [Image.open(f) for f in sorted(glob.glob(f"{d}/f*.png"))][:12]
    row = Image.new("RGB", (220 * 12, 388), (20, 20, 20))
    for k, f in enumerate(fr): row.paste(f, (k * 220, 2))
    rows.append(row)
S = Image.new("RGB", (220 * 12, 388 * len(rows)), (20, 20, 20))
for k, r in enumerate(rows): S.paste(r, (0, k * 388))
S.save(outp, quality=85); print(outp)
