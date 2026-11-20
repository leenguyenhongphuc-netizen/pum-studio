import json, os, subprocess, threading, queue, time
B = "/home/claude/bmt"
import sys
fs = json.load(open(sys.argv[1]))
HAVE = set()
for m in os.listdir(f"{B}/meta"):
    x = json.load(open(f"{B}/meta/" + m)); HAVE.add((x["name"].rsplit(".",1)[0].lower(), int(x["size"])))
vids = {}
for f in fs:
    if f["mimeType"].startswith("video"):
        vids.setdefault((f["title"], f["fileSize"]), f)
todo = [f for f in vids.values() if not os.path.exists(f"{B}/meta/{f["id"]}.json") and (f["title"].rsplit(".",1)[0].lower(), int(f["fileSize"])) not in HAVE]
todo.sort(key=lambda f: int(f["fileSize"]))
q = queue.Queue(maxsize=3)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def dl():
    for f in todo:
        raw = f"{B}/raw/{f['id']}.mp4"
        mez = f"{B}/mez/{f['id']}.mp4"
        if not os.path.exists(mez):
            for t in range(4):
                r = subprocess.run(["curl", "-sSL", "--retry", "3", "-o", raw, "-w", "%{http_code}",
                                    f"https://drive.usercontent.google.com/download?id={f['id']}&export=download&confirm=t"],
                                   capture_output=True, text=True)
                if r.stdout == "200" and os.path.getsize(raw) == int(f["fileSize"]):
                    break
                log("retry dl", f["title"], r.stdout)
                time.sleep(5)
        q.put(f)
    q.put(None)


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", p],
                       capture_output=True, text=True)
    return json.loads(r.stdout)


threading.Thread(target=dl, daemon=True).start()
n = 0
while True:
    f = q.get()
    if f is None:
        break
    raw = f"{B}/raw/{f['id']}.mp4"
    mez = f"{B}/mez/{f['id']}.mp4"
    src = raw if os.path.exists(raw) else mez
    pr = probe(src)
    v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]
    if not os.path.exists(mez):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf",
                        "scale=-2:1080:flags=bicubic,fps=30000/1001,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                        "-movflags", "+faststart", mez], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mez, "-vn", "-ac", "1", "-ar", "16000", f"{B}/wav/{f['id']}.wav"])
    meta = {"id": f["id"], "name": f["title"], "size": int(f["fileSize"]), "dur": float(pr["format"]["duration"]),
            "w": v["width"], "h": v["height"], "codec": v["codec_name"],
            "created": pr["format"].get("tags", {}).get("creation_time", ""),
            "rot": [sd.get("rotation") for sd in v.get("side_data_list", []) if "rotation" in sd]}
    json.dump(meta, open(f"{B}/meta/{f['id']}.json", "w"))
    if os.path.exists(raw):
        os.remove(raw)
    n += 1
    log(n, "/", len(todo), f["title"], round(meta["dur"], 1), "s", meta["created"])
log("DONE", len(todo))
