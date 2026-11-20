#!/bin/bash
# Bản dọc đã dựng + QA xong: xoá cả thư mục tmp và các đoạn dọc trong segcache không còn ai dùng (đoạn ngang giữ nguyên).
end=$((SECONDS + 10800))
while [ $SECONDS -lt $end ]; do
  for d in /home/claude/pumdung/testlate/v10[1-7]; do
    if [ -f "$d/qa/qa.json" ] && [ -f "$d/final.mp4" ] && [ -d "$d/tmp" ]; then rm -rf "$d/tmp"; fi
  done
  find /home/claude/pumdung/testlate/segcache -newermt "2026-11-20 17:46:50" -type f -links 1 -mmin +2 -delete
  rm -f /home/claude/pumdung/testlate/v7/tmp/mix.wav 2>/dev/null
  sleep 60
done
