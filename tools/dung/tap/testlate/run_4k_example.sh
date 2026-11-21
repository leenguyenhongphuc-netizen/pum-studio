#!/bin/bash
cd /home/claude/pum-studio/tools/dung
(
  echo "=== Phần 2 (dựng lại) $(date +%H:%M)"
  PUM_SEG_CRF=17 PUM_CRF=18 PUM_PRESET=fast python3 -I render.py testlate /home/claude/pumdung/testlate/tt4k/tt2.json > /home/claude/bmt/render_tt2.log 2>&1
  grep -v "WARN\|feedback\|TfLite\|INFO" /home/claude/bmt/render_tt2.log | tail -2 | cut -c1-300
  python3 /home/claude/bmt/fixaudio.py /home/claude/pumdung/testlate/v112/final.mp4 256
  python3 -I qa.py testlate 112 2>/dev/null | python3 -c "import json,sys; r=json.load(sys.stdin); print('QA', r['size'], r['dur'], r['lufs'], r['true_peak'], 'pass' if r['pass'] else r['checks'])"
  rm -rf /home/claude/pumdung/testlate/v112/tmp
  echo "=== Phần 2 xong $(date +%H:%M)"
) &
while pgrep -f "render.py testlate /home/claude/pumdung/testlate/edl_4k.json" > /dev/null; do sleep 30; done
grep -v "WARN\|feedback\|TfLite\|INFO" /home/claude/bmt/render_v10.log | tail -2 | cut -c1-300
rm -rf /home/claude/pumdung/testlate/v10/tmp
python3 /home/claude/bmt/fixaudio.py /home/claude/pumdung/testlate/v10/final.mp4 256
python3 -I qa.py testlate 10 > /home/claude/bmt/qa10.json 2>/dev/null
echo "=== ngang v10 xong $(date +%H:%M)"
wait
find /home/claude/pumdung/testlate/segcache -type f -links 1 -delete
echo "=== XONG TẤT CẢ $(date +%H:%M)"
