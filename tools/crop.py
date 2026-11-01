# -*- coding: utf-8 -*-
"""Dark-line crop renderer for visual identification of drawing regions."""
import json, sys, math
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))
LAB = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))

def render(x0, y0, x1, y1, out, px=1600, labels=True):
    W, H = x1 - x0, y1 - y0
    S = px / W
    PH = int(H * S)
    SS = 2
    img = Image.new('RGB', (px * SS, PH * SS), 'white')
    dr = ImageDraw.Draw(img)
    def TX(x): return (x - x0) * S * SS
    def TY(y): return (y1 - y) * S * SS
    try:
        F = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 8 * SS)
    except Exception:
        F = None
    def bl(p, q, b, n=12):
        if abs(b) < 1e-9: return [p, q]
        dx, dy = q[0] - p[0], q[1] - p[1]
        c = math.hypot(dx, dy)
        if c < 1e-12: return [p, q]
        th = 4 * math.atan(b)
        r = c / (2 * math.sin(abs(th) / 2))
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        d = r * math.cos(abs(th) / 2)
        ux, uy = -dy / c, dx / c
        sg = 1 if b > 0 else -1
        cx, cy = mx + ux * d * sg, my + uy * d * sg
        a0 = math.atan2(p[1] - cy, p[0] - cx)
        return [(cx + r * math.cos(a0 + th * i / n), cy + r * math.sin(a0 + th * i / n)) for i in range(n + 1)]
    for e in ENTS:
        t = e['type']
        try:
            if t == 'LINE':
                a, b = e['start'], e['end']
                if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1:
                    continue
                dr.line([TX(a[0]), TY(a[1]), TX(b[0]), TY(b[1])], fill=(40, 40, 40), width=1)
            elif t in ('LWPOLYLINE', 'POLYLINE'):
                vs = e.get('vertices') or []
                pts = []
                for i in range(len(vs) - 1):
                    pts += bl(vs[i][:2], vs[i + 1][:2], vs[i][2] if len(vs[i]) > 2 else 0)
                if e.get('closed') and len(vs) > 2:
                    pts += bl(vs[-1][:2], vs[0][:2], vs[-1][2] if len(vs[-1]) > 2 else 0)
                if len(pts) > 1:
                    dr.line([(TX(p[0]), TY(p[1])) for p in pts], fill=(40, 40, 40), width=1)
            elif t == 'CIRCLE':
                c, r = e['center'], e['radius']
                if not (x0 - r < c[0] < x1 + r and y0 - r < c[1] < y1 + r):
                    continue
                dr.ellipse([TX(c[0] - r), TY(c[1] + r), TX(c[0] + r), TY(c[1] - r)], outline=(40, 40, 40))
        except Exception:
            pass
    if labels:
        for l in LAB:
            if not (x0 < l['x'] < x1 and y0 < l['y'] < y1):
                continue
            if F:
                dr.text((TX(l['x']), TY(l['y'])), l['t'][:22], fill=(180, 0, 0), font=F)
    if F:
        dr.text((6, 6), f"x[{x0},{x1}] y[{y0},{y1}]", fill=(0, 0, 180), font=F)
    img = img.resize((px, PH), Image.LANCZOS)
    img.save(out)
    print('saved', out, img.size)

if __name__ == '__main__':
    a = sys.argv
    if a[1] == 'main':
        render(2901620, 2549020, 2902030, 2549200, r'D:\test\.dwgconv\crop_main2.png', 1700)
    elif a[1] == 'east':
        render(2902030, 2549150, 2902200, 2549320, r'D:\test\.dwgconv\crop_east.png', 1400)
    elif a[1] == 'west':
        render(2901600, 2548940, 2901900, 2549000, r'D:\test\.dwgconv\crop_west.png', 1600)
    elif a[1] == 'south':
        render(2902150, 2548980, 2902500, 2549200, r'D:\test\.dwgconv\crop_south.png', 1500)
