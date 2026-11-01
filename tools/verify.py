# -*- coding: utf-8 -*-
"""Verification plot: overlay plant-data.js structures on the original DWG linework."""
import json, sys, math, re
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SRC = ''
DATA = json.load(open(r'D:\test\.dwgconv\plant-data.json', encoding='utf-8'))
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))

x0, y0, x1, y1 = 2901050, 2548500, 2902450, 2549600
PX = 2000
W, H = x1 - x0, y1 - y0
S = PX / W
PH = int(H * S)
SS = 2
img = Image.new('RGB', (PX * SS, PH * SS), 'white')
dr = ImageDraw.Draw(img)
def TX(x): return (x - x0) * S * SS
def TY(y): return (y1 - y) * S * SS
try:
    FONT = ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc', 9 * SS)
except Exception:
    FONT = None

def bl(p, q, b, n=16):
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
            dr.line([TX(a[0]), TY(a[1]), TX(b[0]), TY(b[1])], fill=(200, 200, 200), width=1)
        elif t in ('LWPOLYLINE', 'POLYLINE'):
            vs = e.get('vertices') or []
            pts = []
            for i in range(len(vs) - 1):
                pts += bl(vs[i][:2], vs[i + 1][:2], vs[i][2] if len(vs[i]) > 2 else 0)
            if e.get('closed') and len(vs) > 2:
                pts += bl(vs[-1][:2], vs[0][:2], vs[-1][2] if len(vs[-1]) > 2 else 0)
            if len(pts) > 1:
                dr.line([(TX(p[0]), TY(p[1])) for p in pts], fill=(205, 205, 205), width=1)
        elif t == 'CIRCLE':
            c, r = e['center'], e['radius']
            dr.ellipse([TX(c[0] - r), TY(c[1] + r), TX(c[0] + r), TY(c[1] - r)], outline=(215, 215, 215))
    except Exception:
        pass

COL = {'main': (200, 40, 40), 'electrical': (30, 90, 200), 'cooling': (0, 150, 160), 'coal': (120, 80, 20),
       'aux': (150, 40, 160), 'living': (230, 140, 0), 'construction': (110, 160, 110)}

for s in DATA['structures']:
    c = COL.get(s['cat'], (0, 0, 0))
    sh = s['shape']
    if sh in ('hyperbolic', 'dome', 'tank'):
        r = s['d'] / 2
        dr.ellipse([TX(s['x'] - r), TY(s['y'] + r), TX(s['x'] + r), TY(s['y'] - r)], outline=c, width=2 * SS)
        dr.line([TX(s['x'] - r), TY(s['y']), TX(s['x'] + r), TY(s['y'])], fill=c, width=SS)
    elif sh == 'chimney':
        r = s['d'] / 2
        dr.ellipse([TX(s['x'] - r), TY(s['y'] + r), TX(s['x'] + r), TY(s['y'] - r)], outline=c, width=2 * SS)
    else:
        w = s.get('w', 20); d = s.get('d', 20)
        dr.rectangle([TX(s['x'] - w / 2), TY(s['y'] + d / 2), TX(s['x'] + w / 2), TY(s['y'] - d / 2)], outline=c, width=2 * SS)
    dr.ellipse([TX(s['x']) - 2 * SS, TY(s['y']) - 2 * SS, TX(s['x']) + 2 * SS, TY(s['y']) + 2 * SS], fill=c)
    if FONT:
        dr.text((TX(s['x']) + 3 * SS, TY(s['y']) - 10 * SS), s['code'] or s['id'], fill=c, font=FONT)

for q in DATA['roads']:
    dr.polygon([(TX(p[0]), TY(p[1])) for p in q], outline=(160, 190, 220))
b = DATA['boundary']
dr.line([(TX(p[0]), TY(p[1])) for p in b], fill=(0, 120, 0), width=2 * SS)

img = img.resize((PX, PH), Image.LANCZOS)
out = r'D:\test\.dwgconv\verify_overlay.png'
img.save(out)
print('saved', out, img.size, 'structures', len(DATA['structures']))
