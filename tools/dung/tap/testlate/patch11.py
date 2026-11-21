"""Vá bản ngang v11 sau chấm độc lập: che thêm ô mờ mềm và thay hình 2 đoạn (s25, s138) bằng bản dựng lại (v12),
chỉ mã hoá lại các khúc giữa hai khung khoá; phần còn lại sao nguyên (cắt bằng -frames:v cho đúng số khung)."""
import subprocess, sys, os
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
SRC = "/home/claude/bmt/patch11/src.mp4"; MINI = "/home/claude/pumdung/testlate/v12/final.mp4"
D = "/home/claude/bmt/patch11"; os.makedirs(D, exist_ok=True); W, H, FPS = 3840, 2160, 30
exec("def soft_hide" + open("/home/claude/pum-studio/tools/dung/render.py").read().split("def soft_hide")[1].split("KEEP_TOGETHER")[0])
F = lambda t: int(round(t * FPS))
TOTAL = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout.strip())
# (khung khoá đầu, khung khoá cuối, [("box", (x,y,w,h), t0, t1) | ("mini", mini_t0, t0, t1)])
P = [(104.333333, 122.2, [("mini", 0.0, 108.333333, 116.466667)]),  # lượt 2: ô che đã vá ở lượt 1; chỉ thay hình 2 đoạn (enable theo t, không theo n)
     (673.866667, 683.933333, [("mini", 8.133333, 678.933333, 683.933333)])]
def sh(c): subprocess.run(c, check=True)
pieces = []; cur = 0
for k, (a, b, ops) in enumerate(P):
    fa, fb = F(a), F(b)
    if fa > cur:
        f = f"{D}/c{k}.mp4"; sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur / FPS:.6f}", "-i", SRC, "-map", "0:v", "-c", "copy", "-frames:v", str(fa - cur), f]); pieces.append(f)
    ins = ["-ss", f"{a:.6f}", "-i", SRC]; fc = []; last = "0:v"; ni = 1
    for j, op in enumerate(ops):
        if op[0] == "box":
            x, y, w, h = op[1]; bx, by = int(x * W) // 2 * 2, int(y * H) // 2 * 2; bw = min(int(w * W) // 2 * 2, W - bx) // 2 * 2; bh = min(int(h * H) // 2 * 2, H - by) // 2 * 2
            fc.append(soft_hide(last, f"o{j}", f"p{j}", bx, by, bw, bh, W, H, op[2] - a, op[3] - a)); last = f"o{j}"
        else:
            m0, t0, t1 = op[1], op[2], op[3]; n = F(t1) - F(t0)
            ins += ["-ss", f"{m0:.6f}", "-i", MINI]
            fc.append(f"[{ni}:v]trim=end_frame={n},setpts=PTS-STARTPTS+{(F(t0) - fa) / FPS:.6f}/TB[m{j}];[{last}][m{j}]overlay=0:0:eof_action=pass:enable='between(t,{(F(t0) - fa - 0.4) / FPS:.4f},{(F(t1) - fa - 0.6) / FPS:.4f})'[o{j}]")
            last = f"o{j}"; ni += 1
    f = f"{D}/e{k}.mp4"
    sh(["ffmpeg", "-y", "-v", "error"] + ins + ["-filter_complex", ";".join(fc), "-map", f"[{last}]", "-frames:v", str(fb - fa),
        "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-video_track_timescale", "15360", f]); pieces.append(f); cur = fb
if cur < TOTAL:
    f = f"{D}/ctail.mp4"; sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur / FPS:.6f}", "-i", SRC, "-map", "0:v", "-c", "copy", f]); pieces.append(f)
open(f"{D}/list.txt", "w").write("".join(f"file '{p}'\n" for p in pieces))
sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{D}/list.txt", "-i", SRC, "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", f"{D}/final_patched.mp4"])
n = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", f"{D}/final_patched.mp4"], capture_output=True, text=True).stdout.strip()
print("xong", TOTAL, n)
