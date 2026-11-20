import json, subprocess, numpy as np
F='/home/claude/pumdung/testlate/v8/final.mp4'; TL=json.load(open('/home/claude/pumdung/testlate/v8/timeline.json'))
E={s['id']:s for s in json.load(open('/home/claude/pumdung/testlate/edl_v8m.json'))['segments']}
# decode the whole final audio once (no seeking)
raw=subprocess.run(["ffmpeg","-v","error","-i",F,"-vn","-ac","1","-ar","16000","-af","highpass=f=300,lowpass=f=3400","-f","s16le","-"],capture_output=True).stdout
A=np.frombuffer(raw,np.int16).astype(float); hop=80; n=len(A)//hop; EF=np.log1p(np.sqrt((A[:n*hop].reshape(n,hop)**2).mean(1)))
def aud(src, dur):
    r=subprocess.run(["ffmpeg","-v","error","-i",src,"-t",f"{dur:.3f}","-vn","-ac","1","-ar","16000","-af","highpass=f=300,lowpass=f=3400","-f","s16le","-"],capture_output=True).stdout
    a=np.frombuffer(r,np.int16).astype(float); m=len(a)//hop; return np.log1p(np.sqrt((a[:m*hop].reshape(m,hop)**2).mean(1)))
for k,t in enumerate(TL['segments']):
    s=E.get(t['id'])
    if not s or s.get('audio')!='src' or s.get('voice')!='noi' or t['end']-t['start']<4 or k%5: continue
    ep=aud(s['path'], t['end']-t['start']); x=ep[40:-40]; i0=int((t['start']-1)/0.005)
    seg=EF[i0:i0+len(x)+400]
    best=max((np.corrcoef(x, seg[j:j+len(x)])[0,1],j) for j in range(0,len(seg)-len(x)))
    print(f"{t['id']:6s} T={t['start']:7.2f} tiếng lệch {(best[1]-200)*0.005:+.3f}s r={best[0]:.2f}")
