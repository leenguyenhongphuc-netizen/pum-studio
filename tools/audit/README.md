# Bộ kiểm giao diện Pum Studio

Chạy sau mỗi lần sửa giao diện, trên 6 cỡ màn hình (Android 412, iPhone 390, iPad dọc 820, iPad ngang 1180, laptop 1366, PC 1920) và thêm WebKit (nhân của Safari, Chrome trên iPhone/iPad). Dữ liệu giả, không ghi vào dữ liệu thật.

1. `python3 -m http.server 8770` ở thư mục web (có `drafts/test` giả nếu muốn thử bước Bản nháp).
2. `PUM_PASS=... python3 dung_audit.py p412 t820 d1920`: lỗi JS, kéo ngang, nút dưới 44px, chữ dưới 12px, chụp từng bước Dựng.
3. `PUM_PASS=... python3 jump_audit.py`: bấm chọn bước, chương (Dựng) và phần (Quay); đạt khi thanh vừa bấm đứng yên (lệch ≤ 2px, đo ngay và sau 1,5 giây) và thanh chọn ngang không tự trượt khi nút đã nằm trong khung.

Quy tắc rút ra (17/11/2026, Pum quay màn hình thấy trang giật khi chọn bước): bấm chọn không được làm trang nhảy dọc hay thanh chọn trượt ngang; khi nội dung mới ngắn hơn, giữ chiều cao để màn hình đang xem không bị kéo đi.

17/11/2026 (ảnh chụp trên máy tính bảng ngang): bước Gửi AI bị vỡ vì lớp `.howto` trùng tên với phần Cẩm nang, lớp sau ghi đè thành lưới 2 cột và chữ đậm nghiêng. Quy tắc: lớp CSS mới phải có tên riêng, tìm `grep -n "\.tên{" index.html` trước khi đặt; thêm cỡ 1280×800 (máy tính bảng Android nằm ngang) vào cả hai bộ kiểm. Nút bị khoá phải có dòng nói vì sao và cách mở khoá; trang trống phải có nút đưa về bước cần làm.
