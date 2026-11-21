"""Ghép edl mới nhất với file đã prep theo nội dung (clip, in, out), không theo id.
python3 merge_prep.py edl_moi.json edl_ra.json -> in các đoạn chưa có bản prep"""
import json, sys, os
new, out = sys.argv[1:3]
import os
P = os.environ.get("PREP_DIR", "/home/claude/pumdung/testlate/prep")
E = json.load(open(new)); rep = json.load(open(P + "/report.json"))
by = {}
for sid, r in rep.items():
    if r.get("src") and os.path.exists(f"{P}/{sid}.mp4"): by.setdefault(tuple(r["src"]), f"{P}/{sid}.mp4")
bad = []
for s in E["segments"]:
    f = by.get((s["clip"], s["in"], s["out"]))
    if not f: bad.append(s["id"]); continue
    s["src_clip"], s["src_in"], s["src_out"] = s["clip"], s["in"], s["out"]
    s["path"] = f; s["out"] = round(float(s["out"]) - float(s["in"]), 3); s["in"] = 0.0
json.dump(E, open(out, "w"), ensure_ascii=False, indent=1)
print("chưa có bản prep:", ",".join(bad) if bad else "không")
