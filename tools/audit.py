# -*- coding: utf-8 -*-
"""Audit: find building footprints in the DWG not covered by plant-data.js."""
import json, math, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))
LAB = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))
try:
    PD = json.load(open(r'D:\test\.dwgconv\plant-data.json', encoding='utf-8'))
except Exception:
    PD = json.load(open(r'D:\test\.dwgconv\plant-data.json', encoding='utf-8'))
STRUCTS = PD['structures'] if isinstance(PD, dict) else PD

SKIP_LAYERS = {'广东火电图框', 'DIM', 'PUB_DIM', 'DEFPOINTS', '24', '地形图', '边坡',
               '水工循环水管沟', '循环水管沟', 'WINDOW_TEXT', 'WINDOW', 'COLUMN'}

# ---------- structure AABBs ----------
def struct_box(s):
    w, d, rot = s.get('w', 0), s.get('d', 0), math.radians(s.get('rot', 0) or 0)
    c, si = abs(math.cos(rot)), abs(math.sin(rot))
    hw, hd = w / 2, d / 2
    ex = hw * c + hd * si
    ey = hw * si + hd * c
    return (s['x'] - ex, s['y'] - ey, s['x'] + ex, s['y'] + ey)

SBOX = [struct_box(s) for s in STRUCTS]

def overlap_area(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)

def best_cover(bb):
    """max fraction of candidate area already covered by any single structure box"""
    ar = max(1e-6, (bb[2] - bb[0]) * (bb[3] - bb[1]))
    best, bi = 0.0, -1
    for i, sb in enumerate(SBOX):
        f = overlap_area(bb, sb) / ar
        if f > best:
            best, bi = f, i
    return best, bi

# ---------- candidate footprints ----------
cands = []

# 1) closed polylines
for e in ENTS:
    if e['type'] not in ('LWPOLYLINE', 'POLYLINE'):
        continue
    if not e.get('closed'):
        continue
    if e['layer'] in SKIP_LAYERS:
        continue
    vs = e.get('vertices') or []
    if len(vs) < 3:
        continue
    xs = [v[0] for v in vs]; ys = [v[1] for v in vs]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    a = w * d
    if a < 60 or a > 60000 or w < 4 or d < 4:
        continue
    if max(w, d) / max(1e-6, min(w, d)) > 15:
        continue
    cands.append(dict(kind='PL', area=a, w=w, d=d,
                      bb=(min(xs), min(ys), max(xs), max(ys)), layer=e['layer']))

# 2) axis-aligned rectangles from LINE segments
TOL = 0.75
def rk(v): return round(v / TOL)
H = defaultdict(set); HL = {}
VBYX = defaultdict(list); VKEYS = set()
def add_line(p1, p2, layer):
    (x1, y1), (x2, y2) = p1, p2
    if abs(y1 - y2) < 0.09 and abs(x1 - x2) > 1.5:
        k = (rk(min(x1, x2)), rk(max(x1, x2)), rk(y1))
        H[(k[0], k[1])].add(k[2]); HL[(k[0], k[1], k[2])] = layer
    elif abs(x1 - x2) < 0.09 and abs(y1 - y2) > 1.5:
        kx, ky0, ky1 = rk(x1), rk(min(y1, y2)), rk(max(y1, y2))
        if (kx, ky0, ky1) not in VKEYS:
            VKEYS.add((kx, ky0, ky1)); VBYX[kx].append((ky0, ky1, layer))
for e in ENTS:
    if e['layer'] in SKIP_LAYERS:
        continue
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
    if len(ys) < 2: continue
    ys = sorted(ys)
    w = (kx1 - kx0) * TOL
    if w < 4: continue
    for i in range(len(ys)):
        for j in range(i + 1, len(ys)):
            h = (ys[j] - ys[i]) * TOL
            if h < 4: continue
            if not (has_v(kx0, ys[i], ys[j]) and has_v(kx1, ys[i], ys[j])): continue
            rects.append((w * h, w, h, kx0 * TOL, ys[i] * TOL, kx1 * TOL, ys[j] * TOL,
                          HL.get((kx0, kx1, ys[i]), '?')))
rects.sort(key=lambda r: -r[0])
kept = []
for r in rects:
    if any(abs(r[3]-k[3]) < 2.5 and abs(r[4]-k[4]) < 2.5 and abs(r[5]-k[5]) < 2.5 and abs(r[6]-k[6]) < 2.5 for k in kept):
        continue
    kept.append(r)
for r in kept:
    if r[0] < 60 or r[0] > 60000: continue
    if max(r[1], r[2]) / max(1e-6, min(r[1], r[2])) > 15: continue
    cands.append(dict(kind='RECT', area=r[0], w=r[1], d=r[2], bb=(r[3], r[4], r[5], r[6]), layer=r[7]))

# 3) circles with radius >= 6
for e in ENTS:
    if e['type'] != 'CIRCLE': continue
    if e['layer'] in SKIP_LAYERS: continue
    r = e['radius']
    if r < 6: continue
    cx, cy = e['center'][0], e['center'][1]
    cands.append(dict(kind='CIRC', area=math.pi * r * r, w=2*r, d=2*r,
                      bb=(cx - r, cy - r, cx + r, cy + r), layer=e['layer']))

# ---------- match ----------
def near(x, y, maxd=120):
    best, bd = '', 1e9
    for l in LAB:
        d = math.hypot(l['x'] - x, l['y'] - y)
        if d < bd: bd, best = d, l
    return (best['t'], bd) if bd < maxd else ('', bd)

rows = []
for c in cands:
    cx, cy = (c['bb'][0] + c['bb'][2]) / 2, (c['bb'][1] + c['bb'][3]) / 2
    if not (2900850 < cx < 2902760 and 2548360 < cy < 2549700):
        continue
    f, bi = best_cover(c['bb'])
    if f >= 0.45:
        continue
    t, dist = near(cx, cy, 90)
    rows.append(dict(c, cov=f, label=t, ldist=dist, cx=cx, cy=cy,
                     near_struct=(STRUCTS[bi]['name'] if bi >= 0 else '')))
rows.sort(key=lambda r: -r['area'])
json.dump(rows, open(r'D:\test\.dwgconv\audit_missing.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"candidates={len(cands)}  uncovered={len(rows)}")
print(f"{'area':>8} {'w':>6} {'h':>6} {'kind':>4} {'cov':>4}  center              label")
for r in rows[:45]:
    print(f"{r['area']:8.0f} {r['w']:6.1f} {r['d']:6.1f} {r['kind']:>4} {r['cov']:.2f}  "
          f"({r['cx']:9.1f},{r['cy']:9.1f})  {r['label']} <{r['layer']}> near={r['near_struct']}")
