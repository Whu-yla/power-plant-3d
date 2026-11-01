# -*- coding: utf-8 -*-
"""Inspect road / boundary / green layers, and export decimated polylines."""
import json, sys, math
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))

for LAY in ('道路', 'NEW道路', '征地红线', '边坡', 'GROUND', '围墙', 'WALL', '地形图'):
    ents = [e for e in ENTS if e['layer'] == LAY]
    types = {}
    for e in ents: types[e['type']] = types.get(e['type'], 0) + 1
    print(f"{LAY}: {len(ents)} {types}")
    for e in ents[:6]:
        if e['type'] in ('LWPOLYLINE', 'POLYLINE'):
            vs = e['vertices']
            print(f"   {e['type']} nv={len(vs)} closed={e.get('closed')} p0={vs[0][:2]} p1={vs[1][:2] if len(vs)>1 else None}")
        elif e['type'] == 'LINE':
            print(f"   LINE {e['start']} -> {e['end']}")
print()

def decimate(pts, tol=0.4):
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > tol:
            out.append(p)
    return out

def collect(layers):
    shapes = []
    for e in ENTS:
        if e['layer'] not in layers: continue
        t = e['type']
        if t in ('LWPOLYLINE', 'POLYLINE'):
            vs = e.get('vertices') or []
            if len(vs) < 3: continue
            pts = [(round(v[0], 1), round(v[1], 1)) for v in vs]
            if e.get('closed') and math.dist(pts[0], pts[-1]) < 1:
                pts = pts[:-1]
            pts = decimate(pts)
            if len(pts) < 3: continue
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            if not (2900800 < min(xs) and max(xs) < 2902800 and 2548300 < min(ys) and max(ys) < 2549800):
                continue
            shapes.append(dict(closed=bool(e.get('closed')), pts=pts))
    return shapes

for lay in (['道路'], ['NEW道路'], ['征地红线'], ['边坡'], ['道路', 'NEW道路']):
    sh = collect(set(lay))
    npts = sum(len(s['pts']) for s in sh)
    print(f"{'+'.join(lay)}: {len(sh)} shapes, {npts} pts")
    json.dump(sh, open(r'D:\test\.dwgconv\!out_%s.json' % '_'.join(lay), 'w', encoding='utf-8'), ensure_ascii=False)
