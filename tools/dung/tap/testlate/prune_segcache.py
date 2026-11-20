"""Dọn kho segcache: chỉ giữ các đoạn mà các bản dựng đang dùng (theo khoá nội dung của render.py).
python3 prune_segcache.py edl_v7m.json:1920x1080 tt/tt1.json:1080x1920 ...   (đường dẫn tính từ thư mục tập)"""
import sys, json, os
from pathlib import Path
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
import render as R
d = Path("/home/claude/pumdung/testlate")
clips = dict(json.load(open(d / "match.json"))["clips"])
keep = set()
for arg in sys.argv[1:]:
    p, wh = arg.split(":"); W, H = [int(x) for x in wh.split("x")]
    if not (d / p).exists(): continue
    for sg in json.load(open(d / p))["segments"]:
        try: keep.add(R.seg_key(sg, clips, W, H))
        except Exception as e: print("bỏ qua", sg.get("id"), e)
n = 0; tot = 0
for f in (d / "segcache").iterdir():
    if f.stem not in keep:
        tot += f.stat().st_size if f.stat().st_nlink == 1 else 0; f.unlink(); n += 1
print(f"giữ {len(keep)} khoá, xoá {n} file, giải phóng ~{tot/1e9:.2f} GB")
