"""Doodle vẽ tay (hình tự vẽ bằng code, không bản quyền) cho video của Pum: nét nâu cocoa, nền hồng/vàng, viền trắng.
doodle(kind, size, seed) -> PIL RGBA. Mỗi kiểu có 3 biến thể rung nhẹ (seed 0,1,2) để làm hiệu ứng "boil" như vẽ tay."""
import math, random
from PIL import Image, ImageDraw, ImageFilter

COCOA = (57, 38, 48, 255); WHITE = (255, 255, 255, 255)
PINK = (255, 208, 227, 255); ROSE = (232, 92, 145, 255); YEL = (255, 210, 90, 255); BROWN = (150, 95, 62, 255)
RED = (226, 64, 64, 255); GREEN = (96, 170, 90, 255); BLUE = (125, 185, 240, 255); CREAM = (255, 248, 245, 255)
KINDS = ["heart", "sparkle", "star", "sun", "coffee", "steam", "swirl", "chili", "cloud", "drop", "arrow", "pin", "bowl", "clock",
         "flower", "tulip", "leaf", "clover", "butterfly", "note", "rainbow", "daisy"]
LAV = (196, 170, 240, 255); ORANGE = (255, 165, 90, 255); MINT = (150, 220, 190, 255)


def _j(rng, p, a):
    return (p[0] + rng.uniform(-a, a), p[1] + rng.uniform(-a, a))


def _wob(rng, pts, a):
    return [_j(rng, p, a) for p in pts]


def _circle(cx, cy, r, n=40):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


def doodle(kind, size=160, seed=0):
    S = size * 3; rng = random.Random(hash((kind, seed)) & 0xffff)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = max(4, int(S * 0.045)); a = S * 0.006
    shapes = []  # (points, fill, closed)

    def poly(pts, fill=None, closed=True): shapes.append((_wob(rng, pts, a), fill, closed))

    def blob(circles, fill):  # hợp nhiều hình tròn/elip thành một khối, chỉ viền ngoài
        import numpy as _np, cv2 as _cv
        mk = _np.zeros((S, S), _np.uint8)
        for cc in circles:
            if len(cc) == 3: _cv.circle(mk, (int(cc[0]), int(cc[1])), int(cc[2]), 255, -1)
            else: _cv.ellipse(mk, (int(cc[0]), int(cc[1])), (int(cc[2]), int(cc[3])), cc[4], 0, 360, 255, -1)
        cs, _ = _cv.findContours(mk, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_NONE)
        for ct in cs:
            pts = [tuple(map(float, q[0])) for q in ct][::4]; poly(pts + [pts[0]], fill)
    c = S / 2
    if kind == "heart":
        pts = [(c + S * 0.026 * 16 * math.sin(t) ** 3, c - S * 0.026 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) + S * 0.03)
               for t in [2 * math.pi * k / 60 for k in range(61)]]
        poly(pts, ROSE); poly([(c - S * .18, c - S * .12), (c - S * .1, c - S * .2)], None, False)
    elif kind == "sparkle":
        for (x, y, r, f) in [(c, c, S * .34, YEL), (c + S * .3, c - S * .28, S * .1, PINK), (c - S * .3, c + S * .26, S * .08, PINK)]:
            pts = []
            for k in range(8):
                ang = math.pi / 4 * k - math.pi / 2; rr = r if k % 2 == 0 else r * 0.28
                pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
            poly(pts + [pts[0]], f)
    elif kind == "star":
        pts = []
        for k in range(10):
            ang = math.pi / 5 * k - math.pi / 2; rr = S * .38 if k % 2 == 0 else S * .16
            pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
        poly(pts + [pts[0]], YEL)
    elif kind == "sun":
        poly(_circle(c, c, S * .2), YEL)
        for k in range(10):
            ang = 2 * math.pi * k / 10
            poly([(c + S * .27 * math.cos(ang), c + S * .27 * math.sin(ang)), (c + S * .4 * math.cos(ang), c + S * .4 * math.sin(ang))], None, False)
        poly([(c - S * .08, c - S * .03), (c - S * .07, c - S * .05)], None, False); poly([(c + S * .07, c - S * .03), (c + S * .08, c - S * .05)], None, False)
        poly([(c - S * .07, c + S * .06), (c, c + S * .1), (c + S * .07, c + S * .06)], None, False)
    elif kind == "coffee":
        poly([(c - S * .25, c - S * .05), (c + S * .2, c - S * .05), (c + S * .16, c + S * .3), (c - S * .21, c + S * .3)], CREAM)
        poly([(c + S * .19, c + S * .02), (c + S * .32, c + S * .03), (c + S * .32, c + S * .16), (c + S * .17, c + S * .18)], None, False)
        poly([(c - S * .2, c), (c + S * .16, c), (c + S * .15, c + S * .06), (c - S * .19, c + S * .06)], BROWN)
        for dx in (-.1, .02):
            poly([(c + S * dx, c - S * .12), (c + S * (dx + .05), c - S * .2), (c + S * dx, c - S * .28), (c + S * (dx + .05), c - S * .36)], None, False)
    elif kind == "steam":
        for dx in (-.16, 0, .16):
            poly([(c + S * dx, c + S * .3), (c + S * (dx + .07), c + S * .15), (c + S * dx, c), (c + S * (dx + .07), c - S * .15), (c + S * dx, c - S * .3)], None, False)
    elif kind == "swirl":
        pts = [(c + S * .012 * t * math.cos(t * .55), c + S * .012 * t * math.sin(t * .55)) for t in [k * 0.5 for k in range(60)]]
        poly(pts, None, False)
    elif kind == "chili":
        cl = [(c - S * .3 + S * .62 * u, c - S * .12 + S * .32 * u * u) for u in [k / 24 for k in range(25)]]
        top, bot = [], []
        for i, (x, y) in enumerate(cl):
            u = i / 24; w = S * .11 * math.sin(math.pi * min(1, u * 1.15 + .05)) ** .7
            if i < 24: dx, dy = cl[i + 1][0] - x, cl[i + 1][1] - y
            L = math.hypot(dx, dy) or 1; nx, ny = -dy / L, dx / L
            top.append((x + nx * w, y + ny * w)); bot.append((x - nx * w, y - ny * w))
        poly(top + bot[::-1] + [top[0]], RED)
        st = [(c - S * .31, c - S * .12), (c - S * .38, c - S * .2), (c - S * .33, c - S * .3)]
        poly(st + [(c - S * .28, c - S * .26), (c - S * .25, c - S * .14), st[0]], GREEN)
    elif kind == "cloud":
        import numpy as _np, cv2 as _cv
        mk = _np.zeros((S, S), _np.uint8)
        for (x, y, r) in [(c - S * .2, c + S * .06, S * .14), (c + S * .0, c - S * .06, S * .2), (c + S * .2, c + S * .05, S * .15), (c - S * .02, c + S * .12, S * .16)]:
            _cv.circle(mk, (int(x), int(y)), int(r), 255, -1)
        cs, _ = _cv.findContours(mk, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)
        pts = [tuple(map(float, p[0])) for p in max(cs, key=_cv.contourArea)][::3]
        poly(pts + [pts[0]], WHITE)
    elif kind == "drop":
        pts = [(c, c - S * .34)] + [(c + S * .2 * math.cos(t), c + S * .1 + S * .2 * math.sin(t)) for t in [-.35 + k * (math.pi + .7) / 20 for k in range(21)]] + [(c, c - S * .34)]
        poly(pts, BLUE); poly([(c - S * .08, c + S * .05), (c - S * .1, c + S * .14)], None, False)
    elif kind == "arrow":
        pts = [(c - S * .34 + S * .62 * u, c + S * .16 - S * .3 * math.sin(math.pi * u)) for u in [k / 20 for k in range(21)]]
        pts = [(x, y) for x, y in pts]; poly(pts, None, False); e = pts[-1]; p0 = pts[-3]
        ang = math.atan2(e[1] - p0[1], e[0] - p0[0])
        h1 = (e[0] - S * .14 * math.cos(ang - .55), e[1] - S * .14 * math.sin(ang - .55)); h2 = (e[0] - S * .14 * math.cos(ang + .55), e[1] - S * .14 * math.sin(ang + .55))
        poly([h1, e, h2], None, False)
    elif kind == "pin":
        pts = [(c, c + S * .38)] + [(c + S * .22 * math.cos(t), c - S * .08 + S * .22 * math.sin(t)) for t in [math.pi * .78 + k * (math.pi * 1.44) / 30 for k in range(31)]] + [(c, c + S * .38)]
        poly(pts, ROSE); poly(_circle(c, c - S * .08, S * .08), CREAM)
    elif kind == "bowl":
        pts = [(c - S * .34, c)] + [(c + S * .34 * math.cos(t), c + S * .3 * math.sin(t)) for t in [k * math.pi / 20 for k in range(21)]][::-1] + [(c + S * .34, c)]
        poly([(c - S * .34, c), (c + S * .34, c)] + [(c + S * .34 * math.cos(t), c + S * .3 * math.sin(t)) for t in [k * math.pi / 20 for k in range(21)]] + [(c - S * .34, c)], PINK)
        poly([(c + S * .05, c - S * .02), (c + S * .36, c - S * .36)], None, False); poly([(c + S * .14, c - S * .02), (c + S * .42, c - S * .3)], None, False)
        for dx in (-.16, -.04):
            poly([(c + S * dx, c - S * .08), (c + S * (dx + .04), c - S * .18), (c + S * dx, c - S * .28)], None, False)
    elif kind == "clock":
        poly(_circle(c, c, S * .32), CREAM); poly([(c, c), (c, c - S * .2)], None, False); poly([(c, c), (c + S * .14, c + S * .06)], None, False)
        poly([(c - S * .3, c - S * .34), (c - S * .4, c - S * .24)], None, False); poly([(c + S * .3, c - S * .34), (c + S * .4, c - S * .24)], None, False)
    elif kind in ("flower", "daisy"):
        n = 5 if kind == "flower" else 9
        if kind == "flower":
            blob([(c + S * .17 * math.cos(2 * math.pi * k / n - math.pi / 2), c + S * .17 * math.sin(2 * math.pi * k / n - math.pi / 2), S * .15) for k in range(n)], PINK)
        else:
            blob([(c + S * .2 * math.cos(2 * math.pi * k / n), c + S * .2 * math.sin(2 * math.pi * k / n), S * .14, S * .07, math.degrees(2 * math.pi * k / n)) for k in range(n)], WHITE)
        poly(_circle(c, c, S * .1, 24), YEL)
    elif kind == "tulip":
        poly([(c, c + S * .05), (c - S * .02, c + S * .4)], None, False)
        lf = [(c - S * .01, c + S * .34), (c - S * .2, c + S * .14), (c - S * .16, c + S * .3), (c - S * .01, c + S * .38)]
        poly(lf + [lf[0]], GREEN)
        cup = [(c - S * .18, c - S * .3), (c - S * .09, c - S * .16), (c, c - S * .32), (c + S * .09, c - S * .16), (c + S * .18, c - S * .3),
               (c + S * .17, c - S * .02), (c + S * .08, c + S * .08), (c - S * .08, c + S * .08), (c - S * .17, c - S * .02)]
        poly(cup + [cup[0]], ROSE)
    elif kind == "leaf":
        pts = [(c - S * .3, c + S * .3)] + [(c - S * .3 + S * .6 * u, c + S * .3 - S * .6 * u - S * .22 * math.sin(math.pi * u)) for u in [k / 16 for k in range(17)]]
        pts += [(c - S * .3 + S * .6 * u, c + S * .3 - S * .6 * u + S * .22 * math.sin(math.pi * u)) for u in [k / 16 for k in range(16, -1, -1)]]
        poly(pts, GREEN); poly([(c - S * .3, c + S * .3), (c + S * .25, c - S * .25)], None, False)
    elif kind == "clover":
        blob([(c + S * .14 * math.cos(ang), c - S * .04 + S * .14 * math.sin(ang), S * .13) for ang in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6)], MINT)
        poly([(c, c + S * .08), (c + S * .06, c + S * .38)], None, False)
    elif kind == "butterfly":
        blob([(c - S * .17, c - S * .1, S * .15), (c - S * .13, c + S * .14, S * .1)], PINK)
        blob([(c + S * .17, c - S * .1, S * .15), (c + S * .13, c + S * .14, S * .1)], LAV)
        poly([(c, c - S * .22), (c, c + S * .24)], None, False)
        poly([(c, c - S * .22), (c - S * .08, c - S * .36)], None, False); poly([(c, c - S * .22), (c + S * .08, c - S * .36)], None, False)
    elif kind == "note":
        poly(_circle(c - S * .14, c + S * .22, S * .1, 24), ROSE); poly(_circle(c + S * .16, c + S * .14, S * .1, 24), ROSE)
        poly([(c - S * .05, c + S * .22), (c - S * .05, c - S * .26), (c + S * .25, c - S * .34), (c + S * .25, c + S * .14)], None, False)
    elif kind == "rainbow":
        outer = [(c + S * .38 * math.cos(t), c + S * .16 - S * .38 * math.sin(t)) for t in [math.pi * j / 30 for j in range(31)]]
        inner = [(c + S * .12 * math.cos(t), c + S * .16 - S * .12 * math.sin(t)) for t in [math.pi * j / 30 for j in range(30, -1, -1)]]
        poly(outer + inner + [outer[0]], WHITE)
        bands = []
        for k, col in enumerate([ROSE, ORANGE, YEL, MINT, BLUE]):
            r = S * (.335 - k * .05)
            bands.append(([(c + r * math.cos(t), c + S * .16 - r * math.sin(t)) for t in [math.pi * j / 30 for j in range(31)]], col))
        blob([(c - S * .3, c + S * .18, S * .09), (c - S * .22, c + S * .2, S * .07)], WHITE); blob([(c + S * .3, c + S * .18, S * .09), (c + S * .22, c + S * .2, S * .07)], WHITE)
    else:
        raise ValueError(kind)
    # vẽ: viền trắng dày (dễ thấy trên mọi nền) → màu nền → nét cocoa
    for pts, fill, closed in shapes:
        if fill: d.polygon(pts, fill=WHITE)
        d.line(pts, fill=WHITE, width=lw * 3, joint="curve")
    for pts, fill, closed in shapes:
        if fill: d.polygon(pts, fill=fill)
        if kind == "rainbow" and fill == WHITE and len(pts) > 40 and not locals().get("_bdone"):
            for bp, col in bands: d.line(bp, fill=col, width=int(S * .05), joint="curve")
            _bdone = True
    for pts, fill, closed in shapes:
        d.line(pts, fill=COCOA, width=lw, joint="curve")
        for p in (pts[0], pts[-1]):
            d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=COCOA)
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.paste((57, 38, 48, 70), (0, 0), im.split()[3])
    out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(S * .02)), (int(S * .015), int(S * .025))); out.alpha_composite(im)
    return out.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    sheet = Image.new("RGBA", (180 * len(KINDS), 540), (250, 220, 232, 255))
    for i, k in enumerate(KINDS):
        for s in range(3): sheet.alpha_composite(doodle(k, 170, s), (i * 180 + 5, s * 180 + 5))
    sheet.convert("RGB").save(sys.argv[1] if len(sys.argv) > 1 else "/tmp/doodles.png")
