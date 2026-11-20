# Tập test BMT (testlate): bộ script đã dùng để dựng v8 và loạt TikTok

Đây là bản mẫu thật, đường dẫn còn ghi cứng `/home/claude/bmt` và `/home/claude/pumdung/testlate`. Tập mới: chép thư mục này, đổi đường dẫn và mã tập.

| File | Việc |
|---|---|
| `ingest3.py` | tải video gốc từ Drive, làm bản trung gian `mez/` (hiện hạ về 1080p, xem mục 4K trong SKILL) và tách tiếng để nghe |
| `build_edl_v5.py` | dựng edl bản ngang: `SP()` đoạn Pum nói (cắt nhảy, cảnh chèn giữ tiếng, `hide_src` chia theo mảnh), `BR()` cảnh không lời, nhạc, tiếng hiệu ứng, sửa phụ đề ngắt giữa từ ghép |
| `merge_prep.py` | ghép edl với file đã làm đẹp và che riêng tư (`prep/`) theo (clip, in, out) |
| `prune_segcache.py` | dọn kho đoạn đã dựng, chỉ giữ đoạn bản đang dùng |
| `build_tiktok.py` | cắt bản ngang thành loạt TikTok dọc theo câu chuyện: hook đầu video, nhãn series n/7, nhá phần sau ở cuối |
| `run_tiktok.sh` | dựng lần lượt các phần, chuẩn tiếng (`../../fixaudio.py`), QA |
| `make_thumbs.py` | thumbnail YouTube 1280x720 và ảnh bìa TikTok 1080x1920 |
| `make_kit.py` | bộ đăng: tên, mô tả YouTube có chương theo giờ thật, caption TikTok → `pumdung.py post` |
| `tiktok_captions.txt` | caption 7 phần (mẫu giọng văn) |
| `mock_vert.py`, `vtest.py` | xem nhanh bố cục khung dọc, thử cửa sổ 9:16 bám mặt Pum mà không cần dựng |
| `sync8.py` | đo lệch tiếng và hình của bản cuối |
| `cleanup_watch.sh` | dọn file tạm lớn khi máy ít chỗ |
