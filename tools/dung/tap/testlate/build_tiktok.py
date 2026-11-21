"""Cắt tập BMT thành loạt video TikTok dọc 9:16, mỗi câu chuyện một video.
Mỗi video: mở bằng câu hook (đoạn hay nhất của chính chuyện đó + băng chữ), kể trọn chuyện,
cuối video là đoạn gợi ý phần sau (hook của phần sau + băng "Phần N · …"). Phần cuối kết bằng câu hỏi.
python3 build_tiktok.py edl_merged.json out_dir"""
import json, sys, copy, re
from pathlib import Path

E = json.load(open(sys.argv[1])); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
H5 = json.load(open("/home/claude/pumdung/testlate/edl_v5.json"))  # bản ngang (danh nghĩa) để lấy tiếng hiệu ứng
SEG = E["segments"]; IDX = {s["id"]: k for k, s in enumerate(SEG)}

# tiếng hiệu ứng của bản ngang -> gắn vào từng đoạn (id, giây trong đoạn)
starts = {}; t = 0.0
for s in H5["segments"]:
    starts[s["id"]] = (t, t + s["out"] - s["in"]); t += s["out"] - s["in"]
SFX = {}
for f in H5["sfx"]:
    for sid, (a, b) in starts.items():
        if a <= f["at"] < b:
            SFX.setdefault(sid, []).append(dict(f, at=round(f["at"] - a, 3))); break

def find(label):
    return next(s["id"] for s in SEG if s["label"] == label)

def rng(a_label, b_label_excl=None, skip=()):
    """các đoạn từ nhãn a tới trước nhãn b (theo thứ tự bản ngang), bỏ các nhãn gốc trong skip"""
    i = IDX[find(a_label)]; j = IDX[find(b_label_excl)] if b_label_excl else len(SEG)
    return [s["id"] for s in SEG[i:j] if re.sub(r" \((tiếp|cảnh chèn)\)$", "", s["label"]) not in skip]

def sub(sid, a=None, b=None, newid=None, strict=False):
    """bản sao một đoạn, có thể chỉ lấy khúc [a, b] giây trong đoạn"""
    s = copy.deepcopy(SEG[IDX[sid]]); d = s["out"] - s["in"]
    a = 0.0 if a is None else a; b = d if b is None else min(b, d)
    s["in"] = round(s["in"] + a, 3); s["out"] = round(s["in"] + (b - a), 3); L = b - a
    keep = (lambda x, y: (min(y, b) - max(x, a)) >= 0.6 * (y - x)) if strict else (lambda x, y: y > a + 0.15 and x < b - 0.15)
    s["subs"] = [[round(max(0, x - a), 2), round(min(L, y - a), 2), tx] for x, y, tx in s.get("subs", []) if keep(x, y)]
    s["text"] = [dict(x, start=round(max(0, x["start"] - a), 2), end=round(min(L, x["end"] - a), 2), cont_in=False, cont_out=False)
                 for x in s.get("text", []) if x["end"] > a + 0.3 and x["start"] < b - 0.3]
    s["doodles"] = [dict(x, start=round(max(0, x["start"] - a), 2), end=round(min(L - 0.05, x["end"] - a), 2))
                    for x in s.get("doodles", []) if x["end"] > a + 0.6 and x["start"] < b - 0.6]
    if s.get("vo") and s["vo"].get("speech"):
        s["vo"]["in"] = round(s["vo"]["in"] + a, 3); s["vo"]["out"] = round(s["vo"]["in"] + L, 3)
    s["_sfx"] = [dict(f, at=round(f["at"] - a, 3)) for f in SFX.get(sid, []) if a <= f["at"] < b]
    s["hide_src"] = [dict(h, start=round(max(0, float(h.get("start", 0)) - a), 2), end=round(min(L, float(h.get("end", 1e6)) - a), 2))
                     for h in s.get("hide_src", []) if float(h.get("end", 1e6)) > a and float(h.get("start", 0)) < b]  # giờ ô che tính lại theo khúc cắt
    s["id"] = newid or sid; s.pop("trans", None); s["fade"] = 0.06
    return s

def bysub(words, pad=0.15, extra=0.35, lines=1):
    """(id, a, b) của dòng phụ đề chứa cụm chữ (lấy thêm các dòng sau cho đủ câu)"""
    for s in SEG:
        L = s.get("subs", [])
        for k, (x, y, tx) in enumerate(L):
            if words in tx:
                y2 = L[min(len(L) - 1, k + lines - 1)][1]
                return (s["id"], max(0.0, x - pad), min(s["out"] - s["in"], y2 + extra))
    raise SystemExit("không thấy câu: " + words)

def full(sid):
    s = copy.deepcopy(SEG[IDX[sid]]); s["_sfx"] = list(SFX.get(sid, [])); return s

def hook(parts, tape, label=None, subs=None, label_end=3.0):
    """parts: [(id, a, b)] ; băng chữ hook nằm suốt đoạn hook; nhãn series (nếu có) trong ~3 giây đầu"""
    segs = [sub(sid, a, b, newid=f"hook{k}_{sid}", strict=True) for k, (sid, a, b) in enumerate(parts)]
    for (sid, a, b), s in zip(parts, segs):
        s["text"] = [x for x in s["text"] if x["style"] not in ("tape", "label", "postcard")]
        s["doodles"] = []; s["_sfx"] = []
    if subs: segs[0]["subs"] = subs  # phụ đề gõ tay cho khúc hook (cắt giữa dòng phụ đề gốc)
    acc = 0.0
    for k, s in enumerate(segs):  # băng chữ (và nhãn) kéo liền qua các mảnh
        L = s["out"] - s["in"]
        tp = {"style": "tape", "text": tape, "start": 0.1 if k == 0 else 0.0, "end": round(L, 2), "cont_in": k > 0, "cont_out": k < len(segs) - 1}
        if label: tp["pos"] = TAPE_POS.get(tape, TAPE_Y_LABEL)
        s["text"].insert(0, tp)
        if label and acc < label_end:
            s["text"].insert(0, {"style": "label", "text": label, "start": round(max(0.1 - acc, 0), 2), "end": round(min(label_end - acc, L), 2),
                                 "cont_in": acc > 0.1, "cont_out": label_end > acc + L})
        acc += L
    segs[0]["_sfx"] = [{"name": "swoosh", "at": 0.15, "vol": 0.45}]
    return segs

TAPE_POS = {"Kịp hoàng hôn không đây?": 0.555}  # hook có mặt Pum chiếm nửa trên khung: đặt băng dưới mặt
TAPE_Y_LABEL = 0.165  # khung dọc: băng chữ hook nằm dưới nhãn series (nhãn ở 8,5% chiều cao)
SERIES = "Đi đâu thử đó"

# ---------------- các câu chuyện ----------------
S = []
_s21 = find("Hết sườn vì dậy trễ (tiếp)")
S.append(dict(n=1, title="Dậy trễ đi ăn bánh canh", tt="Dậy trễ\nđi ăn bánh canh",
              # "Mà hôm nay dậy trễ quá nên hết sườn rồi nha mọi người," (cắt ở khoảng nghỉ trước "chỉ còn…")
              hook=[(_s21, 1.76, 5.25)], hook_subs=[[0.05, 3.45, "Mà hôm nay dậy trễ quá nên hết sườn rồi nha mọi người"]],
              tape="Dậy trễ là… hết sườn!",
              body=rng("Hook", "Biển buôn", skip=("Thú nhận", "Xem trước cả ngày", "Tượng đài"))))  # vào thẳng chuyện bánh canh
S.append(dict(n=2, title="Buôn Ê Đê ngay giữa phố", tt="Buôn Ê Đê\nngay giữa phố",
              hook=[(find("Tưởng người Nhật"), 0.0, 2.7)], tape="Pum bị tưởng là người Nhật?!",
              body=rng("Biển buôn", "Đi ăn trưa")))
S.append(dict(n=3, title="Mâm cơm đồng bào 6 món", tt="Mâm cơm\nđồng bào 6 món",
              hook=[(find("Cay"), 0.0, None)], tape="Cay tới mức này luôn!",
              body=rng("Đi ăn trưa", "Đi tiếp lên farm")))
S.append(dict(n=4, title="Người không thích cà phê lên farm", tt="Người không\nthích cà phê lên farm",
              hook=[(x, 0.0, None) for x in rng("Thú nhận", "Xem trước cả ngày")], tape="Người Buôn Mê mà không thích cà phê?!",
              body=rng("Đi tiếp lên farm", "Quả cà phê đi đâu tiếp")))
S.append(dict(n=5, title="Tự rang, tự pha, uống thử", tt="Tự rang,\ntự pha, uống thử",
              hook=[(x, 0.0, None) for x in rng("Teaser", "Hook")][:1], tape="Pum tự pha cà phê…",  # chỉ "Thơm quá mọi người ơi!", giữ kết quả cho cuối video
              body=rng("Quả cà phê đi đâu tiếp", "Đi ngắm hoàng hôn")))
S.append(dict(n=6, title="Đi tìm hoàng hôn",
              hook=None, tape="Kịp hoàng hôn không đây?",
              body=rng("Đi ngắm hoàng hôn", "Đói bụng")))
S.append(dict(n=7, title="Món gì đây?",
              hook=[(find("Sụp sụp"), 0.0, None)], tape="Ngon nhất lòng Pum!",
              body=rng("Đói bụng", "Câu hỏi cuối")))

# hook phần 6: câu "chạy ra hồ Ea Kao mà nó lặn rồi chắc khóc to luôn" (2 mảnh cuối của "Thất bại")
tb = [s["id"] for s in SEG if s["label"].startswith("Thất bại")]
h6 = bysub("Chứ giờ mà chạy ra hồ Ea Kao")
S[5]["hook"] = [(h6[0], h6[1], None)] + [(x, 0.0, None) for x in tb[tb.index(h6[0]) + 1:]]

MUS = {"Mở tập": "cheery_monday", "Chương 1 · Bánh canh": "daily_beetle", "Chương 2 · Nhà dài giữa phố": "dream_culture",
       "Chương 3 · Cơm đồng bào": "bossa_antigua", "Chương 4 · Lên farm cà phê": "life_of_riley", "Chương 5 · Đi tìm hoàng hôn": "dreamer",
       "Chương 6 · Tối · Mì hoành thánh": "daily_beetle", "Cuối tập": "late_night_radio"}
SWITCH = {"Mùa cà phê chín": "dream_culture", "Nếm thử": None, "Kịp rồi": "late_night_radio", "Quả cà phê đi đâu tiếp": "dream_culture"}

for k, st in enumerate(S):
    segs = []
    hk = hook(st["hook"], st["tape"], label=f"Phần {st['n']}/{len(S)} · {SERIES}", subs=st.get("hook_subs"))
    segs += hk
    body = [sub(x, 8.55, None, newid=x, strict=True) if st["n"] == 1 and SEG[IDX[x]]["label"] == "Dậy trễ" else full(x) for x in st["body"]]  # phần 1: chỉ giữ câu "dậy trễ rồi"
    for s in body:  # nhãn series đã có ở hook
        s["text"] = [x for x in s.get("text", []) if not (x["style"] == "label" and x["text"] == SERIES)]
    body[0].pop("trans", None); body[0]["_sfx"] = [f for f in body[0]["_sfx"] if f["name"] != "whoosh"] + [{"name": "whoosh", "at": -0.25, "vol": 0.35}]
    segs += body
    if k + 1 < len(S):
        nx = S[k + 1]
        tz = hook(nx["hook"], f"Phần {nx['n']} · " + nx.get("tt", nx["title"]), subs=nx.get("hook_subs"))
        tz[0]["_sfx"] = [{"name": "whoosh", "at": -0.25, "vol": 0.35}, {"name": "ding", "at": 0.3, "vol": 0.35}]
        for s in tz: s["id"] = "next_" + s["id"]
        segs += tz
    else:
        q = full(find("Câu hỏi cuối")); q["_sfx"] = [{"name": "sparkle", "at": 0.4, "vol": 0.4}]
        pm = full(find("Pum ăn mì"))  # nền thẻ hỏi: cảnh tô mì của chính phần này
        for k_ in ("path", "clip", "in", "out", "src_clip", "src_in", "src_out", "crop"): q[k_] = pm.get(k_)
        q["audio"] = "low"; q["out"] = round(min(float(q["out"]), float(pm["in"]) + 5.0), 3) if q.get("in") is not None else q["out"]
        for x in q["text"]:
            if x["style"] == "question": x["text"] = "Ở chỗ bạn có quán mì hoành thánh nào ngon không?"; x["pos"] = 0.56  # dưới mặt Pum
        segs.append(q)
    # mọi đoạn khung dọc: cửa sổ 9:16 tự theo mặt Pum (vùng crop cũ thành giới hạn)
    for s in segs:
        s["cx"] = "auto"; s.pop("zoom", None)
        if s["label"] == "Tự pha cà phê": s["cx"] = 0.515  # khung dọc vào phễu và ấm rót, không bám mặt
        if s["label"] == "Đoán món (cảnh chèn)": s["cx"] = 0.47; s["bright"] = 0.05  # biển Mì Hường trọn chữ
    # dòng thời gian, tiếng hiệu ứng, nhạc
    t = 0.0; sfx = []; music = []; cur = None
    trk = MUS[body[0]["chapter"]]; seen = set(); prev_ch = None
    for s in segs:
        d = s["out"] - s["in"]
        for f in s.pop("_sfx", []):
            sfx.append({"name": f["name"], "at": round(max(0, t + f["at"]), 2), "vol": f.get("vol", 0.4)})
        base = re.sub(r" \((tiếp|cảnh chèn)\)$", "", s["label"])
        if not s["id"].startswith(("hook", "next_")):
            if s["chapter"] != prev_ch and s["chapter"] in MUS and prev_ch is not None: trk = MUS[s["chapter"]]
            prev_ch = s["chapter"]
            if base in SWITCH and base not in seen: trk = SWITCH[base]; seen.add(base)
        tk = trk if not s["id"].startswith("next_") else (trk or MUS[body[-1]["chapter"]])
        if s["id"].startswith("next_") and trk is None: trk = tk
        if tk is None: cur = None
        elif cur and cur["track"] == tk and abs(cur["end"] - t) < 0.05: cur["end"] = round(t + d, 2)
        else:
            cur = {"track": tk, "start": round(t, 2), "end": round(t + d, 2), "from": 0, "vol": 0.2, "fadein": 0.8, "fadeout": 1.5}; music.append(cur)
        t += d
    for m in music:
        m["vol"] = {"late_night_radio": 0.15}.get(m["track"], 0.2)
    sfx.sort(key=lambda f: f["at"])
    ed = {"ep": "testlate", "ver": int(__import__("os").environ.get("TT_BASE", "100")) + st["n"], "size": [1080, 1920], "segments": segs, "music": music, "sfx": sfx,
          "title": f"Phần {st['n']} · {st['title']}"}
    json.dump(ed, open(OUT / f"tt{st['n']}.json", "w"), ensure_ascii=False, indent=1)
    print(f"Phần {st['n']} · {st['title']}: {len(segs)} đoạn, {t:.1f} s, hook {sum(s['out']-s['in'] for s in hk):.1f} s")
