---
name: pum-dung-vlog
description: Dựng tập vlog YouTube/TikTok của Pum từ footage Pum gắn theo kịch bản trong Pum Studio: quét clip, đề xuất hướng dựng, dựng bản nháp có lồng tiếng, nhạc có giấy phép, âm môi trường, chấm 9/10 rồi mới giao.
---

# Dựng vlog cho Pum (AI dựng song song kịch bản)

Dùng khi nhắn: "Dựng tập … từ Pum Studio", "Dựng tiếp tập …", "Sửa bản nháp tập …", "Xuất bản cuối tập …", hoặc khi Pum gửi footage để dựng. Luôn mở skill **pum-video-dna** trước: luật trung thực, chữ ký hình ảnh và bảng chấm của kênh cao hơn mọi thứ ở đây.

## Luồng 5 bước (app pum.cherie.io.vn › Quay › Dựng và đăng)
1. **Gắn clip**: Pum gắn clip vào đúng cảnh của kịch bản (Cảnh / Nói tại chỗ / Lồng tiếng, ghi chú take, sao "Ưng"), cảnh ngoài kịch bản kèm lý do. App chỉ lưu tên, dung lượng, thời lượng; file nằm trên điện thoại.
2. **Gửi AI**: Pum bấm Gửi, rồi đính kèm file vào chat Claude và nhắn "Dựng tập X". → AI quét, viết hướng dựng.
3. **Hướng dựng**: AI đưa hướng dựng lên app. Pum góp ý, bấm Duyệt, nhắn "Dựng tiếp tập X". → AI dựng bản nháp.
4. **Bản nháp**: Pum xem bản nhẹ trong app, chạm từng đoạn để góp ý (bỏ, ngắn lại, đổi take, sửa chữ, đổi nhạc, sửa phụ đề). "Sửa bản nháp tập X" → AI sửa, tăng số bản. "Ưng rồi" → "Xuất bản cuối tập X".
5. **Đăng**: AI gửi file 1080p trong chat, ghi công nhạc hiện ở app để dán vào mô tả.

## Chuẩn bị mỗi phiên
- Repo: `leenguyenhongphuc-netizen/pum-studio` (gắn bằng add_repo, access "push"), clone vào `/home/claude/pum-studio`. Công cụ ở `tools/dung/`.
- `pip install --break-system-packages faster-whisper cryptography pillow numpy`; cần ffmpeg có libass, libvpx.
- Concat (trình dựng mã nguồn mở, github.com/jub0t/Concat, AGPL-3.0): `python3 -I concat_mcp.py install` (tải bản .deb Linux từ trang Concat, giải nén vào `~/.local/concat`, không cần quyền root). Kiểm: `python3 -I concat_mcp.py` in ra phiên bản, chế độ `headless`.
- Mật khẩu app (đọc kịch bản, ghi trạng thái, mã hoá bản nháp): `export PUM_PASS=<mật khẩu app>` (có trong skill riêng của anh Phúc). Không ghi mật khẩu vào repo, Project hay tin nhắn công khai.
- Phông chữ (Be Vietnam Pro, Nunito, Playfair) và nhạc tự tải về `/home/claude/cache` khi chạy.
- Tập test có hai kịch bản: `test` (bản gốc) và `testlate` (bản dậy muộn). Dùng đúng mã tập mà app ghi trong `edits` (xem `fetch`).

## Lệnh (chạy trong `tools/dung`, luôn `python3 -I`)
| Việc | Lệnh |
|---|---|
| Lấy kịch bản, clip đã gắn, góp ý | `pumdung.py fetch <ep>` |
| Khớp file Pum gửi với clip đã gắn | `pumdung.py match <ep> /mnt/user-data/uploads` (khớp theo dung lượng, thời lượng ±0,35 s, tên; báo clip thiếu và file chưa gắn) |
| Quét clip | `pumdung.py scan <ep>` (lời nói có mốc từng chữ, độ nét, độ sáng, độ lớn âm) rồi `pumdung.py sheet <ep>` và **tự xem ảnh** từng clip |
| Đưa hướng dựng lên app | `pumdung.py board <ep> board.json "lời nhắn ngắn"` |
| Dựng | `render.py <ep> edl.json` → `work/<ep>/v<N>/final.mp4, proxy.mp4, timeline.json, credits.txt` |
| Kiểm kỹ thuật | `qa.py <ep> <N>` + xem mọi ảnh `qa/sheet_*.jpg` |
| Đưa bản nháp lên app | `pumdung.py draft <ep> <N> "lời nhắn"` (mã hoá, đẩy lên web, ghi trạng thái) |
| Dự án Concat chỉnh tay | `concat_build.py <ep> edl.json` → `v<N>/concat_project.zip` + `concat_final.mp4` (khoảng 3 giây máy cho 1 giây video) |
| Báo bản cuối | gửi `final.mp4` bằng SendUserFile, rồi `pumdung.py final <ep> <N>` |

## Hướng dựng (board.json, bước 3)
Đọc hết: kịch bản theo thứ tự, ghi chú và sao "Ưng" của Pum, lý do quay ngoài kịch bản, lời nói thật trong `scan.json`, ảnh xem nhanh. Rồi viết:
```json
{"summary":"2–4 câu: câu hỏi của tập, cách mở, nhịp","length":"khoảng 12 phút",
 "music":[{"track":"carefree","title":"Carefree","part":"Mở tập, đi đường"}],
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
- Nhạc chỉ lấy trong `music.json` (Kevin MacLeod, CC BY 4.0, đã kiểm giấy phép; tự ghi công trong `credits.txt`). Tiếng hiệu ứng do code tự tạo, không bản quyền. Không dùng nhạc, phim, ảnh của người khác ngoài danh sách. Không chèn footage tải từ mạng (video mẫu tham khảo có dùng cảnh phim tài liệu: Pum không làm vậy).

## Phong cách (theo video mẫu Pum đưa và DNA kênh)
- Mở tập trong 10 giây đầu: câu hook thật của Pum + băng hồng; không intro logo. Xem trước 4–6 cảnh đẹp nhất có lồng tiếng.
- Nhịp: cảnh không lời 2–4 s, đổi cỡ cảnh khi có lý do; đoạn Pum nói giữ trọn câu, cắt bỏ khoảng ngập ngừng; trung vị đoạn khoảng 3–5 s như video mẫu.
- Phản ứng tại chỗ ("ủa", cười, nếm thử) giữ nguyên tiếng thật, có thể chèn `pop` nhẹ và nhãn chữ. Phần kể chuyện (lịch sử, văn hoá) dùng lồng tiếng trên cảnh nền, nhạc `teller_of_the_tales` hoặc `dream_culture`.
- Âm: lời nói rõ nhất; nhạc nhỏ, tự hạ khi có lời (render đã nén theo lời); âm môi trường giữ ở cảnh không lời; tổng -14 LUFS.
- Chữ: `tape` cho hook và kết luận, `postcard` cho nơi/thời điểm, `price` cho giá có nơi và ngày, `label` cho nhãn series, `question` + Mini Pum cho lời mời cuối. Chuyển cảnh thương hiệu chỉ khi đổi chương hoặc đổi nơi.
- Kết: một câu hỏi, không xin like/đăng ký, không outro logo.

## Concat: dự án để Pum tự chỉnh tay
Concat chạy không cửa sổ qua MCP (`concat --mcp headless`, gói gọn trong `concat_mcp.py`: `Concat().call(tên_công_cụ, tham_số)`; 46 công cụ: project_create, media_import, clip_add, clip_trim, clips_move, clip_update, title_add, captions_add, effect_layer_add, export_start, preview_frame…).
- `render.py` vẫn là bản giao chính (chữ thương hiệu nghiêng đúng DNA, nhạc tự hạ theo lời, nhanh hơn). `concat_build.py` dựng **cùng edl.json** thành dự án Concat: mỗi đoạn một clip trên dòng thời gian, lồng tiếng, chữ, phụ đề, nhạc, hiệu ứng âm ở lane riêng; lời nói qua `concat.denoise` + `concat.enhance-voice`; clip dọc nền mờ; chuyển cảnh lấy từ thư viện Concat; cuối cùng chuẩn -14 LUFS bằng ffmpeg.
- Gửi `concat_project.zip` khi Pum muốn tự kéo cắt: giải nén, mở bằng app Concat (máy tính hoặc Android), chỉ cho Concat thư mục clip gốc nếu báo thiếu (dự án chỉ ghi đường dẫn, không chứa clip).
- Dùng thêm khi cần: `clip_stabilize` cho cảnh rung, `concat.denoise` cho tiếng gió, bộ lọc màu (`concat.natural`, `concat.golden-hour` cho hoàng hôn; không phủ màu làm sai món ăn), `preview_frame` để tự xem khung hình.
- Lưu ý đã gặp: chữ nghiêng làm mất dấu chồng (Ủ, Ẩ) nên chữ trong Concat để đứng; `strokeWidth` tính theo chiều cao khung (0.004 là viền mảnh, 0.1 thành mảng đặc); hai mảng chữ chồng nhau sẽ che dấu của dòng dưới.
- Concat không ghi ngoài thư mục được phép: đặt `CONCAT_MCP_ROOTS` (mặc định `/home/claude`).

## Sửa theo góp ý (bước 4 lặp lại)
`fetch` in ra `notes` của bản đang xem (bỏ, ngắn lại, đổi take, sửa chữ, đổi nhạc, sửa phụ đề, góp ý tại giây). Áp từng góp ý vào edl.json, tăng `ver`, dựng lại, chạy qa, chấm lại, rồi `draft`. Phụ đề Pum sửa thì ghi vào `subs` của đoạn đó.

## Cổng chất lượng: chỉ giao khi đạt 9/10
1. `qa.py` phải `pass` (1080p 30fps, -15..-13 LUFS, đỉnh ≤ -1 dBTP, không khung đen, không lặng > 2 s, không còn ___ hay [ ] trên hình).
2. Tự xem mọi ảnh `qa/sheet_*.jpg`: chữ không che mặt, đúng dấu tiếng Việt, đúng vùng an toàn, màu thật.
3. Chấm theo pum-video-dna mục 9 (5 tiêu chí × 2 điểm) và đủ 6 cổng. Thêm cho tập dài: mở tập giữ người xem trong 30 giây đầu; mỗi chương trả lời đúng điều nó hứa; không đoạn nào lê thê quá 20 s không đổi hình.
4. Nhờ một agent khác (chưa thấy quá trình dựng) xem ảnh qa, timeline.json và kịch bản rồi chấm độc lập. Lấy điểm thấp hơn.
5. Dưới 9: sửa chỗ yếu nhất, dựng lại, chấm lại. Không giao bản dưới 9. Nói rõ phần AI không nghe được (âm thanh): Pum phải nghe lại.

## Lưu ý kỹ thuật
- Bản nhẹ ≤ 95 MB mới đẩy lên web được (GitHub). Tập dài quá thì hạ `crf` proxy hoặc 640 px.
- File 1080p gửi bằng SendUserFile; nếu quá nặng thì xuất `crf 23` và báo dung lượng.
- iPhone có thể nén lại file khi chọn từ Thư viện: nếu `match` báo thiếu, so theo thời lượng và hỏi Pum đúng clip nào.
- Whisper nghe tiếng Việt có thể sai chữ: luôn nhắc Pum xem mục Phụ đề trong bản nháp.
