# -*- coding: utf-8 -*-
"""Pair parallel road edge lines into road strip polygons (exact geometry from DWG)."""
import json, sys, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))

segs = []   # (x1,y1,x2,y2, layer)
for e in ENTS:
    if e['layer'] not in ('道路', 'NEW道路'):
        continue
    if e['type'] == 'LINE':
        p, q = e['start'], e['end']
        segs.append((p[0], p[1], q[0], q[1], e['layer']))
    elif e['type'] == 'LWPOLYLINE':
        vs = e.get('vertices') or []
        for i in range(len(vs) - 1):
            segs.append((vs[i][0], vs[i][1], vs[i + 1][0], vs[i + 1][1], e['layer']))
        if e.get('closed') and len(vs) > 2:
            segs.append((vs[-1][0], vs[-1][1], vs[0][0], vs[0][1], e['layer']))

def unit(s):
    dx, dy = s[2] - s[0], s[3] - s[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L, L) if L > 1e-9 else (0, 0, 0)

# keep long segs for pairing
cand = [s for s in segs if unit(s)[2] > 12]
print('segments', len(segs), 'long', len(cand))
cand.sort(key=lambda s: -unit(s)[2])

used = [False] * len(cand)
strips = []
for i, a in enumerate(cand):
    if used[i]:
        continue
    ua, va, la = unit(a)
    best, bd = -1, 1e9
    for j, b in enumerate(cand):
        if j <= i or used[j]:
            continue
        ub, vb, lb = unit(b)
        if abs(ua * ub + va * vb) < 0.995:
            continue
        # perpendicular distance
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = abs(-va * dx + ua * dy)
        if not (3.0 < d < 14.0):
            continue
        # overlap of projections
        pa0, pa1 = 0.0, la
        pb0 = dx * ua + dy * va
        pb1 = pb0 + lb
        ov = min(pa1, pb1) - max(pa0, pb0)
        if ov < 0.5 * min(la, lb):
            continue
        if d < bd:
            bd, best = d, j
    if best < 0:
        continue
    b = cand[best]
    used[i] = used[best] = True
    strips.append((a, b, bd))

print('strips', len(strips))
polys = []
for a, b, d in strips:
    ua, va, la = unit(a)
    ax, ay = a[0], a[1]
    dx, dy = b[0] - ax, b[1] - ay
    signed = -va * dx + ua * dy           # signed perpendicular offset of b's line
    nx, ny = -va * signed, ua * signed
    tb0 = dx * ua + dy * va
    tb1 = tb0 + unit(b)[2]
    t0 = max(0.0, min(tb0, tb1))
    t1 = min(la, max(tb0, tb1))
    if t1 - t0 < 8:
        t0, t1 = 0.0, la
    p0 = (ax + ua * t0, ay + va * t0)
    p1 = (ax + ua * t1, ay + va * t1)
    q0 = (ax + ua * t0 + nx, ay + va * t0 + ny)
    q1 = (ax + ua * t1 + nx, ay + va * t1 + ny)
    poly = [p0, p1, q1, q0]
    area = 0.0
    for m in range(4):
        x1, y1 = poly[m]; x2, y2 = poly[(m + 1) % 4]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2
    if area < 30:
        continue
    polys.append([[round(p[0], 1), round(p[1], 1)] for p in poly] + [d])

print('quads', len(polys))
json.dump(polys, open(r'D:\test\.dwgconv\roads.json', 'w', encoding='utf-8'), ensure_ascii=False)
xl = [p[k][0] for p in polys for k in range(4)]
yl = [p[k][1] for p in polys for k in range(4)]
print('bbox', min(xl), min(yl), max(xl), max(yl))
