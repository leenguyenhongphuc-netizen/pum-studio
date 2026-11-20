"""edl v5 cho tập test BMT (dậy muộn): giữ trọn câu thoại, thêm khoảnh khắc vui trên đường, phụ đề khớp từng chữ,
hiệu ứng doodle + âm thanh theo nội dung, nhạc to hơn. Số #n là số trong ov2_index.json. Lời phụ đề do mình chép lại."""
import json, re, os, unicodedata, difflib
B = "/home/claude/bmt"
IDX = json.load(open(f"{B}/ov2_index.json"))
BIG = "1yLnUP9JTatrw9QIYnkx2plVDNwdspaWr"
ASR = json.load(open(f"{B}/asr2.json"))
VO = json.load(open("/home/claude/pumdung/testlate/vo_tmp/vo.json"))
VO.update(json.load(open("/home/claude/pumdung/testlate/vo_pum.json")))  # giọng Pum đã thu (20/11)
segs = []

def cid(n): return BIG if n == "BIG" else IDX[str(n)]
MEZ = lambda n: f"{B}/raw/{BIG}.mp4" if n == "BIG" else f"{B}/mez/{cid(n)}.mp4"

def norm(w):
    w = unicodedata.normalize("NFD", w.lower()); w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9đ]", "", w.replace("đ", "d"))

def align(n, a, b, text):
    """thời điểm (giờ trong clip) cho từng chữ của câu đã sửa, dựa vào mốc chữ của máy nghe"""
    W = [w for g in ASR.get(cid(n), []) for w in g["words"] if a - 0.3 <= w[0] <= b + 0.1]
    toks = text.split(); tn = [norm(t) for t in toks]; wn = [norm(w[2]) for w in W]
    tm = [None] * len(toks)
    for blk in difflib.SequenceMatcher(None, tn, wn, autojunk=False).get_matching_blocks():
        for k in range(blk.size): tm[blk.a + k] = W[blk.b + k][0]
    # nội suy chữ không khớp
    known = [(i, t) for i, t in enumerate(tm) if t is not None]
    if not known: known = [(0, a + 0.1), (len(toks) - 1, b - 0.3)]
    for i in range(len(toks)):
        if tm[i] is None:
            prv = max([k for k in known if k[0] < i], default=(-1, a + 0.05), key=lambda k: k[0])
            nxt = min([k for k in known if k[0] > i], default=(len(toks), b - 0.2), key=lambda k: k[0])
            tm[i] = prv[1] + (nxt[1] - prv[1]) * (i - prv[0]) / max(1, nxt[0] - prv[0])
    for i in range(1, len(tm)): tm[i] = max(tm[i], tm[i - 1] + 0.05)
    return toks, tm

def subs_for(n, a, b, text, maxc=42):
    toks, tm = align(n, a, b, text); out = []; cur = []
    for i, t in enumerate(toks):
        cand = " ".join(x for x, _ in cur + [(t, 0)])
        if cur and len(cand) > maxc and not (re.search(r"[.!?…,]$", t) and len(cand) <= maxc + 10):
            out.append(cur); cur = []
        cur.append((t, tm[i]))
        if re.search(r"[.!?…]$", t) and len(" ".join(x for x, _ in cur)) > 12: out.append(cur); cur = []
    if cur: out.append(cur)
    res = []
    for k, ch in enumerate(out):
        s = ch[0][1] - 0.08; e = (out[k + 1][0][1] - 0.04) if k + 1 < len(out) else min(b, ch[-1][1] + 0.7)
        res.append([round(s - a, 2), round(e - a, 2), " ".join(x for x, _ in ch)])
    # gộp dòng quá ngắn (< 0,9 s) vào dòng trước
    merged = []
    for r in res:
        if merged and (r[1] - r[0] < 0.9) and len(merged[-1][2]) + len(r[2]) < 64:
            merged[-1][1] = r[1]; merged[-1][2] += " " + r[2]
        else: merged.append(r)
    return [[max(0, s), max(0.3, e), t] for s, e, t in merged]

def normd(w): return re.sub(r"[^\w']", "", unicodedata.normalize("NFC", w.lower()))
def kw_times(n, a, b, text):
    toks, tm = align(n, a, b, text); return [(normd(t), x - a) for t, x in zip(toks, tm)]

def SP(n, a, b, words, label, ch, **kw):
    """Pum nói tại chỗ. Tuỳ chọn: cuts=[(giây tính từ a, #clip, in, dài)] cảnh chèn giữ tiếng Pum;
    skip=[(giây nguồn từ, đến)] bỏ đoạn (lặp ý, lỡ lời); tighten=True rút các khoảng lặng > 0,6 s (cắt nhảy kiểu vlog)."""
    cuts = kw.pop("cuts", []) or []; skip = kw.pop("skip", []) or []; tighten = kw.pop("tighten", False)
    text = kw.pop("text", []); hide = kw.pop("hide_src", []) or []; extra = dict(kw)
    subs = subs_for(n, a, b, words); kws = kw_times(n, a, b, words)
    # các mảnh nguồn được giữ
    cutpts = [(x, y, 1) for x, y in skip]
    if tighten:
        W = [w for g in ASR.get(cid(n), []) for w in g["words"] if a <= w[0] <= b]
        for w0, w1 in zip(W, W[1:]):
            gap_s = w0[0] + max(0.25, min(0.9, w0[1] - w0[0])); gap_e = w1[0]
            if gap_e - gap_s > 0.6 and gap_e - w0[1] > 0.15: cutpts.append((gap_s + 0.2, gap_e - 0.12, 0))
    cutpts = sorted((max(a, x), min(b, y), f) for x, y, f in cutpts if y > x)
    # bỏ những chỗ rút lặng làm ra mảnh < 0,6 s (cắt nhảy lắt nhắt); chỗ bỏ (skip) luôn giữ
    keep = []; cur = a
    for x, y, f in cutpts:
        if not f and x - cur < 1.0 and cur > a: continue
        if not f and keep and not keep[-1][2] and x - keep[-1][1] < 1.0: continue
        keep.append((x, y, f)); cur = max(cur, y)
    while keep and not keep[-1][2] and b - keep[-1][1] < 1.0: keep.pop()  # mảnh cuối quá ngắn
    pieces = []; cur = a
    for x, y, f in keep:
        if x > cur + 0.05: pieces.append((cur, x))
        cur = max(cur, y)
    if b > cur + 0.05: pieces.append((cur, b))
    omap = []; o = 0.0
    for pa, pb in pieces: omap.append((pa, pb, o)); o += pb - pa
    total = o
    def to_out(src):  # giờ nguồn tuyệt đối -> giờ ra
        for pa, pb, oo in omap:
            if src < pb: return oo + max(0.0, src - pa)
        return total
    subs_o = []
    for s0, s1, tx in subs:
        o0, o1 = to_out(a + s0), to_out(a + s1)
        if o1 - o0 > 0.25: subs_o.append([round(o0, 2), round(o1, 2), tx])
    kws_o = [(w, to_out(a + x)) for w, x in kws]
    cx_ = {}
    for c in cuts:
        if len(c) > 4: cx_[(c[1], c[2])] = c[4]
    cuts_o = sorted((to_out(a + c[0]), c[1], c[2], c[3]) for c in cuts)
    # cảnh chèn bắt đầu/kết thúc sát chỗ cắt nhảy thì kéo trùng chỗ cắt, không để loé 0,3 s mặt Pum
    obs = [oo for _, _, oo in omap] + [total]
    snapped = []
    for c0, bn, bi, bd in cuts_o:
        c1 = c0 + bd; ex_ = cx_.get((bn, bi), {})
        p0 = max([x for x in obs if x <= c0 + 1e-6], default=0.0)
        if 0 < c0 - p0 < 1.2: bi -= c0 - p0; c0 = p0
        n1 = min([x for x in obs if x >= c1 - 1e-6], default=total)
        if 0 < n1 - c1 < 1.2: c1 = n1
        snapped.append((c0, bn, max(0.0, bi), c1 - c0, ex_))
    cuts_o = snapped
    # ranh giới: mảnh nguồn và cảnh chèn
    bounds = sorted(set([0.0, total] + [oo for _, _, oo in omap] + [c[0] for c in cuts_o] + [min(total, c[0] + c[3]) for c in cuts_o]))
    first = True
    for lo, hi in zip(bounds, bounds[1:]):
        if hi - lo < 0.04: continue
        pa, pb, oo = next(m for m in omap if m[2] <= lo + 1e-6 and lo < m[2] + (m[1] - m[0]) - 1e-6)
        src0 = pa + (lo - oo)
        ss = [[max(0, x - lo), min(hi - lo, y - lo), z] for x, y, z in subs_o if y > lo + 0.15 and x < hi - 0.15]
        kk = [(w, x - lo) for w, x in kws_o if lo <= x < hi]
        cut = next((c for c in cuts_o if c[0] <= lo + 1e-6 and lo < c[0] + c[3] - 1e-6), None)
        lab = label if first else label + (" (cảnh chèn)" if cut else " (tiếp)")
        if cut is None:
            sg = dict(id=None, label=lab, chapter=ch, clip=cid(n), **{"in": round(src0, 2), "out": round(src0 + hi - lo, 2)},
                      audio="src", voice="noi", say=words if first else "", subs=ss, _kw=kk)
        else:
            ci = cut[2] + (lo - cut[0])
            sg = dict(id=None, label=lab, chapter=ch, clip=cid(cut[1]), **{"in": round(ci, 2), "out": round(ci + hi - lo, 2)}, audio="mute",
                      voice="noi", say=words if first else "", subs=ss, _kw=kk, vo={"path": MEZ(n), "in": round(src0, 2), "out": round(src0 + hi - lo, 2), "at": 0, "vol": 1.0, "speech": True})
            if len(cut) > 4 and cut[4]: sg.update(cut[4])
        sg["fade"] = 0.012 if not first else 0.06
        # chữ kéo dài qua nhiều mảnh: mỗi mảnh một bản, đánh dấu nối (render bỏ hiệu ứng hiện/ẩn ở chỗ nối, nhìn liền mạch)
        sg["text"] = [dict(x, start=round(max(0.0, x["start"] - lo), 2), end=round(min(hi - lo, x["end"] - lo), 2), cont_in=x["start"] < lo - 1e-6, cont_out=x["end"] > hi + 1e-6 and hi < total - 1e-6)
                      for x in text if x["start"] < hi - 0.05 and x["end"] > lo + 0.05]
        if first: sg.update(extra)
        elif "crop" in extra and cut is None: sg["crop"] = extra["crop"]
        if cut is None and hide:  # che trên khung nguồn: giờ tính từ a (giờ nguồn), chia về từng mảnh
            r0 = src0 - a; hs = []
            for h in hide:
                h0, h1 = h["start"] - r0, h["end"] - r0
                if h1 > 0 and h0 < hi - lo: hs.append({"box": h["box"], "start": round(max(0.0, h0), 2), "end": round(min(hi - lo, h1), 2)})
            if hs: sg["hide_src"] = hs
        if "vol" in extra:  # tăng lời cho cả các mảnh và cảnh chèn mang tiếng Pum
            if cut is None: sg["vol"] = extra["vol"]
            else: sg["vo"]["vol"] = extra["vol"]; sg.pop("vol", None)
        first = False
        segs.append(sg)

def SPX(n, a, b, words, label, ch, cuts, **kw):
    return SP(n, a, b, words, label, ch, cuts=cuts, **kw)

def BR(n, a, b, label, ch, audio="amb", **kw):
    sg = dict(id=kw.pop("id", None), label=label, chapter=ch, clip=cid(n), **{"in": a, "out": b}, audio=audio, voice="", subs=[])
    sg.update(kw); segs.append(sg); return sg

def vo_subs(v, total, maxc=42):
    """phụ đề lồng tiếng: khớp câu đã sửa với mốc chữ của bản thu (giọng Pum) hoặc rải đều (giọng tạm)"""
    toks = v["text"].split(); lead = 0.25
    if v.get("words"):
        W = v["words"]; tn = [norm(t) for t in toks]; wn = [norm(w[2]) for w in W]; tm = [None] * len(toks)
        for blk in difflib.SequenceMatcher(None, tn, wn, autojunk=False).get_matching_blocks():
            for k in range(blk.size): tm[blk.a + k] = W[blk.b + k][0] + lead
        known = [(i, t) for i, t in enumerate(tm) if t is not None] or [(0, lead)]
        for i in range(len(toks)):
            if tm[i] is None:
                prv = max([k for k in known if k[0] < i], default=(-1, lead), key=lambda k: k[0]); nxt = min([k for k in known if k[0] > i], default=(len(toks), v["dur"] + lead), key=lambda k: k[0])
                tm[i] = prv[1] + (nxt[1] - prv[1]) * (i - prv[0]) / max(1, nxt[0] - prv[0])
    else:
        L = sum(len(t) for t in toks); tm = []; x = lead
        for t in toks: tm.append(x); x += (min(total, v["dur"] + lead) - lead) * len(t) / L
    out = []; cur = []
    for t, x in zip(toks, tm):
        if cur and len(" ".join(c for c, _ in cur + [(t, 0)])) > maxc and not (re.search(r"[.!?,]$", t) and len(" ".join(c for c, _ in cur + [(t, 0)])) <= maxc + 8): out.append(cur); cur = []
        cur.append((t, x))
        if re.search(r"[.!?,]$", t) and len(" ".join(c for c, _ in cur)) > 22: out.append(cur); cur = []
    if cur: out.append(cur)
    return [[c[0][1] - 0.05, (out[k + 1][0][1] - 0.04) if k + 1 < len(out) else min(total, v["dur"] + lead + 0.3), " ".join(w for w, _ in c)] for k, c in enumerate(out)]

def VOG(key, shots, ch, label, note=""):
    v = VO[key]; total = sum(b - a for _, a, b in shots); acc = 0.0
    subs_all = vo_subs(v, total)
    for k, (n, a, b) in enumerate(shots):
        d = b - a
        sg = dict(id=key if k == 0 else f"{key}_{k}", label=label if k == 0 else label + " (tiếp)", chapter=ch, clip=cid(n),
                  **{"in": a, "out": b}, audio="low", voice="vo", subs=[[round(s - acc, 2), round(e - acc, 2), t] for s, e, t in subs_all if e > acc and s < acc + d])
        sg["subs"] = [[max(0, s), min(d, e), t] for s, e, t in sg["subs"] if min(d, e) - max(0, s) > 0.35]
        if v["dur"] + 0.25 > acc:
            sg["vo"] = {"path": v["path"], "in": round(acc, 2), "out": round(min(v["dur"], acc + d), 2), "at": 0.25 if k == 0 else 0, "vol": 1.0}
            if k: sg["vo"]["in"] = round(acc - 0.25, 2); sg["vo"]["out"] = round(min(v["dur"], acc - 0.25 + d), 2)
        if k == 0:
            sg["voReq"] = {"text": v["text"], "sec": round(v["dur"]), "temp": not v.get("pum"), "done": bool(v.get("pum")), "note": note}; sg["say"] = v["text"]
        else: sg["say"] = ""
        segs.append(sg); acc += d

T = lambda style, text, s, e: {"style": style, "text": text, "start": s, "end": e}

# ================= MỞ TẬP =================
C = "Mở tập"
SP(168, 2.3, 11.3, "Thơm quá mọi người ơi! Ơ, nó đắng!", "Teaser", C, skip=[(3.55, 9.85)], text=[T("tape", "Hôm nay Pum thử cà phê…", 0.1, 2.6)])
SP(61, 3.9, 6.5, "Ai cũng biết Pum là người Buôn Ma Thuột rồi đúng không?", "Hook", C, text=[T("label", "Đi đâu thử đó", 0.2, 2.5)])
SP(63, 0.0, 12.75, "Đáng lẽ hôm nay 5, 6 giờ là em phải dậy để quay vlog một ngày của em ở Buôn Ma Thuột, người con của Buôn Ma Thuột sẽ như thế nào. Nhưng mà hôm nay em đã dậy trễ rồi mọi người ơi. Bây giờ là 9 giờ rồi.",
   "Dậy trễ", C, text=[T("tape", "Một ngày ở Buôn Ma Thuột", 3.4, 8.4), T("tape", "Dậy trễ mất rồi!", 9.0, 12.5)])
SP("BIG", 548.2, 555.55, "Thật ra em là người Buôn Mê nhưng mà không thích uống cà phê cho lắm, tại vì nó khá là đắng.",
   "Thú nhận", C, cuts=[(0.0, "BIG", 132.5, 4.0), (4.0, "BIG", 450.5, 3.4)], text=[T("tape", "Người Buôn Mê mà không thích cà phê?!", 0.4, 5.0)])
VOG("lt_xemtruoc", [(202, 10.0, 13.2), (105, 60.0, 63.0), (46, 1.0, 3.6), (48, 4.5, 7.0), (20, 6.5, 9.1), (91, 7.0, 9.6), (197, 5.0, 8.0)], C, "Xem trước cả ngày",
    "Đã dùng giọng Pum thu ngày 20/11.")
segs[-7]["trans"] = "bang_hong"
BR(54, 2.0, 5.5, "Tượng đài", C, text=[T("postcard", "Tượng đài Buôn Ma Thuột · 9 giờ sáng", 0.2, 3.3)])

# ================= CHƯƠNG 1 · Bánh canh =================
C = "Chương 1 · Bánh canh"
SP(50, 0.0, 22.3, "Thường thường buổi sáng ở Buôn Ma Thuột thì Pum rất là thích ăn món này. Mỗi lần ở Sài Gòn là luôn luôn thèm thèm thèm, để về Buôn Ma Thuột ăn sáng món này. Mọi người có tò mò không? Thì theo Pum nhé, Pum chỉ dẫn mọi người đi ăn quán mà dân local Buôn Ma Thuột rất là thích.",
   "Món Pum thèm", C, trans="bang_hong", cuts=[(14.4, 47, 0.3, 3.4), (17.8, 46, 4.2, 4.5)], text=[T("label", "Món Pum thèm mỗi lần xa nhà", 6.4, 9.8)])
BR(48, 0.5, 3.3, "Tô bánh canh", C, text=[dict(T("postcard", "Bánh canh · buổi sáng", 0.1, 2.7), pos="top")])
SP(149, 0.6, 16.8, "Ở trong tô này sẽ có gà xé, má heo và sườn. Mà hôm nay dậy trễ quá nên hết sườn rồi nha mọi người, chỉ còn gà xé với lại má heo thôi.",
   "Hết sườn vì dậy trễ", C, cuts=[(3.0, 47, 4.0, 3.0)], text=[T("label", "Dậy trễ = hết sườn", 9.5, 13.5)])
SP(150, 0.5, 10.1, "Thường thường là sẽ có 2 cách ăn cho mọi người: ăn chung, còn đây là ăn riêng, mọi người sẽ để riêng đồ ăn ra.", "Hai cách ăn", C)
BR(45, 2.0, 6.0, "Pum ăn", C, audio="src", crop=[0.42, 0.18, 0.58, 0.58])
BR(46, 8.5, 11.0, "Cận tô", C)
SP(38, 0.3, 12.45, "Rồi mọi người ơi, đây là địa chỉ nha. Mọi người lưu ý là chủ nhật nghỉ bán, nên chủ nhật mọi người đừng ghé nha. Chủ nhật mọi người ghé, nghỉ bán, mọi người lại trách Pum đấy nhờ.",
   "Địa chỉ", C, cuts=[(1.0, 34, 1.0, 3.0)], text=[T("postcard", "Bánh canh Bà Già · 52/11 Hồ Tùng Mậu", 1.2, 4.0), T("label", "Chủ nhật nghỉ bán", 4.6, 9.0)])
SP(42, 0.6, 6.35, "Nóng quá mọi người ơi. Thôi mọi người cùng theo chân em đi qua địa điểm thứ 2 nhé.", "Đi tiếp", C)

# ================= CHƯƠNG 2 · Nhà dài giữa phố =================
C = "Chương 2 · Nhà dài giữa phố"
BR(29, 3.0, 6.5, "Biển buôn", C, trans="bang_hong", text=[T("postcard", "Buôn Akô Dhông · cuối đường Trần Nhật Duật", 0.2, 3.3)])
SP(145, 0.1, 22.8, "Địa điểm tiếp theo mà Pum muốn cho mọi người biết đó là một cái buôn ở cuối đường Trần Nhật Duật. Ngay ở trong Buôn Ma Thuột vẫn còn một cái buôn, một con đường vẫn còn giữ lại nét nhà sàn, nhà dài. Bây giờ theo chân Pum đi vô trong nha.",
   "Buôn giữa phố", C, cuts=[(6.6, 141, 8.0, 4.0)], hide_src=[{"box": [0.70, 0.47, 0.12, 0.14], "start": 13.0, "end": 14.8}])  # biển xe máy dưới hiên
BR(20, 2.0, 6.5, "Sân buôn", C)
SP(18, 7.8, 10.5, "Đây là nhà dài nha mọi người.", "Vô nhà dài", C)
SP(21, 34.3, 50.8, "Thường thường là ở nhà sàn là sẽ có 2 cái cầu thang để đi lên. Cầu thang mà có 2 cái này là dành cho người phụ nữ để đi lên nha mọi người. Còn cầu thang bên này là sẽ dành cho đàn ông.",
   "Hai cầu thang", C, tighten=True, text=[T("label", "Cầu thang cho phụ nữ · cho đàn ông", 8.0, 13.0)])
VOG("lt_nhadai", [(12, 0.0, 4.5), (17, 2.0, 5.5), (8, 4.0, 8.5), (144, 3.0, 6.0), (11, 6.0, 8.6)], C, "Vì sao nhà dài",
    "Đã dùng giọng Pum thu ngày 20/11.")
SP(13, 0.3, 13.5, "Thường thường mọi người nghĩ là nhà sàn họ sẽ làm bằng gỗ, nhưng mà không nha mọi người, người ta sẽ làm bằng tre nứa kết lại với nhau.",
   "Sàn tre nứa", C, vol=6.0, text=[T("label", "Sàn nhà dài: tre nứa", 6.6, 11.0)])
SP(177, 3.0, 14.7, "Đây là phía sau của nhà dài nha mọi người. Ở đằng sau này thì có một bộ bàn ghế. Không biết là bộ bàn ghế này ngày xưa nó có không, hay là bây giờ mọi người decor nó như vậy thôi.",
   "Phía sau nhà", C, vol=6.0)
BR(142, 9.0, 13.0, "Pum ở cửa", C)
SP(5, 0.4, 19.6, "Một người Buôn Mê nhưng mà lại không thích uống cà phê. Nhưng mà ngồi nhà sàn thì rất là Buôn Mê rồi mọi người ạ. Ngồi ở nhà sàn, thay vì cà phê, em sẽ uống ca cao. Mời mọi người nha.",
   "Không thích cà phê", C, cuts=[(12.0, 175, 4.0, 3.0)])
SP(174, 49.6, 58.0, "Nhìn Pum có giống người Nhật Bản không mọi người? Hồi nãy mà bước ra đây nè, ai cũng tưởng Pum là người Nhật Bản hết, họ còn nói tiếng Nhật Bản với Pum nữa.",
   "Tưởng người Nhật", C, text=[T("label", "Pum: người Nhật?!", 4.2, 7.6)])

# ================= CHƯƠNG 3 · Cơm đồng bào =================
C = "Chương 3 · Cơm đồng bào"
SP(101, 0.6, 19.5, "Ngồi một xíu là đến trưa rồi, mà thường á, trưa trưa Pum sẽ ăn cơm ở nhà. Nhưng mà hôm nay đã ở trong buôn này rồi thì Pum sẽ đi ăn cơm đồng bào, để cho mọi người biết cơm đồng bào ở Buôn Ma Thuột sẽ như thế nào nha. Let's go!",
   "Đi ăn trưa", C, cuts=[(10.0, 97, 4.0, 3.5)], trans="bang_hong", tighten=True)
BR(91, 3.0, 6.0, "Cận mâm", C, text=[T("postcard", "Cơm đồng bào · buổi trưa", 0.2, 2.9)])
SP(86, 0.1, 19.2, "Mâm ở đây thì thường thường sẽ theo ngày, không có cố định. Hôm nay thì mâm ăn có 6 món: đồ xào, đồ chua, đồ khô, thịt ba chỉ, canh.",
   "Mâm 6 món", C, cuts=[(9.0, 93, 3.0, 3.0, {"crop": [0.0, 0.2, 0.8, 0.8]}), (14.0, 92, 2.0, 3.0)], crop=[0.0, 0.0, 0.86, 0.86])
SP(85, 204.3, 209.75, "Đây là măng. Đây là mít.", "Từng món", C, cuts=[(2.0, 88, 2.0, 3.45, {"crop": [0.0, 0.1, 0.85, 0.85]})], crop=[0.03, 0.05, 0.7, 0.7])
SP(85, 242.4, 252.3, "Còn đây là thịt ba chỉ. Thường thường là mọi người ướp xong rồi mới nướng, còn đây là người ta nướng xong rồi mới trộn theo kiểu người đồng bào.",
   "Thịt ba chỉ nướng", C, text=[T("label", "Nướng xong rồi mới trộn", 3.2, 6.4)], crop=[0.03, 0.05, 0.7, 0.7])
BR(85, 341.6, 345.0, "Cay", C, audio="src", voice="noi", subs=[[0.15, 3.35, "Đồ ăn đồng bào thì sẽ rất là cay. Cay!"]], crop=[0.06, 0.04, 0.6, 0.6])

# ================= CHƯƠNG 4 · Lên farm cà phê =================
C = "Chương 4 · Lên farm cà phê"
SP(165, 0.6, 21.15, "Ăn xong rồi thì bây giờ Pum sẽ đi uống, không phải đi uống cà phê! Ăn xong rồi thì bây giờ Pum sẽ đi qua địa điểm tiếp theo, địa điểm tiếp theo sẽ cho mọi người biết để làm ra được một ly cà phê, những giọt cà phê đó thì sẽ trải qua những công đoạn như thế nào. Let's go!",
   "Đi tiếp lên farm", C, trans="bang_hong", tighten=True, text=[T("label", "Lỡ lời rồi!", 4.0, 6.2)],
   cuts=[(8.3, 82, 17.5, 3.2), (15.5, "BIG", 1111.5, 3.0)],  # 20 s nói liền: chèn cảnh đường phố và hạt cà phê đang phơi (giữ tiếng Pum)
   hide_src=[{"box": [0.0, 0.55, 0.07, 0.13], "start": 19.0, "end": 20.6}]  # biển số xe bán tải sát mép trái 19,2 s → hết đoạn (máy dò bỏ sót)
   + [{'box': [0.606, 0.175, 0.1, 0.16], 'start': 6.2, 'end': 6.9}, {'box': [0.65, 0.19, 0.1, 0.16], 'start': 6.2, 'end': 6.9}, {'box': [0.58, 0.17, 0.1, 0.16], 'start': 6.7, 'end': 7.4}, {'box': [0.64, 0.17, 0.1, 0.16], 'start': 6.7, 'end': 7.4}, {'box': [0.586, 0.15, 0.1, 0.16], 'start': 7.2, 'end': 7.9}, {'box': [0.65, 0.15, 0.1, 0.16], 'start': 7.2, 'end': 7.9}, {'box': [0.6, 0.16, 0.1, 0.16], 'start': 7.7, 'end': 8.4}, {'box': [0.66, 0.16, 0.1, 0.16], 'start': 7.7, 'end': 8.4}, {'box': [0.605, 0.13, 0.1, 0.16], 'start': 8.2, 'end': 8.9}, {'box': [0.69, 0.18, 0.1, 0.16], 'start': 8.2, 'end': 8.9}, {'box': [0.625, 0.14, 0.1, 0.16], 'start': 8.7, 'end': 9.4}, {'box': [0.74, 0.16, 0.1, 0.16], 'start': 8.7, 'end': 9.4}, {'box': [0.65, 0.155, 0.1, 0.16], 'start': 9.2, 'end': 9.9}, {'box': [0.7, 0.17, 0.1, 0.16], 'start': 9.2, 'end': 9.9}, {'box': [0.75, 0.14, 0.1, 0.16], 'start': 9.7, 'end': 10.4}, {'box': [0.67, 0.25, 0.1, 0.16], 'start': 9.7, 'end': 10.4}, {'box': [0.695, 0.23, 0.1, 0.16], 'start': 10.2, 'end': 10.9}, {'box': [0.84, 0.14, 0.1, 0.16], 'start': 10.2, 'end': 10.9}, {'box': [0.71, 0.24, 0.1, 0.16], 'start': 10.7, 'end': 11.4}, {'box': [0.82, 0.14, 0.1, 0.16], 'start': 10.7, 'end': 11.4}, {'box': [0.72, 0.25, 0.1, 0.16], 'start': 11.2, 'end': 12.0}, {'box': [0.81, 0.16, 0.1, 0.16], 'start': 11.2, 'end': 12.0}])  # mặt người lạ ở cầu thang nhà gỗ (máy dò che không đều)
SP(161, 0.4, 30.0, "Từ buôn Akô Dhông qua địa điểm tiếp theo thì mất khoảng 20 đến 30 phút đi xe, qua trang trại cà phê đấy. Pum cũng biết từ lâu rồi, nhưng mà hình như dạo gần đây thì mới cho khách đến để biết được quy trình trồng trọt, sản xuất ra được những thành phẩm. Mọi người cùng theo chân Pum để đi nhá.",
   "Đường lên farm", C, cuts=[(7.5, 82, 30.0, 4.0), (15.5, 158, 2.0, 4.0)], tighten=True, text=[T("label", "20–30 phút đi xe", 1.0, 5.0)])
SP(71, 0.1, 11.8, "Tới trang trại cà phê rồi, trang trại cà phê này gần hồ Ea Kao luôn, nên là chắc chiều nay Pum sẽ đi ra ngoài này ngắm hoàng hôn luôn. Mắc gì cái tóc vậy trời.",
   "Gần hồ Ea Kao", C, tighten=True)
SP(156, 3.0, 6.6, "Đã tới Aeroco Coffee rồi nha mọi người.", "Tới farm", C, text=[T("postcard", "Trang trại cà phê · chiều", 0.2, 3.2)])
SP(189, 138.0, 143.6, "Ủa, mùa này có phải mùa cà phê không anh? Đúng rồi, mùa này là bắt đầu mùa cà phê chín, mọi người bắt đầu đi thu hoạch á.",
   "Mùa cà phê chín", C, cuts=[(0.0, 202, 14.0, 5.6)], text=[T("label", "Anh hướng dẫn ở farm", 1.8, 5.0)])
SP("BIG", 0.4, 12.9, "Đó, còn bên em thì sẽ hái rất là nhiều lần luôn, tại vì mình sẽ chỉ hái những quả chín đỏ trên cây thôi, cho nên làm về đặc sản nó rất là kỳ công, mất rất là nhiều công sức vào trong công đoạn đấy.",
   "Chỉ hái quả chín", C, cuts=[(0.0, "BIG", 440.0, 3.6), (3.6, "BIG", 165.0, 5.0), (8.6, "BIG", 470.0, 4.4)], text=[T("label", "Chỉ hái quả chín đỏ", 4.4, 8.5)])
SP("BIG", 326.3, 330.3, "Nhìn nó tưởng tiêu không? Ủa? Là cây tiêu không? Đúng rồi, cây tiêu á.", "Tưởng cây tiêu", C, text=[T("label", "Ủa, cây tiêu?!", 1.4, 3.9)])
SP(189, 44.75, 51.6, "Robusta thì nó sẽ thiên về đậm đắng hơn, còn Arabica thì nó sẽ có vị chua, nó sẽ thanh hơn.",
   "Robusta hay Arabica", C, cuts=[(0.0, "BIG", 120.0, 3.4), (3.4, "BIG", 361.5, 3.45)], text=[T("label", "Robusta: đậm đắng · Arabica: chua thanh", 0.3, 6.6)])
SP("BIG", 387.4, 392.0, "Cái lá nó giống lá chè thiệt. Đúng rồi, nên là người ta mới gọi là cà phê chè.", "Lá giống lá chè", C, text=[T("label", "Lá giống lá chè nên gọi cà phê chè", 1.8, 4.5)])
SP("BIG", 610.0, 616.3, "Khi mà mình trồng á thì sẽ mất tầm khoảng 3 năm từ lúc trồng cho đến lúc mà nó ra quả.", "3 năm mới ra quả", C,
   text=[T("label", "Trồng 3 năm mới ra quả", 1.0, 5.0)])
SP("BIG", 291.4, 307.05, "Giống như ở ngoài, khi người ta hái về thì người ta sẽ phơi tràn lan dưới đất hoặc dưới nền xi măng. Còn bên em thì sẽ phơi trên sàn để cho nó đảm bảo vệ sinh hơn, với lại nó cũng không có bị ảnh hưởng xấu đến hạt cà phê.",
   "Phơi trên sàn", C, vol=1.8, cuts=[(0.0, "BIG", 311.5, 4.6)], text=[T("label", "Phơi trên sàn cho sạch hạt", 7.4, 11.4)])
VOG("lt_caphe", [("BIG", 985.0, 988.2), ("BIG", 838.0, 841.0), ("BIG", 1108.0, 1111.0), (111, 5.0, 8.0), (111, 22.0, 25.0), (182, 12.0, 15.0)], C, "Quả cà phê đi đâu tiếp",
    "Đã dùng giọng Pum thu ngày 20/11.")
SP("BIG", 1126.0, 1160.4, "Khi mà mình phơi khô xong á, thì phơi khô xong và mình sàng mấy cái này ra, mình làm sạch ra, thì mình sẽ cho nó vào, tại vì cà phê nó cũng cần nghỉ ngơi để cho nó đạt cái độ chất lượng tốt nhất, để nó ngon hơn á. Thì mình sẽ cho nó ngủ trong phòng máy lạnh, 24 trên 24 luôn. Nó sẽ được nghỉ ngơi tầm khoảng 4 đến 6 tháng, là 6 đến 8 tháng. Lúc nãy mình mới đem ra để mình rang và mình làm cà phê được. Chứ không phải là mình phơi xong mà mình làm được luôn.",
   "Hạt cũng cần nghỉ", C, cuts=[(14.3, "BIG", 1016.5, 3.5), (26.9, 108, 2.0, 3.5)], tighten=True, text=[T("label", "Hạt cà phê cũng cần nghỉ", 9.0, 13.0)])
BR(109, 3.0, 7.0, "Rang hạt", C, audio="low")
SP(105, 0.2, 5.85, "Đầu tiên mình sẽ rót 30 ml nước và mình sẽ ủ cho 30 giây.", "Tự pha cà phê", C)
BR(182, 4.0, 8.0, "Rót nước", C, audio="mute")
SP(105, 153.8, 157.0, "Trời ơi, đẹp lắm, xuất sắc!", "Pha xong", C, text=[T("tape", "Xuất sắc!", 1.8, 3.2)])
SP(168, 2.2, 11.6, "Thơm quá mọi người ơi, em uống thử nhé. Ơ, nó đắng!", "Nếm thử", C, text=[dict(T("tape", "Thơm, nhưng vẫn đắng!", 7.9, 9.4), pos="tr")])
# (bỏ đoạn "Vị khói": Pum và anh ở farm tranh luận qua lại, anh Phúc không muốn đưa vào)

# ================= CHƯƠNG 5 · Đi tìm hoàng hôn =================
C = "Chương 5 · Đi tìm hoàng hôn"
SP(207, 1.1, 13.95, "Mình đã tham quan trang trại xong, giờ mình sẽ đi ngắm hoàng hôn. Mình thấy trời ngon lắm, trời sắp xuống rồi, giờ mình sẽ kiếm một chỗ hợp lý để mình ngắm hoàng hôn nha.",
   "Đi ngắm hoàng hôn", C, trans="bang_hong", cuts=[(6.4, 206, 2.0, 6.6)])  # cảnh đường tới hết câu: bãi xe phía sau có biển số
SP(132, 0.2, 19.4, "Mình là một người rất rất rất thích ngắm hoàng hôn luôn. Nên là mình rất là mong, háo hức là mình có thể được nhìn thấy hoàng hôn. Nên là mong là mình tới đó là vừa thấy hồ mà vừa thấy hoàng hôn luôn. Chứ không mình sẽ rất là buồn luôn đó.",
   "Mê hoàng hôn", C)
SP(132, 25.0, 43.0, "Ngày xưa là sẽ có một cái con đường song song với lại cái con đường này. Nhưng mà đóng cửa rồi. Giờ không còn cho đi vô để mà ngắm hoàng hôn nữa. Cả tuổi thơ của tui!",
   "Con đường tuổi thơ", C, cuts=[(6.0, 204, 2.0, 4.0)], text=[T("tape", "Cả tuổi thơ của tui!", 15.4, 18.0)])
SP(205, 1.3, 22.95, "Cùng mình đi vô một cái chỗ ngắm hoàng hôn. Mình tìm ở trên Google Maps thôi. Nên là mình đi theo Google Maps chạy vô đây.",
   "Theo Google Maps", C, cuts=[(6.2, 130, 22.0, 3.0)], skip=[(8.7, 19.1)])
SP(205, 23.8, 30.7, "Ủa, ở đây có cà phê! Đẹp lắm mọi người. Nó chín hết rồi nè.", "Cà phê ven đường", C, cuts=[(3.6, "BIG", 457.0, 3.3)])
SP(172, 1.4, 26.9, "Buồn quá mọi người ơi, tưởng là sẽ phát hiện ra được một con đường đi ngắm hoàng hôn đẹp, nhưng mà thất bại rồi. Bây giờ em phải chạy ra lại cái hồ Ea Kao để ngắm hoàng hôn, mong là hoàng hôn chưa lặn, để em có thể đón hoàng hôn. Chứ giờ mà chạy ra hồ Ea Kao mà nó lặn rồi chắc khóc to luôn á mọi người ạ.",
   "Thất bại", C, cuts=[(9.6, 171, 8.0, 4.0), (18.0, 200, 6.0, 3.3)], tighten=True, text=[T("label", "Kế hoạch B: hồ Ea Kao", 11.0, 15.0)])
BR(124, 2.0, 8.0, "Kịp rồi", C, text=[T("postcard", "Hồ Ea Kao · hoàng hôn", 0.4, 3.6)])
SP(195, 1.4, 12.9, "Đẹp quá! Bầu trời hôm nay cũng đẹp đẹp đẹp đẹp.", "Đẹp đẹp đẹp", C, vol=1.8, skip=[(2.3, 10.55)], text=[T("tape", "Kịp rồi!", 0.2, 2.6)])
SP(125, 0.6, 2.6, "Mọi người nhìn cái đó giống cái gì?", "Mây giống gì", C, vol=1.8)
SP(194, 18.98, 36.1, "Nhìn bầu trời này mình cứ muốn cầm máy lên quay hoài luôn á mọi người ạ. Nhưng mà nó đẹp, tự nhiên xung quanh đây là màu cam, xong rồi có một cái đám mây nhìn giống con khủng long. Trông nó yêu nhờ.",
   "Mây khủng long", C, vol=1.8, cuts=[(6.3, 126, 1.0, 4.4)], tighten=True, text=[T("label", "Mây khủng long!", 10.4, 13.8)])
BR(197, 10.0, 15.0, "Pum giữa gió", C)
SP(196, 1.8, 4.9, "Đây là mặt trời lặn rồi, nhưng mà nhìn bầu trời nó cũng rất là đẹp.", "Vẫn đẹp", C, vol=1.8)
SP(128, 0.8, 27.6, "Thôi thì hôm nay kết thúc ở đây thôi. Tuy là nó không có đẹp như là mình mong muốn, nhưng mà nó cũng là cơ hội để mình có thể có một vlog hoàn hảo hơn. Lần sau mình sẽ cố gắng tìm một cái chỗ để ngắm hoàng hôn đẹp hơn. Hôm nay cái kết không như mình mong muốn, nhưng mà hậu của hoàng hôn nó vẫn đẹp mọi người ạ.",
   "Nhìn lại", C, vol=1.8, cuts=[(12.8, 198, 2.0, 4.1), (19.4, 199, 3.0, 3.6)], skip=[(5.0, 13.6)])

# ================= CHƯƠNG 6 · Tối · Mì hoành thánh =================
C = "Chương 6 · Tối · Mì hoành thánh"
SP(193, 0.3, 14.3, "Định là sẽ kết thúc video rồi nhưng mà mình đói bụng quá mọi người ơi, nên là mình sẽ chỉ cho mọi người một quán mà ở đâu cũng có. Nhưng mà đối với Pum, chỗ này là ngon nhất lòng Pum. Mọi người đoán xem là món gì nhá.",
   "Đói bụng", C, trans="bang_hong")
SP(121, 1.2, 16.2, "Mọi người đoán được ở đâu chưa? Mọi người đoán được là món gì chưa? Tới rồi nè, mì hoành thánh nha mọi người. Mì Hường, hoành thánh ở đây là số dách.",
   "Đoán món", C, cuts=[(8.7, 122, 2.0, 3.2)], text=[T("postcard", "Mì Hường · mì hoành thánh", 9.6, 13.4)])
SP(118, 6.8, 11.2, "Hoành thánh chiên, rau, chấm với sốt.", "Hoành thánh chiên", C)
BR(191, 30.0, 35.0, "Pum ăn mì", C, audio="src")
SP(191, 74.6, 76.5, "Nó sụp sụp sụp.", "Sụp sụp", C)
SP(190, 2.9, 5.05, "Bye bye mọi người, giờ Pum ăn ở đây,", "Tạm biệt", C)
SP(190, 15.5, 19.0, "hẹn mọi người ở vlog tiếp theo của Pum nha. See you!", "Tạm biệt (tiếp)", C)
BR(199, 6.6, 12.6, "Câu hỏi cuối", "Cuối tập", audio="mute", text=[T("question", "Bạn thuộc phe cà phê hay phe ca cao như Pum?", 0.4, 6.0)])

# ================= hiệu ứng theo nội dung: doodle + âm =================
RULES = [  # (từ khoá có dấu, ghép đôi được; doodle; sfx)
    (["nóng"], "sun", "boing"), (["ngon", "thơm", "xuấtsắc", "đẹplắm", "đẹpquá"], "sparkle", "sparkle"),
    (["càphê"], "coffee", "pop"), (["đắng", "khét", "khói"], "swirl", "boing"), (["cay"], "chili", "boing"),
    (["hoànghôn", "mặttrời", "lặn"], "sunset", "slide"), (["đámmây", "khủnglong"], "cloud", "puff"),
    (["buồn", "khóc", "thấtbại"], "drop", "drip"), (["let'sgo", "theochân"], "arrow", "whoosh"),
    (["địachỉ", "googlemaps"], "pin", "pop"), (["bánhcanh", "cơmđồng", "hoànhthánh"], "bowl", "pop"),
    (["dậytrễ", "9giờ"], "clock", "ticktock"), (["nhậtbản"], "star", "pop"), (["cacao"], "heart", "pop"),
    (["chínđỏ", "chínhết"], "heart", "pop"), (["sụp"], "steam", "pop"), (["seeyou", "byebye"], "heart", "sparkle"),
]
def kw_hit(tok, keys): return any(tok == k for k in keys)

for i, s in enumerate(segs):
    if not s.get("id"): s["id"] = f"s{i+1:02d}"
t = 0.0
for s in segs:
    s["_t"] = round(t, 2); t += s["out"] - s["in"]
total = t

CH_LABEL = {"Chương 6 · Tối · Mì hoành thánh": "Chương 6 · Tối · Món gì đây?"}  # không lộ đáp án trò đoán món
seen_ch = set()
for s in segs:
    ch = s["chapter"]
    if ch in seen_ch: continue
    seen_ch.add(ch)
    if not ch.startswith("Chương"): continue
    if any(tx["start"] < 2.8 and (tx["style"] in ("label", "tape") or tx.get("pos") == "top") for tx in s.get("text", [])): continue
    pass  # 20/11: bỏ băng "Chương n" trên hình (anh Phúc: làm video không tự nhiên)
doodles_last = -99; sfx = []; sfx_last = -99; decor_used = []
DOODLE_OVR = {"Con đường tuổi thơ": {"sunset": "drop"}, "Thất bại": {"sunset": "clock"}}
THEME = {"Mở tập": ["heart", "sparkle", "note"], "Chương 1 · Bánh canh": ["flower", "leaf", "heart"],
         "Chương 2 · Nhà dài giữa phố": ["leaf", "daisy", "flower"], "Chương 3 · Cơm đồng bào": ["leaf", "clover", "tulip"],
         "Chương 4 · Lên farm cà phê": ["leaf", "clover", "butterfly"], "Chương 5 · Đi tìm hoàng hôn": ["cloud", "butterfly", "note"],
         "Chương 6 · Tối · Mì hoành thánh": ["note", "heart", "rainbow"]}
DECOR = ["flower", "tulip", "butterfly", "leaf", "note", "daisy", "sparkle", "clover", "rainbow", "heart"]
pair = {}  # ghép từ đôi: "ca phe", "hoang hon", "google maps"...
for s in segs:
    kws = s.pop("_kw", [])
    s.setdefault("doodles", [])
    toks = [(a + b, x) for (a, x), (b, _) in zip(kws, kws[1:])] + kws
    for tok, x in sorted(toks, key=lambda z: z[1]):
        T0 = s["_t"] + x
        for keys, dk, fx in RULES:
            if kw_hit(tok, keys):
                dk = DOODLE_OVR.get(re.sub(r" \((tiếp|cảnh chèn)\)$", "", s["label"]), {}).get(dk, dk)
                if any(dd["kind"] == dk for dd in s["doodles"]): break
                if T0 - doodles_last >= 3.2 and x + 1.6 <= s["out"] - s["in"]:
                    if sum(1 for q in segs for dd in q.get("doodles", []) if dd["kind"] == dk) >= 4:
                        dk = {"coffee": "leaf", "sun": "sparkle", "bowl": "heart", "swirl": "drop"}.get(dk, dk)
                        if sum(1 for q in segs for dd in q.get("doodles", []) if dd["kind"] == dk) >= 4: break  # đủ rồi: không thay bằng hình ngẫu nhiên
                    s["doodles"].append({"kind": dk, "start": round(max(0, x - 0.05), 2), "end": round(min(s["out"] - s["in"], x + (3.2 if dk in ("sunset", "clock", "drop") else 2.4)), 2)}); doodles_last = T0
                    if T0 - sfx_last >= 2.5: sfx.append({"name": fx, "at": round(T0, 2), "vol": 0.42}); sfx_last = T0
                break
    # doodle trang trí (hoa lá, bướm, nốt nhạc...) cho cảnh không có doodle theo lời, giữ nhịp vui đều tay
    d_ = s["out"] - s["in"]
    pool = THEME.get(s["chapter"], [])
    if pool and not s["label"].startswith(("Thất bại", "Mê hoàng hôn", "Con đường tuổi thơ")) and not s["doodles"] and d_ >= 2.4 and s["_t"] - doodles_last >= 4.5 and s.get("voice") != "noi" and not s.get("nodecor"):
        kind = pool[len(decor_used) % len(pool)]; decor_used.append(kind)
        at = 0.35
        s["doodles"].append({"kind": kind, "start": round(at, 2), "end": round(min(d_ - 0.2, at + 2.6), 2), "size": 0.18}); doodles_last = s["_t"] + at
        if len(decor_used) % 2 == 0 and all(abs(s["_t"] + at - f["at"]) > 1.0 for f in sfx): sfx.append({"name": "flutter" if kind == "butterfly" else "pop", "at": round(s["_t"] + at, 2), "vol": 0.3})
    # tiếng theo chữ trên hình
    for tx in s.get("text", []):
        T0 = s["_t"] + tx["start"]
        nm = {"tape": "swoosh", "label": "pop", "postcard": "click", "question": "sparkle", "price": "ding"}.get(tx["style"], "pop")
        if all(abs(T0 - f["at"]) > 0.6 for f in sfx): sfx.append({"name": nm, "at": round(T0 + 0.05, 2), "vol": 0.45})
    if s.get("trans"):
        sfx.append({"name": "whoosh", "at": round(max(0, s["_t"] - 0.25), 2), "vol": 0.35})
sfx.sort(key=lambda f: f["at"])

# ================= nhạc =================
MUS = {"Mở tập": "cheery_monday", "Chương 1 · Bánh canh": "daily_beetle", "Chương 2 · Nhà dài giữa phố": "dream_culture",
       "Chương 3 · Cơm đồng bào": "bossa_antigua", "Chương 4 · Lên farm cà phê": "life_of_riley", "Chương 5 · Đi tìm hoàng hôn": "dreamer",
       "Chương 6 · Tối · Mì hoành thánh": "daily_beetle", "Cuối tập": "late_night_radio"}
SWITCH = {"Mùa cà phê chín": "dream_culture", "Nếm thử": None, "Đi ngắm hoàng hôn": "dreamer", "Kịp rồi": "late_night_radio"}
music = []; cur = None; trk = None; lastch = None
for s in segs:
    if s["chapter"] != lastch: trk = MUS[s["chapter"]]; lastch = s["chapter"]
    base = re.sub(r" \((tiếp|cảnh chèn)\)$", "", s["label"])
    if base in SWITCH and not s["label"].endswith("(tiếp)") and (s["label"] == base or s["label"].endswith("(cảnh chèn)") and not any(x["label"] == base for x in segs[:segs.index(s)])):
        trk = SWITCH[base]
    st = s["_t"]; en = st + s["out"] - s["in"]
    if trk is None:
        if s["label"].startswith("Vị khói") or s["label"].startswith("Nếm thử"): cur = None; continue
        trk = "life_of_riley"
    if cur and cur["track"] == trk and abs(cur["end"] - st) < 0.05 and en - cur["start"] <= 115: cur["end"] = round(en, 2)
    else:
        if cur and cur["track"] == trk and abs(cur["end"] - st) < 0.05:  # quá 115 s: đổi điểm bắt đầu trong bài để không lặp đoạn
            pass
        cur = {"track": trk, "start": round(st, 2), "end": round(en, 2), "from": 0, "vol": {"late_night_radio": 0.17}.get(trk, 0.24), "fadein": 1.0, "fadeout": 1.8}; music.append(cur)
played = {}  # bài dùng lại thì phát tiếp từ chỗ đã dừng, không lặp đoạn đầu
for k, m in enumerate(music):
    if k and music[k - 1]["track"] == m["track"] and abs(m["start"] - music[k - 1]["end"]) < 0.05:
        m["from"] = round(music[k - 1]["from"] + music[k - 1]["end"] - music[k - 1]["start"], 2); m["fadein"] = 0.0; music[k - 1]["fadeout"] = 0.0
    else: m["from"] = round(played.get(m["track"], 0.0), 2)
    played[m["track"]] = m["from"] + m["end"] - m["start"]
for m in music: print("  nhạc", m["track"], m["start"], m["end"], round(m["end"] - m["start"], 1), "từ", m["from"])
for s in segs: s.pop("_t", None)
# phụ đề: không ngắt dòng giữa từ ghép ("cà / phê", "địa / điểm"): kéo chữ cuối dòng trên xuống đầu dòng dưới
COMP = {x.lower() for x in """cà phê|địa điểm|hoàng hôn|bầu trời|nhà sàn|nhà dài|mọi người|Buôn Ma|Ma Thuột|Buôn Mê|đồng bào|trang trại|hoành thánh|bánh canh|Ea Kao|Trần Nhật|Nhật Duật|Nhật Bản|người Nhật|thành phố|cầu thang|phụ nữ|đàn ông|đặc sản|công đoạn|công sức|Sài Gòn|tuổi thơ|khủng long|Google Maps|máy lạnh|thất bại|tham quan|hướng dẫn|ba chỉ|thịt ba|buổi sáng|dậy trễ|ăn riêng|ăn chung|quá trình|trồng trọt|sản xuất|thành phẩm|vệ sinh|chất lượng|Akô Dhông|Hồ Tùng|Tùng Mậu|Bà Già|ca cao|lấy chồng|con gái|vợ chồng|chế độ|mẫu hệ|tre nứa|bàn ghế|chiều nay|hôm nay|ngày xưa|con đường|xung quanh|đám mây|Mì Hường|thơm quá|đẹp quá|cây tiêu|lá chè|quả chín|chín đỏ|hạt cà|nghỉ ngơi|nhiều lần|đi ăn|cơm đồng""".split("|")}
def fix_compounds():
    seq = []
    for sg in segs:
        for x in sg.get("subs", []):
            if not seq or seq[-1] != x[2]: seq.append(x[2])
    rep = {}
    for k in range(len(seq) - 1):
        A, B = rep.get(seq[k], seq[k]), seq[k + 1]
        if A == B: continue
        for _ in range(3):
            aw, bw = A.split(), B.split()
            if len(aw) < 3 or not bw: break
            w1 = aw[-1]; w2 = bw[0].strip(",.!?").lower()
            if w1[-1] in ",.!?:": break
            if f"{w1.lower()} {w2}" in COMP: A = " ".join(aw[:-1]); B = w1 + " " + B
            else: break
        if A != rep.get(seq[k], seq[k]): rep[seq[k]] = A
        if B != seq[k + 1]: rep[seq[k + 1]] = B; seq[k + 1] = B
    n = 0
    for sg in segs:
        for x in sg.get("subs", []):
            if x[2] in rep: x[2] = rep[x[2]]; n += 1
    print("phụ đề sửa ngắt từ ghép:", len(rep), "dòng")
fix_compounds()
edl = {"ep": "testlate", "ver": 8, "size": [1920, 1080], "segments": segs, "music": music, "sfx": sfx}
json.dump(edl, open("/home/claude/pumdung/testlate/edl_v5.json", "w"), ensure_ascii=False, indent=1)
print(len(segs), "đoạn", f"{total/60:.1f} phút", len(sfx), "tiếng hiệu ứng", sum(len(s["doodles"]) for s in segs), "doodle")
