---
name: pum-dung-vlog
description: "Dựng tập vlog YouTube/TikTok của Pum từ clip Pum gắn theo kịch bản trong Pum Studio: quét clip, đề xuất hướng dựng, dựng bản nháp có lồng tiếng, nhạc có giấy phép, chấm 9/10 rồi mới giao."
---

# Dựng vlog cho Pum (AI dựng song song kịch bản)

Dùng khi nhắn: "Dựng tập … từ Pum Studio", "Dựng tiếp tập …", "Sửa bản nháp tập …", "Xuất bản cuối tập …", hoặc khi Pum gửi footage để dựng. Luôn mở skill **pum-video-dna** trước: luật trung thực, chữ ký hình ảnh và bảng chấm của kênh cao hơn mọi thứ ở đây.

## Luồng 5 bước (app pum.cherie.io.vn › Quay › Dựng và đăng)
1. **Tải video**: Pum tải video vào đúng cảnh của kịch bản (Cảnh / Nói tại chỗ / Lồng tiếng, ghi chú take, sao "Ưng"), cảnh ngoài kịch bản kèm lý do. Video tải thẳng lên Google Drive của Pum (thư mục "Pum Studio · Video gốc / Tập / Chương", chia sẻ cho Gmail đang nối với Claude); app lưu tên, dung lượng, thời lượng, ảnh nhỏ và mã file Drive (`drive`).
2. **Gửi AI**: Pum bấm Gửi rồi nhắn "Dựng tập X" trong chat Claude. → AI lấy video trên Drive, quét, viết hướng dựng. Video chưa lên Drive thì Pum đính kèm trong chat.
3. **Hướng dựng**: AI đưa hướng dựng lên app. Pum góp ý, bấm Duyệt, nhắn "Dựng tiếp tập X". → AI dựng bản nháp.
4. **Bản nháp**: Pum xem bản nhẹ trong app, chạm từng đoạn để góp ý (bỏ, ngắn lại, đổi take, sửa chữ, đổi nhạc, sửa phụ đề). "Sửa bản nháp tập X" → AI sửa, tăng số bản. "Ưng rồi" → "Xuất bản cuối tập X".
5. **Đăng**: AI gửi file 1080p trong chat, ghi công nhạc hiện ở app để dán vào mô tả.

## Chuẩn bị mỗi phiên
- Repo: `leenguyenhongphuc-netizen/pum-studio` (gắn bằng add_repo, access "push"), clone vào `/home/claude/pum-studio`. Công cụ ở `tools/dung/`.
- `pip install --break-system-packages faster-whisper cryptography pillow numpy`; cần ffmpeg có libass, libvpx.
- Concat (trình dựng mã nguồn mở, github.com/jub0t/Concat, AGPL-3.0): `python3 -I concat_mcp.py install` (tải bản .deb Linux từ trang Concat, giải nén vào `~/.local/concat`, không cần quyền root). Kiểm: `python3 -I concat_mcp.py` in ra phiên bản và chế độ `headless`.
- Mật khẩu app (đọc kịch bản, ghi trạng thái, mã hoá bản nháp): `export PUM_PASS=<mật khẩu app>` (có trong skill riêng của anh Phúc). Không ghi mật khẩu vào repo, Project hay tin nhắn công khai.
- Phông chữ (Be Vietnam Pro, Nunito, Playfair) và nhạc tự tải về `/home/claude/cache` khi chạy.
- Tập test có hai kịch bản: `test` (bản gốc) và `testlate` (bản dậy muộn). Dùng đúng mã tập mà app ghi (xem `fetch`).
- Dữ liệu dựng nằm trong kho `vids` của app: clip ở `c_<mã cảnh>`, trạng thái dựng ở `e_<mã tập>`.

## Lệnh (chạy trong `tools/dung`, luôn `python3 -I`)
| Việc | Lệnh |
|---|---|
| Lấy kịch bản, clip đã gắn, góp ý | `pumdung.py fetch <ep>` |
| Lấy video trên Drive | `pumdung.py drive <ep>` in danh sách mã Drive cần tải; với mỗi mã gọi công cụ Google Drive `download_file_content` (file về một đường dẫn tạm), rồi `pumdung.py place <ep> <đường dẫn tạm> <mã Drive>`. Xong chạy `match <ep> /home/claude/pumdung/<ep>/src` |
| Khớp file Pum gửi với clip đã gắn | `pumdung.py match <ep> /mnt/user-data/uploads` (khớp theo dung lượng, thời lượng ±0,35 s, tên; báo clip thiếu và file chưa gắn) |
| Quét clip | `pumdung.py scan <ep>` (lời nói có mốc từng chữ, độ nét, độ sáng, độ lớn âm) rồi `pumdung.py sheet <ep>` và **tự xem ảnh** từng clip; sau đó Agent chọn take nghe hết và viết `takes.json` (mục Hai agent) |
| Đưa hướng dựng lên app | `pumdung.py board <ep> board.json "lời nhắn ngắn"` |
| Dựng | `render.py <ep> edl.json` → `work/<ep>/v<N>/final.mp4, proxy.mp4, timeline.json, credits.txt` |
| Kiểm kỹ thuật | `qa.py <ep> <N>` + xem mọi ảnh `qa/sheet_*.jpg` |
| Đưa bản nháp lên app | `pumdung.py draft <ep> <N> "lời nhắn"` (mã hoá, đẩy lên web, ghi trạng thái) |
| Dự án Concat chỉnh tay | `concat_build.py <ep> edl.json` → `v<N>/concat_project.zip` + `concat_final.mp4` (khoảng 3 giây máy cho 1 giây video) |
| Báo bản cuối | gửi `final.mp4` bằng SendUserFile, rồi `pumdung.py final <ep> <N>` |

## Hai agent: Agent chọn take và Agent dựng
Mỗi đoạn kịch bản thường quay lại nhiều lần (sai thoại, ngại, lúng túng, cười giữa câu). Chọn take là việc riêng, làm trước khi dựng, theo tư duy một editor chuyên vlog lifestyle: người xem phải thấy Pum tự nhiên, rõ mặt, nói trôi.

### Agent chọn take (nghe toàn bộ, không bỏ clip nào)
- Nghe **hết mọi giây** của mọi video gốc (bản ghi lời có mốc từng chữ bằng faster-whisper large-v3-turbo, đưa âm vào dạng mảng numpy) và xem ảnh khung hình mỗi 2–3 giây của từng clip. Không chọn theo tên file hay theo clip đầu tiên khớp kịch bản.
- Gom các take cùng một câu/một ý (so lời nói, nơi quay, quần áo, giờ trong tên file), rồi chấm từng take trên 10:

| Tiêu chí | Điểm | Đạt khi |
|---|---|---|
| Thoại | 3 | trọn câu, đúng ý kịch bản hoặc tự nhiên hơn, không vấp, không nói lại, không "ờ ờ" kéo dài |
| Mặt Pum | 2 | thấy rõ mặt Pum, mắt nhìn ống kính hoặc đúng hướng, không bị cắt nửa mặt, không chĩa máy lên trời/xuống đất |
| Hình | 2 | nét, đủ sáng, không rung mạnh, màu thật |
| Năng lượng | 2 | tươi, tự tin, cảm xúc thật (cười, "ủa", nếm thử) |
| Âm | 1 | lời rõ, gió và ồn nền không lấn lời |

- **Chỉ dùng take từ 9/10.** Đoạn nào không có take 9: ghép phần tốt của hai take (cắt ở chỗ ngắt câu, che mối nối bằng cảnh chèn) hoặc dùng lời tại chỗ trên cảnh chèn; vẫn dưới 9 thì đổi thành lồng tiếng và đưa vào yêu cầu lồng tiếng cho Pum. Không dùng take hỏng vì "đủ ý".
- Ghi kết quả vào `takes.json` (mỗi đoạn: các take đã nghe, điểm từng tiêu chí, take chọn, mốc in/out, lý do) và tóm tắt trong `board.json` (`use`). Pum xem được vì sao chọn.

### Riêng tư: người đi cùng và biển số xe
- Không dùng hình người đi cùng Pum (bạn, người nhà, người quay) và người lạ nhìn rõ mặt. Ưu tiên theo thứ tự: chọn take/khung khác → cắt bớt (in/out) → `zoom` cúp sát Pum → che mờ bằng `hide`. Người đứng bán hay hướng dẫn chỉ xuất hiện khi Pum đã xác nhận họ đồng ý (ghi vào `questions`).
- Không để lộ biển số xe (ô tô, xe máy), số điện thoại, giấy tờ, màn hình điện thoại có thông tin riêng: cắt hoặc che `hide` suốt thời gian chúng hiện.
- Cách che trong edl: `"hide":[{"box":[x,y,w,h],"start":0,"end":3.5}]`, `box` tính theo tỉ lệ 0–1 của khung ra 1920×1080, giây tính từ đầu đoạn. Vật di chuyển thì chia nhiều mốc nhỏ. Sau khi dựng phải xem lại ảnh qa để chắc đã che hết.

### Agent dựng (editor vlog lifestyle)
- Nhận `takes.json` và kịch bản, dựng theo các mục bên dưới: nhịp, chèn cảnh, chữ, nhạc, chuyển cảnh, che riêng tư. Mỗi đoạn tự hỏi như editor: đoạn này giữ người xem không, có thừa không, có cảnh đẹp hơn để chèn không, cảm xúc có rõ không.
- Làm việc theo vòng: dựng → qa → tự xem ảnh và chấm → agent chấm độc lập → sửa → dựng lại, cho tới khi đạt cổng chất lượng. Mọi lựa chọn ghi lý do ngắn vào board để Pum duyệt.

## Hướng dựng (board.json, bước 3)
Đọc hết: kịch bản theo thứ tự, ghi chú và sao "Ưng" của Pum, lý do quay ngoài kịch bản, lời nói thật trong `scan.json`, ảnh xem nhanh. Rồi viết:
```json
{"summary":"2–4 câu: câu hỏi của tập, cách mở, nhịp","length":"khoảng 12 phút",
 "music":[{"track":"carefree","title":"Carefree","part":"Mở tập, đi đường","mood":"tươi, đi bộ","why":"vì sao hợp đoạn này","new":true}],
 "chapters":[{"title":"Chương 1 · …","sec":75,"plan":"1–2 câu",
   "segs":[{"label":"Hook câu B","take":"<clip id>","clips":["<id>"],"use":"take 2, 0:03–0:09, câu nói trôi nhất","voice":"tại chỗ|lồng tiếng|không lời","text":"chữ trên hình","fx":"chớp kem","sec":6}]}],
 "extras":[{"clip":"<id>","idea":"dùng cảnh ngoài kịch bản thế nào"}],
 "missing":["cảnh còn thiếu và cách xử lý"], "questions":["tối đa 4 câu cần Pum trả lời"]}
```
Lời nói, giá, tên món, cảm nhận của Pum chỉ lấy từ clip hoặc ghi chú. Điều chưa chắc đưa vào `questions`, không đoán.

## Bản dựng (edl.json, bước 4)
```json
{"ep":"testlate","ver":1,"size":[1920,1080],
 "segments":[{"id":"s1","label":"Dậy muộn","chapter":"Mở tập","clip":"<id>","in":2.0,"out":7.5,
   "audio":"src|amb|low|mute","vol":1,"sub":true,"speed":1,"fit":"fill|blur","zoom":[1.0,1.05],"bright":0.04,
   "vo":{"clip":"<id file lồng tiếng>","in":0,"out":6.2,"at":0.3},
   "text":[{"style":"tape|postcard|label|price|big|question","text":"…","start":0.2,"end":3.0}],
   "subs":[[0.4,2.1,"sửa phụ đề tay khi Pum đã chỉnh"]],
   "trans":"chop_kem|bang_hong|trang_giay|tim"}],
 "music":[{"track":"carefree","start":0,"end":48,"from":0,"vol":0.16,"fadein":1.2,"fadeout":2}],
 "sfx":[{"name":"pop|whoosh|ding|boop|tick","at":12.3,"vol":0.4}]}
```
- `audio`: `src` giữ lời tại chỗ; `amb` tiếng môi trường vừa phải dưới cảnh không lời; `low` hạ nền khi có lồng tiếng; `mute` khi tiếng xấu.
- `fit:blur` cho clip dọc trong video ngang (tự chọn nếu clip dọc). Phụ đề tự lấy từ lời thật của clip hoặc file lồng tiếng.
- Nhạc chỉ lấy trong `music.json` (đã kiểm giấy phép từng bài; tự ghi công trong `credits.txt`). Muốn dùng bài mới thì thêm vào `music.json` theo mục "Âm nhạc" bên dưới, không chèn thẳng vào edl. Tiếng hiệu ứng do code tự tạo, không bản quyền. Không dùng nhạc, phim, ảnh của người khác ngoài danh sách. Không chèn footage tải từ mạng (video mẫu tham khảo có dùng cảnh phim tài liệu: Pum không làm vậy).

## Âm nhạc: phong phú, không nhàm
Nhạc nhàm vì ba lý do: kho ít bài (chỉ Kevin MacLeod), một bài chạy suốt nhiều phút, và tập nào cũng dùng lại vài bài quen. Mỗi tập xử lý cả ba.

### 1. Mở rộng kho nhạc (chỉ bài dùng được cho kênh có kiếm tiền)
| Nguồn | Lấy gì | Không lấy | Ai tải |
|---|---|---|---|
| Kevin MacLeod (incompetech.com) | CC BY 4.0 | | AI |
| Free Music Archive (freemusicarchive.org) | CC BY, CC0, Public Domain | NC (phi thương mại), ND, bài không ghi giấy phép | AI tìm, đưa link; tải không được thì nhờ Pum |
| Chosic (chosic.com) | bài ghi rõ CC BY, CC0 hoặc Public Domain | bài chỉ ghi "free", NC, bài cần mua giấy phép | như trên |
| YouTube Audio Library (YouTube Studio › Thư viện âm thanh) | bài "không cần ghi công" hoặc "cần ghi công" (ghi đúng dòng YouTube đưa) | | Pum tải (cần đăng nhập kênh), gửi qua Drive |
| Nhạc thịnh hành trên TikTok | Pum tự chọn trong app TikTok khi đăng | không bao giờ ghép sẵn vào file | Pum |

- YouTube Audio Library: chỉ dùng cho bản đăng YouTube. Bản TikTok chỉ dùng khi điều khoản của bài cho phép đăng ngoài YouTube; chưa chắc thì đổi bài khác.
- Mỗi bài mới thêm vào `music.json` đủ: `id, title, artist, source_url, license, credit` (dòng ghi công nguyên văn), `mood` (2–3 từ), `energy` (1–5), `bpm`, `instruments`, `best_part` (giây đoạn hay nhất), `checked` (ngày kiểm giấy phép). Thiếu giấy phép rõ ràng thì không thêm.
- Mỗi lần dựng, nếu kho còn ít hơn 3 bài hợp mood một chương mà chưa dùng gần đây: tìm thêm 2–3 bài từ các nguồn trên, ghi vào `questions` để Pum duyệt trước khi thêm.
- Giữ kho cân đối giữa các mood: tươi/đi đường, tò mò/khám phá, ấm/kể chuyện, vui nhộn/phản ứng, lắng/hoàng hôn, nhạc cụ địa phương (đàn tranh, sáo, guitar mộc... chỉ khi có bản đúng giấy phép).

### 2. Bản đồ nhạc cho mỗi tập (viết vào `music` của board.json)
- Nhạc đi theo cảm xúc từng chương, không theo độ dài. Tập 10–12 phút dùng 4–6 bài. Một bài không chạy liền quá 90–120 giây; đổi bài khi đổi chương, đổi nơi hoặc đổi cảm xúc.
- Mẫu khung (điều chỉnh theo kịch bản):

| Đoạn | Năng lượng | Gợi ý |
|---|---|---|
| Hook 0–10 s | 4 | bài vào nhanh, nhạc "rơi" ngay sau câu hook của Pum |
| Đi đường, giới thiệu nơi | 3 | nhịp đi bộ 100–120 bpm |
| Khám phá, xem đồ, xem món | 2–3 | nhẹ, tò mò, ít nhạc cụ |
| Nếm thử, phản ứng | 0 | tắt nhạc, để tiếng thật; vào lại sau phản ứng |
| Kể chuyện, lịch sử | 2 | ấm, chậm, nhạc cụ mộc |
| Kết, câu hỏi cuối | 2 | lắng, mở, kết thúc trọn câu nhạc |

- Tương phản: hai chương liền nhau không dùng cùng mood và cùng mức năng lượng.
- Bắt đầu bài ở `best_part` (trường `from` trong edl), không mặc định từ giây 0. Kết bài ở cuối câu nhạc hoặc fade 1,5–3 s trùng điểm cắt cảnh, không cắt cụt giữa nốt.

### 3. Kỹ thuật làm nhạc sống động
- **Khoảng lặng có chủ đích**: tắt nhạc 1–3 s trước câu quan trọng, khoảnh khắc nếm thử, "ủa", cười; im lặng làm người xem chú ý hơn.
- **Cắt theo nhịp** ở đoạn montage (cảnh không lời 2–4 s): đặt điểm cắt trùng phách theo `bpm` (60/bpm giây một phách), đổi cảnh mỗi 2 hoặc 4 phách.
- **Âm môi trường là một lớp nhạc**: tiếng chợ, xèo xèo, sóng, mưa, tiếng bước chân. Ở cảnh đẹp có tiếng thật hay thì hạ nhạc xuống hoặc bỏ hẳn (`audio:"amb"`).
- **Chuyển bài mượt**: chồng hai bài 0,5–1 s tại chỗ chuyển cảnh thương hiệu, hoặc dùng `whoosh` che chỗ đổi bài.
- **Hiệu ứng âm đúng lúc**: `pop` cho nhãn chữ, `ding` cho giá, `tick` cho đếm ngược. Tối đa một tiếng mỗi 5–8 s để không thành ồn.
- **Bài chữ ký kênh**: được phép một đoạn ngắn 3–5 s giống nhau ở mọi tập (mở hoặc kết) để người xem nhận ra Pum. Ngoài đoạn đó, các bài còn lại phải luân phiên.

### 4. Chống lặp giữa các tập
- Trước khi chọn nhạc, đọc `credits.txt` của 3 tập gần nhất (trong `work/<ep>/v*/` hoặc trạng thái `e_<ep>` trên app). Không dùng lại bài đã dùng ở 2 tập gần nhất, trừ bài chữ ký.
- Mỗi tập có ít nhất 1 bài chưa từng dùng trên kênh (`"new":true` trong board.json).
- Nếu Pum góp ý "đổi nhạc" ở một đoạn: đổi sang bài khác mood hoặc khác nhạc cụ, không đổi sang bài gần giống.

### 5. Bản cho TikTok
- Khi xuất bản cuối, xuất thêm `final_nomusic.mp4`: giữ lời, lồng tiếng, âm môi trường, hiệu ứng, bỏ nhạc nền. Pum có thể thêm nhạc thịnh hành trong app TikTok lúc đăng (tăng phân phối) mà không bị chồng hai lớp nhạc.
- Ghi công trong mô tả: gom đủ mọi bài đã dùng, đúng dòng ghi công của từng giấy phép.

## Phong cách (theo video mẫu Pum đưa và DNA kênh)
- Mở tập trong 10 giây đầu: câu hook thật của Pum + băng hồng; không intro logo. Xem trước 4–6 cảnh đẹp nhất có lồng tiếng.
- Nhịp: cảnh không lời 2–4 s, đổi cỡ cảnh khi có lý do; đoạn Pum nói giữ trọn câu, cắt bỏ khoảng ngập ngừng; trung vị đoạn khoảng 3–5 s như video mẫu.
- Phản ứng tại chỗ ("ủa", cười, nếm thử) giữ nguyên tiếng thật, có thể chèn `pop` nhẹ và nhãn chữ. Phần kể chuyện (lịch sử, văn hoá) dùng lồng tiếng trên cảnh nền, nhạc `teller_of_the_tales` hoặc `dream_culture`.
- Âm: lời nói rõ nhất; nhạc nhỏ, tự hạ khi có lời (render đã nén theo lời); âm môi trường giữ ở cảnh không lời; tổng -14 LUFS. Chọn và đổi nhạc theo mục "Âm nhạc: phong phú, không nhàm".
- Chữ: `tape` cho hook và kết luận, `postcard` cho nơi/thời điểm, `price` cho giá có nơi và ngày, `label` cho nhãn series, `question` + Mini Pum cho lời mời cuối. Chuyển cảnh thương hiệu chỉ khi đổi chương hoặc đổi nơi.
- Kết: một câu hỏi, không xin like/đăng ký, không outro logo.

## Concat: dự án để Pum tự chỉnh tay
Concat chạy không cửa sổ qua MCP (`concat --mcp headless`, gói trong `concat_mcp.py`: `Concat().call(tên_công_cụ, tham_số)`; 46 công cụ như project_create, media_import, clip_add, clip_trim, clips_move, clip_update, title_add, captions_add, effect_layer_add, clip_stabilize, export_start, preview_frame).
- `render.py` vẫn là bản giao chính (chữ thương hiệu nghiêng đúng DNA, nhạc tự hạ theo lời, nhanh hơn). `concat_build.py` dựng **cùng edl.json** thành dự án Concat: mỗi đoạn một clip trên dòng thời gian; lồng tiếng, chữ, phụ đề, nhạc, hiệu ứng âm ở lane riêng; lời nói qua `concat.denoise` + `concat.enhance-voice`; clip dọc nền mờ; chuyển cảnh từ thư viện Concat; cuối cùng chuẩn -14 LUFS bằng ffmpeg.
- Gửi `concat_project.zip` khi Pum muốn tự kéo cắt: giải nén, mở bằng app Concat (máy tính hoặc Android), chỉ cho Concat thư mục clip gốc nếu báo thiếu (dự án chỉ ghi đường dẫn, không chứa clip).
- Dùng thêm khi cần: `clip_stabilize` cho cảnh rung, `concat.denoise` cho tiếng gió, bộ lọc màu (`concat.natural`, `concat.golden-hour` cho hoàng hôn; không phủ màu làm sai món ăn), `preview_frame` để tự xem khung hình.
- Lưu ý đã gặp: chữ nghiêng làm mất dấu chồng (Ủ, Ẩ) nên chữ trong Concat để đứng; `strokeWidth` tính theo chiều cao khung (0.004 là viền mảnh, 0.1 thành mảng đặc); hai mảng chữ chồng nhau sẽ che dấu của dòng dưới.
- Concat chỉ ghi trong thư mục được phép: đặt `CONCAT_MCP_ROOTS` (mặc định `/home/claude`).

## Sửa theo góp ý (bước 4 lặp lại)
`fetch` in ra `notes` của bản đang xem (bỏ, ngắn lại, đổi take, sửa chữ, đổi nhạc, sửa phụ đề, góp ý tại giây). Áp từng góp ý vào edl.json, tăng `ver`, dựng lại, chạy qa, chấm lại, rồi `draft`. Phụ đề Pum sửa thì ghi vào `subs` của đoạn đó.

## Cổng chất lượng: chỉ giao khi đạt 9/10
1. `qa.py` phải `pass` (1080p 30fps, -15..-13 LUFS, đỉnh ≤ -1 dBTP, không khung đen, không lặng > 2 s, không còn ___ hay [ ] trên hình).
   Thêm: mọi đoạn Pum nói dùng take đạt từ 9/10 trong `takes.json`; không còn mặt người đi cùng hay biển số xe nào lộ trên ảnh qa.
2. Tự xem mọi ảnh `qa/sheet_*.jpg`: chữ không che mặt, đúng dấu tiếng Việt, đúng vùng an toàn, màu thật.
3. Chấm theo pum-video-dna mục 9 (5 tiêu chí × 2 điểm) và đủ 6 cổng. Thêm cho tập dài: mở tập giữ người xem trong 30 giây đầu; mỗi chương trả lời đúng điều nó hứa; không đoạn nào lê thê quá 20 s không đổi hình. Nhạc: đủ 4–6 bài cho tập 10–12 phút, không bài nào chạy liền quá 120 s, không trùng bài với 2 tập trước (trừ bài chữ ký), có ít nhất một khoảng lặng ở khoảnh khắc phản ứng, mọi bài có giấy phép và dòng ghi công trong `credits.txt`.
4. Nhờ một agent khác (chưa thấy quá trình dựng) xem ảnh qa, timeline.json và kịch bản rồi chấm độc lập. Lấy điểm thấp hơn.
5. Dưới 9: sửa chỗ yếu nhất, dựng lại, chấm lại. Không giao bản dưới 9. Nói rõ phần AI không nghe được (âm thanh): Pum phải nghe lại.

## Lưu ý kỹ thuật
- Bản nhẹ ≤ 95 MB mới đẩy lên web được (GitHub). Tập dài quá thì hạ `crf` proxy hoặc 640 px.
- File 1080p gửi bằng SendUserFile; nếu quá nặng thì xuất `crf 23` và báo dung lượng.
- Video trên Drive là bản gốc. Nếu `download_file_content` báo file quá lớn, báo anh Phúc tên file và dung lượng, nhờ Pum đính kèm riêng file đó; không đổi quyền chia sẻ sang công khai.
- iPhone có thể nén lại file khi chọn từ Thư viện: nếu `match` báo thiếu, so theo thời lượng và hỏi Pum đúng clip nào.
- Whisper nghe tiếng Việt có thể sai chữ: luôn nhắc Pum xem mục Phụ đề trong bản nháp.