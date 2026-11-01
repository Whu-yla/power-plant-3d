# -*- coding: utf-8 -*-
"""Find 4-cycles (quadrilaterals) in the LINE graph -> building footprints (any rotation)."""
import json, math, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))
LAB = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))
EXC = set("DIM PUB_DIM WINDOW_TEXT WINDOW NEW字 NEW编号 24 地形图 DEFPOINTS '$TD_AUDIT_GENERATED_(1B714A)' 边坡 铁路线 高压线 广东火电图框 TEXT PUB_TEXT".split())

Q = 0.30
def key(p):
    return (round(p[0] / Q), round(p[1] / Q))

nodes = {}
npos = []
def node_of(p):
    k = key(p)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            kk = (k[0] + dx, k[1] + dy)
            if kk in nodes:
                i = nodes[kk]
                if math.dist(npos[i], p) < 0.4:
                    return i
    i = len(npos); npos.append((p[0], p[1])); nodes[k] = i
    return i

edges = []
def add_seg(p, q):
    if math.dist(p, q) < 0.6: return
    a, b = node_of(p), node_of(q)
    if a == b: return
    edges.append((a, b))

for e in ENTS:
    if e['layer'] in EXC: continue
    t = e['type']
    if t == 'LINE':
        add_seg((e['start'][0], e['start'][1]), (e['end'][0], e['end'][1]))
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        vs = e.get('vertices') or []
        for i in range(len(vs) - 1):
            add_seg(vs[i][:2], vs[i + 1][:2])
        if e.get('closed') and len(vs) > 2:
            add_seg(vs[-1][:2], vs[0][:2])

E = set()
for a, b in edges:
    E.add((a, b) if a < b else (b, a))
adj = defaultdict(set)
for a, b in E:
    adj[a].add(b); adj[b].add(a)

print('nodes', len(npos), 'edges', len(E))

# ring corners: A - B - C - D where A,C are the two common neighbours of diagonal (B,D)
diag = defaultdict(list)
for A, nb in adj.items():
    nl = sorted(nb)
    for i in range(len(nl)):
        for j in range(i + 1, len(nl)):
            diag[(nl[i], nl[j])].append(A)

quads = []
seen = set()
for (B, D), cs in diag.items():
    if len(cs) < 2: continue
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            A, C = cs[i], cs[j]
            k = tuple(sorted((A, B, C, D)))
            if k in seen: continue
            seen.add(k)
            pts = [npos[A], npos[B], npos[C], npos[D]]
            ar = 0.0
            for m in range(4):
                x1, y1 = pts[m]; x2, y2 = pts[(m + 1) % 4]
                ar += x1 * y2 - x2 * y1
            ar = abs(ar) / 2
            if ar < 120: continue
            # perpendicularity check
            ok = True
            for m in range(4):
                u = (pts[(m + 1) % 4][0] - pts[m][0], pts[(m + 1) % 4][1] - pts[m][1])
                v = (pts[(m + 2) % 4][0] - pts[(m + 1) % 4][0], pts[(m + 2) % 4][1] - pts[(m + 1) % 4][1])
                lu = math.hypot(*u); lv = math.hypot(*v)
                if lu < 1e-6 or lv < 1e-6: ok = False; break
                cos = abs(u[0] * v[0] + u[1] * v[1]) / (lu * lv)
                if cos > 0.12: ok = False; break
            if not ok: continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            quads.append((ar, max(xs) - min(xs), max(ys) - min(ys), min(xs), min(ys), max(xs), max(ys), pts))

quads.sort(key=lambda q: -q[0])
kept = []
for q in quads:
    dup = False
    for k in kept:
        if abs(q[3] - k[3]) < 3 and abs(q[4] - k[4]) < 3 and abs(q[5] - k[5]) < 3 and abs(q[6] - k[6]) < 3:
            dup = True; break
    if not dup: kept.append(q)

print('quads', len(quads), 'unique', len(kept))
print(f"{'area':>8} {'w':>6} {'h':>6}  bbox                                nearest label")
res = []
for q in kept[:60]:
    cx, cy = (q[3] + q[5]) / 2, (q[4] + q[6]) / 2
    best, bd = '', 1e9
    for l in LAB:
        d = math.hypot(l['x'] - cx, l['y'] - cy)
        if d < bd: bd, best = d, l
    ang = math.degrees(math.atan2(q[7][1][1] - q[7][0][1], q[7][1][0] - q[7][0][0]))
    res.append(dict(area=q[0], w=q[1], h=q[2], x0=q[3], y0=q[4], x1=q[5], y1=q[6], pts=q[7], label=best, dist=bd, ang=ang))
    print(f"{q[0]:8.0f} {q[1]:6.1f} {q[2]:6.1f}  ({q[3]:9.1f},{q[4]:9.1f})-({q[5]:9.1f},{q[6]:9.1f}) ang={ang:6.1f} {best} ({bd:.0f})")
json.dump(res, open(r'D:\test\.dwgconv\quads.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
