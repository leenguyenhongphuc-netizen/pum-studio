"""Vá bản ngang 4K đã xuất: che mờ mềm thêm vài ô (toạ độ khung ra) chỉ trong các đoạn giữa hai khung khoá, phần còn lại sao nguyên."""
import subprocess, sys, json, os
sys.path.insert(0, "/home/claude/pum-studio/tools/dung")
src = "/home/claude/pumdung/testlate/v9/final.mp4"; D = "/home/claude/bmt/patch9"; W, H = 3840, 2160
exec("def soft_hide" + open("/home/claude/pum-studio/tools/dung/render.py").read().split("def soft_hide")[1].split("KEEP_TOGETHER")[0])
END = 697.5
# (đầu, cuối, [(x,y,w,h tỉ lệ khung ra, giây đầu, giây cuối theo dòng thời gian)])
P = [(104.333333, 116.466667, [((0.0, 0.58, 0.15, 0.13), 108.33, 113.53)]),
     (317.966667, 324.833333, [((0.86, 0.48, 0.13, 0.09), 317.97, 319.27), ((0.74, 0.47, 0.12, 0.08), 318.97, 321.97)]),
     (678.933333, None, [((0.83, 0.47, 0.14, 0.11), 683.93, 691.47)])]
pieces = []; cur = 0.0
def sh(c): subprocess.run(c, check=True)
for k, (a, b, boxes) in enumerate(P):
    if a > cur:
        f = f"{D}/c{k}.mp4"; sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur:.6f}", "-i", src, "-t", f"{a - cur:.6f}", "-map", "0:v", "-c", "copy", f]); pieces.append(f)
    fc = []; last = "0:v"
    for j, ((x, y, w, h), s0, s1) in enumerate(boxes):
        bx, by = int(x * W) // 2 * 2, int(y * H) // 2 * 2; bw, bh = int(w * W) // 2 * 2, int(h * H) // 2 * 2
        bw = min(bw, W - bx) // 2 * 2
        fc.append(soft_hide(last, f"o{j}", f"p{j}", bx, by, bw, bh, W, H, s0 - a, s1 - a)); last = f"o{j}"
    f = f"{D}/e{k}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.6f}", "-i", src] + (["-t", f"{b - a:.6f}"] if b else []) + \
          ["-filter_complex", ";".join(fc), "-map", f"[{last}]", "-c:v", "libx264", "-preset", "faster", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-video_track_timescale", "15360", f]
    sh(cmd); pieces.append(f); cur = b if b else END
if cur < END - 0.05:
    f = f"{D}/ctail.mp4"; sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur:.6f}", "-i", src, "-map", "0:v", "-c", "copy", f]); pieces.append(f)
open(f"{D}/list.txt", "w").write("".join(f"file '{p}'\n" for p in pieces))
sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", f"{D}/list.txt", "-i", src, "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", f"{D}/final_patched.mp4"])
print("xong", pieces)
