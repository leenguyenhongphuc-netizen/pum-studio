"""Chuẩn tiếng bản cuối: đưa về -14 LUFS, đỉnh thật ≤ -1,5 dBTP (2 lượt loudnorm), giữ nguyên hình. python3 fixaudio.py final.mp4 [aac_kbps]"""
import json, re, subprocess, sys, os
f = sys.argv[1]; kb = sys.argv[2] if len(sys.argv) > 2 else "256"
r = subprocess.run(["ffmpeg", "-nostats", "-i", f, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
m = json.loads(r[r.rfind("{"):r.rfind("}") + 1])
af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
      "aresample=192000,alimiter=limit=0.79:attack=1:release=50:level=disabled,aresample=48000")
tmp = f[:-4] + ".fix.mp4"
tag = ["-tag:v", "hvc1"] if "hevc" in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", f], capture_output=True, text=True).stdout else []
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-map", "0:v", "-map", "0:a", "-c:v", "copy", *tag, "-af", af, "-c:a", "aac", "-b:a", kb + "k", "-movflags", "+faststart", tmp], check=True)
os.replace(tmp, f); print("tiếng đã chuẩn:", f, "trước", m["input_i"], "LUFS", m["input_tp"], "dBTP")
