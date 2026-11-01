# -*- coding: utf-8 -*-
"""Rasterize DWG entities (extracted to entities.json) into PNG for visual inspection."""
import json, math, sys, os
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))

FONT_CANDIDATES = [
    r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\simsun.ttc', r'C:\Windows\Fonts\Deng.ttf',
]
def get_font(size):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()

def arc_points(cx, cy, r, a0, a1, steps=24):
    # angles in degrees CCW from +X
    if a1 < a0:
        a1 += 360
    span = a1 - a0
    n = max(2, int(steps * span / 360) + 2)
    return [(cx + r * math.cos(math.radians(a0 + span * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + span * i / (n - 1)))) for i in range(n)]

def bulge_seg(p0, p1, bulge, steps=16):
    if not bulge:
        return [p0, p1]
    (x0, y0), (x1, y1) = p0, p1
    dx, dy = x1 - x0, y1 - y0
    chord = math.hypot(dx, dy)
    if chord < 1e-9:
        return [p0, p1]
    theta = 4 * math.atan(abs(bulge))
    r = chord / (2 * math.sin(theta / 2))
    # center
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    h = r * math.cos(theta / 2)
    ux, uy = -dy / chord, dx / chord
    sign = 1 if bulge > 0 else -1
    cx, cy = mx + ux * h * sign, my + uy * h * sign
    a0 = math.degrees(math.atan2(y0 - cy, x0 - cx))
    a1 = math.degrees(math.atan2(y1 - cy, x1 - cx))
    if bulge > 0:
        while a1 < a0:
            a1 += 360
    else:
        while a1 > a0:
            a1 -= 360
    n = steps
    return [(cx + abs(r) * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + abs(r) * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]

def render(bbox, out_png, width_px=2000, show_text=True, font_px=0, line_color=(30, 40, 60),
           bg=(255, 255, 255), text_color=(200, 30, 30), title=None, extra_polys=None):
    x0, y0, x1, y1 = bbox
    scale = width_px / (x1 - x0)
    height_px = int((y1 - y0) * scale)
    SS = 2  # supersample
    img = Image.new('RGB', (width_px * SS, height_px * SS), bg)
    d = ImageDraw.Draw(img)
    def T(p):
        return ((p[0] - x0) * scale * SS, (y1 - p[1]) * scale * SS)
    lw = max(1, int(SS * 1))

    counts = {}
    for e in ENTS:
        t = e['type']
        try:
            if t == 'LINE':
                a, b = e['start'], e['end']
                if not (x0 - 50 < a[0] < x1 + 50 and x0 - 50 < b[0] < x1 + 50):
                    continue
                d.line([T(a), T(b)], fill=line_color, width=lw)
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                vs = e.get('vertices') or []
                if len(vs) < 2:
                    continue
                if not (x0 - 50 < vs[0][0] < x1 + 50):
                    continue
                pts = []
                for i in range(len(vs) - 1):
                    pts += bulge_seg(vs[i][:2], vs[i + 1][:2], vs[i][2] if len(vs[i]) > 2 else 0)
                if e.get('closed') and len(vs) > 2:
                    pts += bulge_seg(vs[-1][:2], vs[0][:2], vs[-1][2] if len(vs[-1]) > 2 else 0)
                d.line([T(p) for p in pts], fill=line_color, width=lw)
            elif t == 'CIRCLE':
                c, r = e['center'], e['radius']
                if not (x0 - r < c[0] < x1 + r):
                    continue
                bb = [T((c[0] - r, c[1] + r)), T((c[0] + r, c[1] - r))]
                d.ellipse([bb[0][0], bb[0][1], bb[1][0], bb[1][1]], outline=line_color, width=lw)
            elif t == 'ARC':
                c, r = e['center'], e['radius']
                if not (x0 - r < c[0] < x1 + r):
                    continue
                pts = arc_points(c[0], c[1], r, e['startAngle'], e['endAngle'])
                d.line([T(p) for p in pts], fill=line_color, width=lw)
            elif t == 'SOLID':
                counts['SOLID'] = counts.get('SOLID', 0) + 1
        except Exception:
            pass

    if extra_polys:
        for poly, col in extra_polys:
            d.line([T(p) for p in poly], fill=col, width=lw * 2)

    if show_text:
        fp = font_px or max(9, int(11 * SS * width_px / 2000))
        font = get_font(fp)
        for e in ENTS:
            if e['type'] not in ('TEXT', 'MTEXT', 'ATTRIB'):
                continue
            p = e.get('position')
            txt = (e.get('text') or '').strip()
            if not p or not txt:
                continue
            if not (x0 < p[0] < x1 and y0 < p[1] < y1):
                continue
            px, py = T(p)
            d.text((px, py - fp), txt.replace('\\P', ' ')[:40], font=font, fill=text_color)

    img = img.resize((width_px, height_px), Image.LANCZOS)
    if title:
        pass
    img.save(out_png)
    print('wrote', out_png, img.size)
    return img

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    A = (2900800, 2548280, 2902820, 2549760)
    B = (2910650, 2534480, 2911780, 2535060)
    if mode in ('all', 'A'):
        render(A, r'D:\test\.dwgconv\view_A.png', 2200)
    if mode in ('all', 'B'):
        render(B, r'D:\test\.dwgconv\view_B.png', 2200)
    if mode == 'zoom':
        bb = tuple(float(v) for v in sys.argv[2:6])
        render(bb, sys.argv[6], 2000, font_px=16)
