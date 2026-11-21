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

## Bản final 4K (v10 ngang, v111–v117 TikTok)
Bản final luôn dựng từ nguồn 4K; bản nháp thì nén nhẹ để gửi nhanh.

| File | Việc |
|---|---|
| `prep.py` + `prep4k_run.py` | `PREP_4K=1`: dò mặt/biển ở 1080 (lượt 1) rồi làm đẹp, che ở 3840×2160 đọc thẳng từ file gốc 4K (lượt 2), ghi `prep4k/`. Tải từng clip gốc, xử lý xong xoá. Chạy `--jobs 1` (2 job bị tràn RAM 8 GB), x264 veryfast crf 21. Đoạn nào trùng (clip, in, out) đã có trong `prep4k/bykey` thì dùng lại. |
| `merge_prep.py` | `PREP_DIR=.../prep4k` để ghép edl với bản 4K. |
| `platescan.py` | dò lại biển số trên bản xuất 4K (`PCONF=0.22 PSHARP=25 PLIKE=0` để bắt rộng rồi tự xem ảnh). Máy dò lúc prep chạy ở 1080 nên sót biển nhỏ, mà ở 4K lại đọc rõ: luôn soát lại bằng ảnh cắt 4K trước khi giao. |
| `patch9.py`, `patch11.py` | vá nhanh bản đã xuất (patch11 còn thay hình cả đoạn bằng bản dựng lại riêng đoạn đó: overlay bật theo `t`, không theo `n` — `n` của overlay đếm khung lớp phủ): che thêm ô mờ chỉ trong các đoạn giữa hai khung khoá, phần còn lại sao nguyên (cắt phần sao bằng `-frames:v`, không dùng `-t`, nếu không sẽ dư khung và lệch tiếng). Không dùng được cho lỗi lật gương: lỗi đó phải dựng lại. |
| `fixaudio.py` | chuẩn tiếng 2 lượt về −14 LUFS, đỉnh ≤ −1,5 dBTP. |
| `run_4k_example.sh` | ví dụ chạy dựng ngang 4K (`PUM_SEG_CRF=20 PUM_CRF=18 PUM_PRESET=faster`) song song một phần TikTok, rồi chuẩn tiếng và QA. |

Bài học từ lần chấm độc lập v9 (6,5/10):
- Clip quay camera trước có thể bị ngược gương: soi chữ trên biển hiệu mọi đoạn, đoạn nào ngược thì `hflip` (ô `hide_src` vẫn tính theo khung chưa lật).
- Không xoá file gốc khi edl còn lấy tiếng lồng từ đó (`vo.path`). Muốn tiết kiệm chỗ thì tách riêng tiếng ra file cùng tên.
- Một bài nhạc không chạy liền quá ~90 s: nghỉ một đoạn rồi đổi bài (`ALT` trong `build_edl_v5.py`).
- Ô che mờ dùng `soft_hide` (mờ Gauss có viền mờ dần), không dùng boxblur mảng phẳng.
- Thumbnail và ảnh bìa cũng phải áp `hide_src` (lấy khung từ nguồn thì không có ô che).
