#!/bin/bash
# Dựng loạt TikTok dọc từ bản ngang đã ghép prep (edl_v8m.json). Chạy: setsid nohup bash run_tiktok.sh [1 2 ...] > tt.log 2>&1 < /dev/null &
set -u
cd /home/claude/bmt
: python3 build_tiktok.py /home/claude/pumdung/testlate/edl_v8m.json /home/claude/pumdung/testlate/tt || exit 1
PARTS="${@:-1 2 3 4 5 6 7}"
cd /home/claude/pum-studio/tools/dung
for n in $PARTS; do
  echo "=== Phần $n $(date +%H:%M:%S)"
  PUM_CRF=20 PUM_PRESET=veryfast python3 -I render.py testlate /home/claude/pumdung/testlate/tt/tt$n.json 2>&1 | grep -v "WARN\|feedback tensors\|TfLite\|INFO:" | tail -4
  python3 /home/claude/bmt/fixaudio.py /home/claude/pumdung/testlate/v$((100 + n))/final.mp4 256
  python3 -I qa.py testlate $((100 + n)) 2>&1 | python3 -c "import json,sys; r=json.load(sys.stdin); print('QA', r['size'], r['dur'], r['lufs'], r['true_peak'], 'pass' if r['pass'] else r['checks'])"
done
echo "=== xong $(date +%H:%M:%S)"
