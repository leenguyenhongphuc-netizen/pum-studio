"""Bản cuối 4K: tải từng video gốc 4K (Drive hoặc iCloud), làm đẹp + che riêng tư các đoạn dùng clip đó ở 3840x2160, xoá file gốc.
Chạy lại được: đoạn đã xong (prep4k/report.json) bỏ qua. python3 prep4k_run.py"""
import json, os, subprocess, time, base64, urllib.parse
B = "/home/claude/bmt"; RAW = f"{B}/raw4k"; os.makedirs(RAW, exist_ok=True)
BIG = "1yLnUP9JTatrw9QIYnkx2plVDNwdspaWr"
E = json.load(open("/home/claude/pumdung/testlate/edl_v5.json"))
for s_ in E["segments"]: s_["id"] = "p2_" + s_["id"]  # lượt 2: tên file riêng, không ghi đè bản 4K của lượt 1 (id đã dời)
json.dump(E, open("/tmp/edl_p2.json", "w"), ensure_ascii=False)
drv = {}
for f in ("drive2_all.json", "drive.json"):
    for x in json.load(open(f"{B}/{f}")):
        if isinstance(x, dict) and x.get("id"): drv[x["id"]] = int(x.get("fileSize") or x.get("size") or 0)
def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)
def icloud():
    G = "077ZtCItziULwDJbiathUsbUA"
    r = json.loads(subprocess.run(["curl", "-sS", "-X", "POST", "https://ckdatabasews.icloud.com/database/1/com.apple.cloudkit/production/public/records/resolve", "-H", "Content-Type: text/plain", "-d", json.dumps({"shortGUIDs": [{"value": G}]})], capture_output=True, text=True).stdout)["results"][0]
    tok = r["anonymousPublicAccess"]["token"]; part = r["anonymousPublicAccess"]["databasePartition"]
    url = f"{part}/database/1/com.apple.clouddocs/production/shared/changes/zone?publicAccessAuthToken={tok}"
    z = json.loads(subprocess.run(["curl", "-sS", "--max-time", "90", "-X", "POST", url, "-H", "Content-Type: text/plain", "-d", json.dumps({"zones": [{"zoneID": r["zoneID"]}]})], capture_output=True, text=True).stdout)["zones"][0]
    out = {}
    for x in z["records"]:
        if x["recordType"] != "content": continue
        f = x["fields"]; n = base64.b64decode(f["encryptedBasename"]["value"]).decode(); ext = f["extension"]["value"]
        out["icl_" + n.replace(" ", "_")] = {"size": f["size"]["value"], "url": f["fileContent"]["value"]["downloadURL"].replace("${f}", urllib.parse.quote(f"{n}.{ext}"))}
    return out
def fetch(c):
    p = f"{RAW}/{c}.mp4"
    if c == BIG: return f"{B}/raw/{BIG}.mp4"
    if os.path.exists(p): return p
    for t in range(4):
        if c.startswith("icl_"):
            L = icloud(); v = L[c]; url, size = v["url"], v["size"]
        else:
            url, size = f"https://drive.usercontent.google.com/download?id={c}&export=download&confirm=t", drv.get(c, 0)
        r = subprocess.run(["curl", "-sSL", "--retry", "3", "-o", p + ".part", "-w", "%{http_code}", url], capture_output=True, text=True)
        if r.stdout in ("200", "206") and (not size or os.path.getsize(p + ".part") == size): os.replace(p + ".part", p); return p
        log("thử lại", c, r.stdout); time.sleep(5)
    raise SystemExit("không tải được " + c)
order = []
for s in E["segments"]:
    if s["clip"] not in order: order.append(s["clip"])
order.sort(key=lambda c: c != BIG)
rp = "/home/claude/pumdung/testlate/prep4k/report.json"
for c in order:
    rep = json.load(open(rp)) if os.path.exists(rp) else {}
    done = {tuple(r.get("src", [])) for k_, r in rep.items() if os.path.exists(f"/home/claude/pumdung/testlate/prep4k/{k_}.mp4")}
    ids = [s["id"] for s in E["segments"] if s["clip"] == c and (c, s["in"], s["out"]) not in done]  # đoạn đã có bản 4K (theo nội dung) thì bỏ qua
    if not ids: continue
    t0 = time.time(); p = fetch(c); log("tải xong", c, round(os.path.getsize(p) / 1e9, 2), "GB", round(time.time() - t0), "s")
    r = subprocess.run(["python3", f"{B}/prep.py", "/tmp/edl_p2.json", "/tmp/prep4k_out.json", "--only", ",".join(ids), "--jobs", "1"],
                       env=dict(os.environ, PREP_4K="1"), capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.startswith("[") or "cần xử lý" in l]
    log(c, "xong", len(ids), "đoạn", round(time.time() - t0), "s", lines[-1][:120] if lines else r.stderr[-300:])
    if c != BIG and os.path.exists(p): os.remove(p)
log("XONG HẾT")
