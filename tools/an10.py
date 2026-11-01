# -*- coding: utf-8 -*-
"""Detect axis-aligned rectangles from LINE segments; match to nearest labels."""
import json, math, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))
LAB = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))

TOL = 0.75
def rk(v):
    return round(v / TOL)

H = defaultdict(set)        # (kx0,kx1) -> set of ky
V = defaultdict(set)        # (kx, ky0, ky1) exists
VBYX = defaultdict(list)    # kx -> list of (ky0, ky1, layer)
HL = {}                     # (kx0,kx1,ky) -> layer

def add_line(p1, p2, layer):
    (x1, y1), (x2, y2) = p1, p2
    if abs(y1 - y2) < 0.09 and abs(x1 - x2) > 1.5:
        k = (rk(min(x1, x2)), rk(max(x1, x2)), rk(y1))
        H[(k[0], k[1])].add(k[2])
        HL[(k[0], k[1], k[2])] = layer
    elif abs(x1 - x2) < 0.09 and abs(y1 - y2) > 1.5:
        kx, ky0, ky1 = rk(x1), rk(min(y1, y2)), rk(max(y1, y2))
        if (kx, ky0, ky1) not in V:
            V[(kx, ky0, ky1)] = layer
            VBYX[kx].append((ky0, ky1, layer))

for e in ENTS:
    if e['type'] == 'LINE':
        add_line((e['start'][0], e['start'][1]), (e['end'][0], e['end'][1]), e['layer'])
    elif e['type'] in ('LWPOLYLINE', 'POLYLINE'):
        vs = e.get('vertices') or []
        for i in range(len(vs) - 1):
            add_line(vs[i][:2], vs[i + 1][:2], e['layer'])
        if e.get('closed') and len(vs) > 2:
            add_line(vs[-1][:2], vs[0][:2], e['layer'])

def has_v(kx, ky0, ky1, tol=1):
    for dx in (0, -1, 1):
        for (a, b, ly) in VBYX.get(kx + dx, ()):
            if abs(a - ky0) <= tol and abs(b - ky1) <= tol:
                return True
    return False

rects = []
for (kx0, kx1), ys in H.items():
    if len(ys) < 2:
        continue
    ys = sorted(ys)
    w = (kx1 - kx0) * TOL
    if w < 3:
        continue
    for i in range(len(ys)):
        for j in range(i + 1, len(ys)):
            h = (ys[j] - ys[i]) * TOL
            if h < 3:
                continue
            if not (has_v(kx0, ys[i], ys[j]) and has_v(kx1, ys[i], ys[j])):
                continue
            rects.append((w * h, w, h, kx0 * TOL, ys[i] * TOL, kx1 * TOL, ys[j] * TOL,
                          HL.get((kx0, kx1, ys[i]), '?')))

# de-dup nested (same bbox within 2m)
rects.sort(key=lambda r: -r[0])
kept = []
for r in rects:
    dup = False
    for k in kept:
        if abs(r[3] - k[3]) < 2.5 and abs(r[4] - k[4]) < 2.5 and abs(r[5] - k[5]) < 2.5 and abs(r[6] - k[6]) < 2.5:
            dup = True; break
    if not dup:
        kept.append(r)

print('rects found:', len(rects), 'unique:', len(kept))
print(f"{'area':>9} {'w':>7} {'h':>7}  bbox                              layer         label(dist)")

def near(x, y, maxd=200):
    best, bd = '', 1e9
    for l in LAB:
        d = math.hypot(l['x'] - x, l['y'] - y)
        if d < bd:
            bd, best = d, l
    return (best['t'], bd) if bd < maxd else ('', bd)

out = []
for r in kept[:60]:
    cx, cy = (r[3] + r[5]) / 2, (r[4] + r[6]) / 2
    t, d = near(cx, cy)
    out.append(dict(area=r[0], w=r[1], h=r[2], x0=r[3], y0=r[4], x1=r[5], y1=r[6], layer=r[7], label=t, dist=d))
    print(f"{r[0]:9.0f} {r[1]:7.1f} {r[2]:7.1f}  ({r[3]:9.1f},{r[4]:9.1f})-({r[5]:9.1f},{r[6]:9.1f}) {r[7]:<12} {t} ({d:.0f})")
json.dump(out, open(r'D:\test\.dwgconv\rects.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
