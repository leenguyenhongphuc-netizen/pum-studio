# Công cụ dựng vlog của Pum Studio

Dùng cùng skill `pum-dung-vlog` (xem SKILL.md). Mật khẩu app không nằm trong repo: đặt biến môi trường `PUM_PASS` khi chạy.

- `pumdung.py`: lấy kịch bản và clip Pum gắn trong app, khớp file, quét clip, đưa hướng dựng và bản nháp lên app.
- `render.py`: dựng video từ `edl.json` (chữ thương hiệu, phụ đề từ lời thật, lồng tiếng, nhạc tự hạ khi có lời, hiệu ứng âm tự tạo, chuyển cảnh thương hiệu).
- `qa.py`: kiểm kỹ thuật và tạo ảnh xem nhanh để chấm.
- `music.json`: danh sách nhạc đã kiểm giấy phép (Kevin MacLeod, CC BY 4.0).

Bản nháp nằm trong `drafts/<tập>/` dưới dạng mã hoá, chỉ mở được khi đã vào app.
