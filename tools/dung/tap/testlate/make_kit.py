"""Bộ đăng (bước 5 trong app): tên + mô tả YouTube có chương thật, caption TikTok từng phần.
python3 make_kit.py <bản ngang> <kit.json>"""
import json, sys, re
from pathlib import Path
D = Path("/home/claude/pumdung/testlate"); ver = sys.argv[1]; out = Path(sys.argv[2])
TL = json.load(open(D / f"v{ver}" / "timeline.json"))

def ts(t):
    t = int(t); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"
NAME = {"Mở tập": "Mở tập: dậy trễ mất rồi", "Chương 1 · Bánh canh": "Bánh canh Bà Già (hết sườn!)", "Chương 2 · Nhà dài giữa phố": "Buôn Akô Dhông, nhà dài giữa phố",
        "Chương 3 · Cơm đồng bào": "Mâm cơm đồng bào 6 món", "Chương 4 · Lên farm cà phê": "Lên trang trại cà phê, tự pha và nếm thử",
        "Chương 5 · Đi tìm hoàng hôn": "Đi tìm hoàng hôn ở hồ Ea Kao", "Chương 6 · Tối · Mì hoành thánh": "Tối: mì hoành thánh"}
ch = []
for s in TL["segments"]:
    c = s.get("chapter", "")
    if c in NAME and (not ch or ch[-1][1] != NAME[c]): ch.append((s["start"], NAME[c]))
ch[0] = (0, ch[0][1])
ch = [x for k, x in enumerate(ch) if k + 1 == len(ch) or ch[k + 1][0] - x[0] >= 10]
credits = TL.get("credits") or ""
titles = list(dict.fromkeys(re.findall(r"^(.+?) Kevin MacLeod", credits, re.M)))
cred_full = "\n".join(f"{t} – Kevin MacLeod (incompetech.com)" for t in titles) + "\nLicensed under Creative Commons: By Attribution 4.0 License\nhttp://creativecommons.org/licenses/by/4.0/"

desc = f"""Hôm nay Pum dậy trễ, nên một ngày ở Buôn Ma Thuột cứ thế đi theo nhịp của người dậy trễ: tới quán bánh canh thì hết sườn, ghé buôn Akô Dhông ngay giữa phố, trưa ăn cơm đồng bào, chiều lên trang trại cà phê rồi đi tìm hoàng hôn ở hồ Ea Kao.
Pum là người Buôn Mê mà không thích cà phê vì đắng, nên lần này thử rang hạt và tự tay pha một ly. Kết quả thì bạn xem trong video nha.

Chương
""" + "\n".join(f"{ts(t)} {n}" for t, n in ch) + f"""

Những nơi trong tập
· Bánh canh Bà Già, 52/11 Hồ Tùng Mậu (chủ nhật nghỉ bán)
· Buôn Akô Dhông, cuối đường Trần Nhật Duật
· Cơm đồng bào trong buôn
· Trang trại cà phê gần hồ Ea Kao
· Hồ Ea Kao
· Mì Hường (mì hoành thánh)

Bạn thuộc phe cà phê hay phe ca cao như Pum? Kể Pum nghe dưới bình luận nha.

Nhạc:
{cred_full}

#thudicungpum #buonmathuot #didauthudo"""

cap = (D / "tiktok_captions.txt").read_text().split("────────────────────────")[1:]
tt = []
for n, blk in enumerate(cap, 1):
    lines = [l for l in blk.strip().split("\n")]
    title = lines[0].split(" · ", 1)[1]; text = "\n".join(lines[1:]).strip()
    if n == 7: text = text.replace("Bạn thuộc phe cà phê hay phe ca cao như Pum?", "Ở chỗ bạn có quán mì hoành thánh nào ngon không?")
    T = json.load(open(D / f"v10{n}" / "timeline.json"))
    tt.append({"n": n, "title": title, "caption": text, "cover": f"tiktok_{n}_cover.jpg.enc", "dur": T["dur"], "file": f"Phan_{n}.mp4 (1080x1920)"})
kit = {"v": int(ver), "youtube": {"label": "tập dài", "title": "Người Buôn Mê không thích cà phê, về tận farm thử lại | Một ngày ở Buôn Ma Thuột",
       "desc": desc, "tags": ["Buôn Ma Thuột", "Buôn Mê", "vlog Buôn Ma Thuột", "bánh canh Buôn Ma Thuột", "buôn Akô Dhông", "nhà dài Ê Đê", "cơm đồng bào",
       "cà phê Buôn Ma Thuột", "trang trại cà phê", "hồ Ea Kao", "hoàng hôn", "mì hoành thánh", "Thử đi cùng Pum", "Đi đâu thử đó"],
       "thumb": "youtube_thumb.jpg.enc", "dur": TL["dur"], "file": f"final.mp4 bản {ver} (1920x1080)",
       "note": "Ghi chú: tên trang trại trong video máy nghe là “Aeroco Coffee”. Pum xác nhận đúng tên thì thêm vào dòng trang trại."},
       "tiktok": tt}
out.write_text(json.dumps(kit, ensure_ascii=False, indent=1)); print(desc[:1200])
