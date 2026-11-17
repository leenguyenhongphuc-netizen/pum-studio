# Kiểm giao diện bước Dựng trên 6 cỡ màn hình + WebKit, chặn mạng thật bằng dữ liệu giả.
# Chạy: python3 -m http.server 8770 (ở thư mục web có bản nháp giả) rồi PUM_PASS=... python3 dung_audit.py p412 t820 d1920
import asyncio, json, sys, os
from playwright.async_api import async_playwright
ROWS=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'mock_rows.json')))
DEV=[("p412",412,915),("i390",390,844),("t820",820,1180),("t1180",1180,820),("t1280",1280,800),("d1366",1366,768),("d1920",1920,1080)]
METRIC="""()=>{const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};
const small=[...document.querySelectorAll('#view button,#view a,#view label.btn,#view input:not([type=file]),#view textarea,#view summary,#view [role=button]')].filter(vis).filter(e=>{const r=e.getBoundingClientRect();return r.height<44||(r.width<44&&!e.matches('a:not(.btn)'))}).map(e=>(e.className||e.tagName).toString().slice(0,24)+':'+Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height));
const tiny=[...document.querySelectorAll('#view *')].filter(e=>e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())&&vis(e)&&parseFloat(getComputedStyle(e).fontSize)<12).map(e=>(e.className||e.tagName).toString().slice(0,20)+':'+getComputedStyle(e).fontSize);
return {overflow:document.documentElement.scrollWidth>innerWidth, small:[...new Set(small)].slice(0,14), tiny:[...new Set(tiny)].slice(0,8)}}"""
async def run(p, engine, dev, shots):
    b = await (p.webkit.launch() if engine=="wk" else p.chromium.launch(executable_path="/usr/bin/google-chrome"))
    out={}
    for name,w,h in dev:
        ctx=await b.new_context(viewport={"width":w,"height":h}); pg=await ctx.new_page(); errs=[]
        pg.on("pageerror",lambda e: errs.append(str(e)))
        rows=[dict(r) for r in ROWS]
        async def hd(route):
            u=route.request.url; body="[]"
            if "pum_check" in u: body="true"
            elif "pum_list" in u: body=json.dumps(rows)
            elif "pum_put" in u:
                a=json.loads(route.request.post_data); hit=[r for r in rows if r["col"]==a["c"] and r["id"]==a["i"]]
                if hit: hit[0]["data"]=a["d"]; hit[0]["updated_at"]=str(float(hit[0]["updated_at"])+1)
                else: rows.append({"col":a["c"],"id":a["i"],"data":a["d"],"updated_at":"1"})
                body="null"
            await route.fulfill(status=200, body=body, headers={"content-type":"application/json","access-control-allow-origin":"*","access-control-allow-headers":"*"})
        await pg.route("**/rest/v1/rpc/**", hd)
        await pg.goto("http://localhost:8770/"); await pg.fill("#gatePass",os.environ["PUM_PASS"]); await pg.click("#gateBtn"); await pg.wait_for_timeout(2500)
        await pg.goto("http://localhost:8770/#/san-xuat/test"); await pg.wait_for_timeout(1200)
        await pg.click("[data-tab=dang]"); await pg.wait_for_timeout(1000)
        r={}
        for s in [1,2,3,4]:
            await pg.click(f".stepper [data-step='{s}']"); await pg.wait_for_timeout(1500 if s>2 else 600)
            if s==1:
                await pg.click("[data-dsec='ttests1']"); await pg.wait_for_timeout(400)
                await pg.set_input_files("input[data-addkey='ttests1b1'][accept='video/*']", ["/home/claude/fake/canh_tuong.mp4"]); await pg.wait_for_timeout(2500)
                if await pg.query_selector("input[data-addkey='ttests1b1'][accept='audio/*']"): await pg.set_input_files("input[data-addkey='ttests1b1'][accept='audio/*']", ["/home/claude/fake/long_tieng.m4a"]); await pg.wait_for_timeout(2500)
            if s==4:
                await pg.click("#openDraft"); await pg.wait_for_timeout(2500)
                await pg.click(".tb.vs >> nth=1"); await pg.wait_for_timeout(500)
                await pg.click("#subBox summary"); await pg.wait_for_timeout(300)
            r[s]=await pg.evaluate(METRIC)
            if name in shots: await pg.screenshot(path=f"/tmp/au_{engine}_{name}_{s}.png", full_page=True)
        r["errs"]=errs; out[name]=r; await ctx.close()
    await b.close(); return out
async def main():
    async with async_playwright() as p:
        res={"ch":await run(p,"ch",DEV,sys.argv[1:]), "wk":await run(p,"wk",[DEV[1],DEV[2]],sys.argv[1:])}
    json.dump(res,open('/tmp/audit.json','w'),ensure_ascii=False,indent=1)
    for e,d in res.items():
        for n,r in d.items():
            print(e,n,"errs",r["errs"])
            for s in [1,2,3,4]: print("  b",s,"ovf",r[s]["overflow"],"small",r[s]["small"],"tiny",r[s]["tiny"])
asyncio.run(main())
