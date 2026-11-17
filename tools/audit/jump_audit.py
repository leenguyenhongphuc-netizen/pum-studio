# Kiểm "giật trang" khi bấm chọn: thanh bước Dựng, thanh chương (Dựng và Quay).
# Đạt khi: thanh vừa bấm đứng yên trên màn hình (lệch <= 2px, đo ngay và sau 1,5 giây),
# và thanh chọn ngang không tự trượt khi nút được chọn vẫn đang nằm trong khung nhìn.
# Chạy: python3 -m http.server 8770 ở thư mục web, rồi PUM_PASS=... python3 jump_audit.py
import asyncio, json, os
from playwright.async_api import async_playwright
ROWS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_rows.json")))
DEV = [("p412",412,915),("i390",390,844),("t820",820,1180),("t1180",1180,820),("d1366",1366,768),("d1920",1920,1080)]
POS = "(s)=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [Math.round(r.top),Math.round(e.scrollLeft)]}"
async def page(b, w, h):
    ctx = await b.new_context(viewport={"width":w,"height":h}); pg = await ctx.new_page()
    async def hd(route):
        u = route.request.url
        body = "true" if "pum_check" in u else json.dumps(ROWS) if "pum_list" in u else "null"
        await route.fulfill(status=200, body=body, headers={"content-type":"application/json","access-control-allow-origin":"*","access-control-allow-headers":"*"})
    await pg.route("**/rest/v1/rpc/**", hd)
    await pg.goto("http://localhost:8770/"); await pg.fill("#gatePass", os.environ["PUM_PASS"]); await pg.click("#gateBtn"); await pg.wait_for_timeout(2500)
    return ctx, pg
async def clicks(pg, bar, items):
    bad = []
    await pg.evaluate(f"(()=>{{const e=document.querySelector('{bar}');window.scrollTo(0,e.getBoundingClientRect().top+scrollY-200)}})()"); await pg.wait_for_timeout(300)
    for it in items:
        b0 = await pg.evaluate(POS, bar)
        btn = pg.locator(it).first
        inview = await btn.evaluate("e=>{const p=e.parentElement.getBoundingClientRect(),r=e.getBoundingClientRect();return r.left>=p.left&&r.right<=p.right}")
        await btn.click(); await pg.wait_for_timeout(60); b1 = await pg.evaluate(POS, bar); await pg.wait_for_timeout(1500); b2 = await pg.evaluate(POS, bar)
        if b1 is None or abs(b1[0]-b0[0]) > 2 or abs(b2[0]-b0[0]) > 2: bad.append((it, "nhảy dọc", b0[0], b1 and b1[0], b2 and b2[0]))
        if inview and b1 and b1[1] != b0[1]: bad.append((it, "thanh ngang tự trượt", b0[1], b1[1]))
    return bad
async def main():
    async with async_playwright() as p:
        for eng in ["ch","wk"]:
            b = await (p.webkit.launch() if eng=="wk" else p.chromium.launch(executable_path="/usr/bin/google-chrome"))
            for name,w,h in (DEV if eng=="ch" else [DEV[1],DEV[2]]):
                ctx, pg = await page(b, w, h); res = {}
                await pg.goto("http://localhost:8770/#/san-xuat/test"); await pg.wait_for_timeout(1200)
                await pg.click("[data-tab=quay]"); await pg.wait_for_timeout(800)
                res["quay"] = await clicks(pg, ".daypick", [".daypick [data-sec] >> nth=1", ".daypick [data-sec] >> nth=2", ".daypick [data-sec] >> nth=0"])
                await pg.click("[data-tab=dang]"); await pg.wait_for_timeout(1000)
                res["buoc"] = await clicks(pg, ".stepper", [".stepper [data-step='2']", ".stepper [data-step='3']", ".stepper [data-step='4']", ".stepper [data-step='1']"])
                res["chuong"] = await clicks(pg, "#stepBody .daypick", ["#stepBody [data-dsec] >> nth=1", "#stepBody [data-dsec] >> nth=2", "#stepBody [data-dsec] >> nth=0"])
                print(eng, name, "ĐẠT" if not any(res.values()) else res)
                await ctx.close()
            await b.close()
asyncio.run(main())
