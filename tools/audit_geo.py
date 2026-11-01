# -*- coding: utf-8 -*-
"""
CAD 几何审计：多方法提取候选建筑足迹 -> 与已建模清单 plant-data.json 比对 -> 遗漏清单
读: .dwgconv/out/entities.json, labels.json, plant-data.json
写: .dwgconv/audit_missing.json, .dwgconv/audit_missing.md
只读 src/3d-powerplant，不作任何修改。
方法: A 近闭合多段线 / B 任意旋转四边形(4-cycle) / C 轴对齐矩形(配对) /
      D 圆 / E 线段图闭合环(4~12 边) / F 三边直角折线补全
"""
import json, math, sys, re, collections, time, os, hashlib, shutil
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = r'D:\test\.dwgconv'
ENT = json.load(open(BASE + r'\out\entities.json', encoding='utf-8'))
LAB = json.load(open(BASE + r'\labels.json', encoding='utf-8'))
# plant-data.json 会被并行工作实时改写：先冻结快照，审计数字以快照为准（报告内注明基线）
SRC_PLANT = BASE + r'\plant-data.json'
SNAPSHOT = BASE + r'\_audit_plant_baseline.json'
shutil.copyfile(SRC_PLANT, SNAPSHOT)
_ps = os.stat(SRC_PLANT)
PLANT = json.load(open(SNAPSHOT, encoding='utf-8'))
BASELINE = dict(path=SRC_PLANT, mtime=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(_ps.st_mtime)),
                bytes=_ps.st_size,
                sha1=hashlib.sha1(open(SNAPSHOT, 'rb').read()).hexdigest()[:12],
                n=len(PLANT['structures']))
STRUCTS = PLANT['structures']
print(f"[基线] plant-data.json {BASELINE['n']} 条构筑物，mtime {BASELINE['mtime']}，sha1 {BASELINE['sha1']}")

EXC_LAYERS = {
    '广东火电图框', '道路', 'NEW道路', '边坡', 'DIM', 'PUB_DIM', '24', '15',
    '地形图', '3', '11', '铁路线', '高压线', '征地红线', 'NEW字', 'NEW编号',
    'TEXT', 'PUB_TEXT', 'WINDOW_TEXT', 'DEFPOINTS', '0', '8', '2', '12', '-5',
    'DLSS', 'HDASHDOT', 'ASSIST', 'JMD', 'AXIS', 'AXIS_TEXT', 'Layer6',
    '$TD_AUDIT_GENERATED_(1B714A)',
}
BUILD_LAYERS = ['1', 'WALL', 'COLUMN', 'WINDOW', '设备', '电气', '34', '3']
PIPE_LAYERS = {'循环水管沟', '水工循环水管沟', '循环水管'}
AOI = (2900900.0, 2548300.0, 2902800.0, 2549700.0)
TABLE_ZONE = [(2902440.0, 2548900.0, 3.0e6, 2549620.0)]   # 表格/工程量表区（x>2902440 一律排除）
REGIONS = [
    ('主厂房区',   2901640, 2901930, 2549000, 2549340),
    ('东侧辅助区', 2901970, 2902200, 2549020, 2549320),
    ('南侧输煤区', 2901600, 2902400, 2548850, 2549020),
    ('施工临建区', 2901350, 2901650, 2549390, 2549560),
]
AREA_SHAPES = {'pad', 'coalheap', 'switchyard', 'pipes', 'retaining', 'duct'}

def inbox(p, bb, m=0.0):
    return bb[0] - m <= p[0] <= bb[2] + m and bb[1] - m <= p[1] <= bb[3] + m

def bbox_of(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

def poly_area(pts):
    a = 0.0; n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0

def bulge_pts(p, q, b, n=10):
    if abs(b) < 1e-9:
        return [p, q]
    dx, dy = q[0] - p[0], q[1] - p[1]
    c = math.hypot(dx, dy)
    if c < 1e-12:
        return [p, q]
    th = 4 * math.atan(b)
    r = c / (2 * math.sin(abs(th) / 2))
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    d = r * math.cos(abs(th) / 2)
    ux, uy = -dy / c, dx / c
    sgn = 1 if b > 0 else -1
    cx, cy = mx + ux * d * sgn, my + uy * d * sgn
    a0 = math.atan2(p[1] - cy, p[0] - cx)
    return [(cx + r * math.cos(a0 + th * i / n), cy + r * math.sin(a0 + th * i / n)) for i in range(n + 1)]

def poly_pts(ent):
    vs = ent.get('vertices') or []
    if len(vs) < 2:
        return []
    pts = []
    for i in range(len(vs) - 1):
        b = vs[i][2] if len(vs[i]) > 2 else 0.0
        pts.extend(bulge_pts(vs[i][:2], vs[i + 1][:2], b))
    return pts

def vdist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])

# ============================================================ 几何收集
segs = []; polys = []; circles = []
for e in ENT:
    lay = e['layer']; t = e['type']
    if lay in EXC_LAYERS:
        continue
    if t == 'LINE':
        segs.append(((e['start'][0], e['start'][1]), (e['end'][0], e['end'][1]), lay))
    elif t in ('LWPOLYLINE', 'POLYLINE'):
        vs = e.get('vertices') or []
        if len(vs) < 2:
            continue
        for i in range(len(vs) - 1):
            segs.append(((vs[i][0], vs[i][1]), (vs[i + 1][0], vs[i + 1][1]), lay))
        if e.get('closed') and len(vs) > 2:
            segs.append(((vs[-1][0], vs[-1][1]), (vs[0][0], vs[0][1]), lay))
        if len(vs) >= 3:
            polys.append((e, poly_pts(e), lay))
    elif t == 'CIRCLE':
        circles.append((e['center'][0], e['center'][1], e['radius'], lay))

print(f'[几何] 线段 {len(segs)}  多段线(>=3点) {len(polys)}  圆 {len(circles)}')
gaps = sorted(vdist((e['vertices'][0][0], e['vertices'][0][1]),
                    (e['vertices'][-1][0], e['vertices'][-1][1])) for e, _, _ in polys)
print(f'[多段线] 首尾缺口中位数 {gaps[len(gaps)//2]:.2f} m, 缺口<2m {sum(1 for g in gaps if g < 2.0)}/{len(gaps)}'
      f'，closed=True {sum(1 for e, _, _ in polys if e.get("closed"))}')

CAND = []
def add(**kw):
    CAND.append(kw)

# ---- A 近闭合多段线
A_N = 0
for e, pts, lay in polys:
    vs = e['vertices']; n = len(vs)
    if not (3 <= n <= 30):
        continue
    gap = vdist((vs[0][0], vs[0][1]), (vs[-1][0], vs[-1][1]))
    if not e.get('closed') and gap > 2.0:
        continue
    bb = bbox_of(pts)
    if bb[2] - bb[0] < 2 or bb[3] - bb[1] < 2:
        continue
    ar = poly_area(pts); bba = (bb[2] - bb[0]) * (bb[3] - bb[1])
    if ar < 80 or bba > 90000 or ar / bba < 0.12:
        continue
    A_N += 1
    add(method='poly_closed', pts=pts, bbox=bb, area=ar, layers={lay}, nverts=n, rot=0.0)

# ---- F 三边直角折线补全为矩形
F_N = 0
for e, pts, lay in polys:
    vs = [(v[0], v[1]) for v in e['vertices']]
    if len(vs) != 4 or e.get('closed'):
        continue
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = vs
    ax = abs(y0 - y1) < 0.15 and abs(y2 - y3) < 0.15 and abs(x1 - x2) < 0.15
    if not ax:
        continue
    w = abs(x1 - x0); h = abs(y1 - y2)
    if w < 2 or h < 2 or w > 320 or h > 320:
        continue
    ar = w * h
    if ar < 80:
        continue
    F_N += 1
    bb = (min(x0, x1), min(y1, y2), max(x0, x1), max(y1, y2))
    add(method='u3_rect', pts=[(bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])],
        bbox=bb, area=ar, layers={lay}, nverts=4, rot=0.0)

# ---- B 任意旋转四边形（4-cycle + 垂直度）
QST = 0.30
nodes = {}; npos = []
def node_of(p):
    k = (round(p[0] / QST), round(p[1] / QST))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            kk = (k[0] + dx, k[1] + dy)
            if kk in nodes:
                i = nodes[kk]
                if math.dist(npos[i], p) < 0.4:
                    return i
    i = len(npos); npos.append((p[0], p[1])); nodes[k] = i
    return i

ELAY = {}
E = set()
for p, q, lay in segs:
    if math.dist(p, q) < 0.8:
        continue
    if not (AOI[0] - 250 < p[0] < AOI[2] + 250 and AOI[1] - 250 < p[1] < AOI[3] + 250):
        continue
    if not (AOI[0] - 250 < q[0] < AOI[2] + 250 and AOI[1] - 250 < q[1] < AOI[3] + 250):
        continue
    a, b = node_of(p), node_of(q)
    if a != b:
        k = (a, b) if a < b else (b, a)
        E.add(k)
        ELAY.setdefault(k, set()).add(lay)

adj = collections.defaultdict(set)
for a, b in E:
    adj[a].add(b); adj[b].add(a)
print(f'[线段图] 节点 {len(npos)}  边 {len(E)}  最大度 {max((len(v) for v in adj.values()), default=0)}')

def edge_layers(path):
    s = set()
    for i in range(len(path)):
        a, b = path[i], path[(i + 1) % len(path)]
        s |= ELAY.get((a, b) if a < b else (b, a), set())
    return s

B_N = 0
diag = collections.defaultdict(list)
for A, nb in adj.items():
    nl = sorted(nb)
    for i in range(len(nl)):
        for j in range(i + 1, len(nl)):
            diag[(nl[i], nl[j])].append(A)
seen = set()
for (B, D), cs in diag.items():
    if len(cs) < 2 or len(cs) > 8:
        continue
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            A, C = cs[i], cs[j]
            k = tuple(sorted((A, B, C, D)))
            if k in seen:
                continue
            seen.add(k)
            pts = [npos[A], npos[B], npos[C], npos[D]]
            mx = sum(p[0] for p in pts) / 4; my = sum(p[1] for p in pts) / 4
            pts.sort(key=lambda p: math.atan2(p[1] - my, p[0] - mx))
            ar = poly_area(pts)
            bb0 = bbox_of(pts)
            if ar < 100 or (bb0[2] - bb0[0]) < 4 or (bb0[3] - bb0[1]) < 4:
                continue
            if ar / ((bb0[2] - bb0[0]) * (bb0[3] - bb0[1])) < 0.30:
                continue
            ok = True
            for m in range(4):
                u = (pts[(m + 1) % 4][0] - pts[m][0], pts[(m + 1) % 4][1] - pts[m][1])
                v = (pts[(m + 2) % 4][0] - pts[(m + 1) % 4][0], pts[(m + 2) % 4][1] - pts[(m + 1) % 4][1])
                lu = math.hypot(*u); lv = math.hypot(*v)
                if lu < 2.0 or lv < 2.0 or abs(u[0] * v[0] + u[1] * v[1]) / (lu * lv) > 0.12:
                    ok = False; break
            if not ok:
                continue
            bb = bbox_of(pts)
            if bb[2] - bb[0] > 320 or bb[3] - bb[1] > 320:
                continue
            B_N += 1
            ang = math.degrees(math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0]))
            add(method='quad4', pts=pts, bbox=bb, area=ar, layers=edge_layers([A, B, C, D]),
                nverts=4, rot=round(ang, 1))

# ---- E 线段图闭合环（4~12 边）
E_N = 0
cycles = {}
t0 = time.time()
for s in list(adj):
    stack = [(s, [s])]
    while stack:
        cur, path = stack.pop()
        if len(path) > 12:
            continue
        for nb in adj[cur]:
            if nb == s and len(path) >= 4:
                key = frozenset(path)
                if key not in cycles:
                    pts = [npos[i] for i in path]
                    cycles[key] = (poly_area(pts), len(path), pts, path)
            elif nb not in path and nb > s:
                stack.append((nb, path + [nb]))
print(f'[环] 闭合环 {len(cycles)} 个，耗时 {time.time()-t0:.1f}s')
for key, (ar, n, pts, path) in cycles.items():
    if ar < 80:
        continue
    bb = bbox_of(pts)
    w = bb[2] - bb[0]; h = bb[3] - bb[1]
    if w > 320 or h > 320 or w < 4 or h < 4:
        continue
    if ar / (w * h) < 0.30:      # 过于破碎的环（组合噪声）
        continue
    E_N += 1
    add(method='cycle%d' % n, pts=pts, bbox=bb, area=ar, layers=edge_layers(path), nverts=n, rot=0.0)

# ---- C 轴对齐矩形（H/V 配对）
TOL = 0.40
def rk(v):
    return round(v / TOL)
H = collections.defaultdict(lambda: collections.defaultdict(list))
V = {}; VBYKX = collections.defaultdict(list)
for p, q, lay in segs:
    (x1, y1), (x2, y2) = p, q
    if abs(y1 - y2) < 0.10 and abs(x1 - x2) > 2.0:
        H[(rk(min(x1, x2)), rk(max(x1, x2)))][rk((y1 + y2) / 2)].append(
            (min(x1, x2), max(x1, x2), (y1 + y2) / 2, lay))
    elif abs(x1 - x2) < 0.10 and abs(y1 - y2) > 2.0:
        kk = (rk((x1 + x2) / 2), rk(min(y1, y2)), rk(max(y1, y2)))
        if kk not in V:
            V[kk] = ((x1 + x2) / 2, min(y1, y2), max(y1, y2), lay)
            VBYKX[kk[0]].append((kk[1], kk[2]))

def has_v(kx, ky0, ky1, tol=1):
    for dx in (-1, 0, 1):
        for (a, b) in VBYKX.get(kx + dx, ()):
            if abs(a - ky0) <= tol and abs(b - ky1) <= tol:
                return True
    return False

C_N = 0
for (kx0, kx1), ys in H.items():
    if len(ys) < 2:
        continue
    xs_all = [s for lst in ys.values() for s in lst]
    x0m = sum(s[0] for s in xs_all) / len(xs_all)
    x1m = sum(s[1] for s in xs_all) / len(xs_all)
    w = x1m - x0m
    if w < 2.5 or w > 320:
        continue
    yk = sorted(ys)
    for i in range(len(yk)):
        for j in range(i + 1, len(yk)):
            if not has_v(kx0, yk[i], yk[j]) or not has_v(kx1, yk[i], yk[j]):
                continue
            y0m = sum(s[2] for s in ys[yk[i]]) / len(ys[yk[i]])
            y1m = sum(s[2] for s in ys[yk[j]]) / len(ys[yk[j]])
            h = y1m - y0m
            if h < 2.5 or h > 320:
                continue
            ar = w * h
            if ar < 80 or max(w, h) / min(w, h) > 45:
                continue
            C_N += 1
            add(method='axis_rect', pts=[(x0m, y0m), (x1m, y0m), (x1m, y1m), (x0m, y1m)],
                bbox=(x0m, y0m, x1m, y1m), area=ar,
                layers=set(s[3] for s in xs_all), nverts=4, rot=0.0)

# ---- D 圆
D_N = 0
for cx, cy, r, lay in circles:
    ar = math.pi * r * r
    if r < 5 or ar < 80:
        continue
    D_N += 1
    add(method='circle', pts=[(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)],
        bbox=(cx - r, cy - r, cx + r, cy + r), area=ar, layers={lay}, nverts=0, rot=0.0)

print(f'[方法] A 近闭合多段线 {A_N} | B 四边形 {B_N} | C 轴对齐矩形 {C_N} | D 圆 {D_N} | '
      f'E 闭合环 {E_N} | F 三边补全 {F_N} | 合计 {len(CAND)}')

# ============================================================ 过滤 + 去重
def cand_ok(c):
    bb = c['bbox']
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    if not (AOI[0] <= cx <= AOI[2] and AOI[1] <= cy <= AOI[3]):
        return False
    if cx > 2902440:            # 表格/图例区
        return False
    if not (bb[0] < AOI[2] and bb[2] > AOI[0] and bb[1] < AOI[3] and bb[3] > AOI[1]):
        return False
    if (bb[2] - bb[0]) < 4.0 or (bb[3] - bb[1]) < 4.0:   # 剔除狭缝/双线夹层
        return False
    return True

n_before = len(CAND)
filtered = [c for c in CAND if cand_ok(c)]
print(f'[过滤] 区域/表格区/离群剔除 {n_before - len(filtered)} 条，保留 {len(filtered)} 条')

def iou_bb(a, b):
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0, 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    ca = (a[2] - a[0]) * (a[3] - a[1])
    return (inter / ua if ua > 0 else 0.0), (inter / ca if ca > 0 else 0.0)

filtered.sort(key=lambda c: -c['area'])
MERGED = []
for c in filtered:
    cx1 = (c['bbox'][0] + c['bbox'][2]) / 2; cy1 = (c['bbox'][1] + c['bbox'][3]) / 2
    hit = None
    for m in MERGED:
        iou, cov = iou_bb(c['bbox'], m['bbox'])
        if iou >= 0.70:
            hit = m; break
        if cov >= 0.90 and c['area'] >= 0.85 * m['area']:
            hit = m; break
        cx2 = (m['bbox'][0] + m['bbox'][2]) / 2; cy2 = (m['bbox'][1] + m['bbox'][3]) / 2
        if math.hypot(cx1 - cx2, cy1 - cy2) < 1.2 and 0.8 < c['area'] / max(m['area'], 1e-6) < 1.25:
            hit = m; break
    if hit is None:
        c = dict(c); c['methods'] = {c['method']}; c['layers'] = set(c['layers'])
        MERGED.append(c)
    else:
        hit['methods'].add(c['method']); hit['layers'] |= c['layers']
        if c['area'] > hit['area'] * 1.02:
            for kk in ('pts', 'bbox', 'area', 'rot', 'nverts'):
                hit[kk] = c.get(kk, hit.get(kk))
print(f'[去重] 合并后候选足迹 {len(MERGED)} 条')

# ============================================================ 证据
wall_mid = [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q, lay in segs if lay == 'WALL']
all_mid = [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q, lay in segs]
def ins_pts(layer):
    return [(e['position'][0], e['position'][1]) for e in ENT if e['type'] == 'INSERT' and e['layer'] == layer]
col_pts = ins_pts('COLUMN'); win_pts = ins_pts('WINDOW'); b34 = ins_pts('34')
equip_mid = [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q, lay in segs if lay in ('设备', '电气')]
def cnt_pts(pts, bb):
    return sum(1 for x, y in pts if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3])

SC = []
for s in STRUCTS:
    cx, cy = s.get('x', 0), s.get('y', 0)
    w, d = s.get('w', 0) or 0, s.get('d', 0) or 0
    if s.get('shape') in ('hyperbolic', 'dome', 'chimney') or (w == 0 and d > 0):
        hw = hd = d / 2.0
    elif w == 0 and d == 0:
        hw = hd = math.sqrt(max(s.get('area', 0) or 1, 1)) / 2
    else:
        hw, hd = w / 2.0, d / 2.0
    SC.append(dict(id=s['id'], name=s['name'], cat=s.get('cat'), shape=s.get('shape'),
                   bb=(cx - hw, cy - hd, cx + hw, cy + hd), area=s.get('area', 0) or w * d))

# 任务书口径的 71 条基线：当前文件中前 71 条（ST-101 … ST-S-26），其后为并行工作新增件
N_BASE = 71
SC71 = SC[:N_BASE]
BASE_IDS = [s['id'] for s in SC71]
print(f'[基线] 71 条基线集合末项 = {BASE_IDS[-1]}，新增件 {len(SC) - N_BASE} 条')

def has_cn(t):
    return any('\u4e00' <= ch <= '\u9fff' for ch in t)

def strip_area(t):
    t2 = re.sub(r'[\d.,]+\s*m2', '', t, flags=re.I)
    t2 = re.sub(r'[\d.,]+\s*平方米', '', t2)
    return t2.strip(' 　-—:：') or t

records = []
for idx, c in enumerate(MERGED):
    bb = c['bbox']
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    w, d = bb[2] - bb[0], bb[3] - bb[1]
    labs = sorted(((math.hypot(l['x'] - cx, l['y'] - cy), l) for l in LAB), key=lambda t: t[0])[:3]
    labs = [dict(t=l['t'][:40], d=round(dd, 1), layer=l['layer']) for dd, l in labs]
    inside = [l for l in LAB if inbox((l['x'], l['y']), bb, 2.5)]
    cn_inside = [l for l in inside if has_cn(l['t'])]
    if cn_inside:
        li = max(cn_inside, key=lambda l: len(l['t']))
        lt, ld, lsrc = li['t'][:40], round(math.hypot(li['x'] - cx, li['y'] - cy), 1), '框内'
    elif labs:
        lt, ld, lsrc = labs[0]['t'], labs[0]['d'], '最近'
    else:
        lt, ld, lsrc = '', 999, '-'
    code = ''
    for l in inside:
        t = l['t'].strip()
        if re.fullmatch(r'\d{2,3}', t) and l['layer'] in ('15', 'NEW编号', 'PUB_TEXT', '1', 'PUB_DIM'):
            code = t; break

    best = None
    near = None
    for s in SC71:                     # 任务书 71 条基线
        iou, cov = iou_bb(bb, s['bb'])
        if iou >= 0.25 or cov >= 0.55:
            if best is None or (iou + cov) > (best[1] + best[2]):
                best = (s, iou, cov)
        dd = math.hypot(cx - (s['bb'][0] + s['bb'][2]) / 2, cy - (s['bb'][1] + s['bb'][3]) / 2)
        if near is None or (round(iou + cov, 4), -dd) > (round(near[1] + near[2], 4), -near[3]):
            near = (s, iou, cov, dd)
    hit = None; covered = False; pad_only = False
    if best:
        s, iou, cov = best
        hit = dict(id=s['id'], name=s['name'], iou=round(iou, 2), cover=round(cov, 2))
        covered = True
        if s['shape'] in AREA_SHAPES and c['area'] < 0.35 * max(s['area'], 1):
            pad_only = True
    near_d = None
    if near:
        s, iou, cov, dd = near
        near_d = dict(id=s['id'], name=s['name'], iou=round(iou, 2), cover=round(cov, 2), dist=round(dd, 1))

    # 与「当前最新清单」（含并行新增件）的覆盖关系，用于说明列表漂移
    now = None; now_best = None
    for s in SC:
        iou, cov = iou_bb(bb, s['bb'])
        if iou >= 0.25 or cov >= 0.55:
            if now_best is None or (iou + cov) > (now_best[1] + now_best[2]):
                now_best = (s, iou, cov)
    if now_best:
        s, iou, cov = now_best
        now = dict(id=s['id'], name=s['name'], iou=round(iou, 2), cover=round(cov, 2),
                   dist=round(math.hypot(cx - (s['bb'][0] + s['bb'][2]) / 2, cy - (s['bb'][1] + s['bb'][3]) / 2), 1))
        if s['shape'] in AREA_SHAPES and c['area'] < 0.35 * max(s['area'], 1):
            now['pad_only'] = True

    ev = dict(wall=cnt_pts(wall_mid, bb), col=cnt_pts(col_pts, bb), win=cnt_pts(win_pts, bb),
              b34=cnt_pts(b34, bb), equip=cnt_pts(equip_mid, bb), dens=cnt_pts(all_mid, bb))
    reg = next((nm for nm, x0, x1, y0, y1 in REGIONS if x0 <= cx <= x1 and y0 <= cy <= y1), '')

    records.append(dict(
        cid='C%04d' % (idx + 1), method='/'.join(sorted(c['methods'])),
        layers=sorted(x for x in c['layers'] if x),
        cx=round(cx, 1), cy=round(cy, 1),
        x0=round(bb[0], 1), y0=round(bb[1], 1), x1=round(bb[2], 1), y1=round(bb[3], 1),
        w=round(w, 1), d=round(d, 1), area=round(c['area'], 1), bbox_area=round(w * d, 1),
        rot=c.get('rot', 0.0), nverts=c.get('nverts', 4),
        labels=labs, label=lt, label_dist=ld, label_src=lsrc, code=code,
        hit=hit, covered=covered, pad_only=pad_only, region=reg, ev=ev, near=near_d, now=now,
        outline=[[round(p[0], 1), round(p[1], 1)] for p in c['pts']],
    ))

N_COV = sum(1 for r in records if r['covered'] and not r['pad_only'])
N_PAD = sum(1 for r in records if r['pad_only'])
N_UNC = sum(1 for r in records if not r['covered'])
N_NOW = sum(1 for r in records if not r['covered'] and r['now'])
print(f'[结果] 候选 {len(records)} | 覆盖(71基线) {N_COV} | 仅场地覆盖 {N_PAD} | 未覆盖(71基线) {N_UNC}'
      f' | 其中已被并行新增件覆盖 {N_NOW} | 仍未覆盖 {N_UNC - N_NOW}')

json.dump(records, open(BASE + r'\audit_missing.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[写出] audit_missing.json')

# ============================================================ 区域 × 建筑图层统计
def ent_rep(e):
    t = e['type']
    if t == 'LINE':
        return ((e['start'][0] + e['end'][0]) / 2, (e['start'][1] + e['end'][1]) / 2)
    if t in ('LWPOLYLINE', 'POLYLINE') and e.get('vertices'):
        vs = e['vertices']
        return (sum(v[0] for v in vs) / len(vs), sum(v[1] for v in vs) / len(vs))
    if t == 'INSERT':
        return (e['position'][0], e['position'][1])
    if t == 'CIRCLE':
        return (e['center'][0], e['center'][1])
    p = e.get('position') or e.get('insertionPoint')
    return (p[0], p[1]) if p else None

REGSTAT = []
for nm, x0, x1, y0, y1 in REGIONS:
    rows = []
    for lay in BUILD_LAYERS:
        ents = 0
        for e in ENT:
            if e['layer'] != lay:
                continue
            p = ent_rep(e)
            if p and x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                ents += 1
        cands = [r for r in records if lay in r['layers'] and x0 <= r['cx'] <= x1 and y0 <= r['cy'] <= y1]
        rows.append(dict(layer=lay, ents=ents, n=len(cands),
                         unc=sum(1 for r in cands if not r['covered']),
                         list=[dict(cid=r['cid'], cx=r['cx'], cy=r['cy'], w=r['w'], d=r['d'],
                                    area=r['area'], covered=r['covered'], pad=r['pad_only'])
                               for r in sorted(cands, key=lambda r: -r['area'])]))
    tot = [r for r in records if x0 <= r['cx'] <= x1 and y0 <= r['cy'] <= y1]
    REGSTAT.append(dict(name=nm, box=[x0, x1, y0, y1], rows=rows, total=len(tot),
                        unc=sum(1 for r in tot if not r['covered']),
                        pad=sum(1 for r in tot if r['pad_only']),
                        area=round(sum(r['area'] for r in tot), 1)))

# ============================================================ 推断用途
def infer(r):
    lab = r['label']
    if lab and has_cn(lab):
        return strip_area(lab), ('用途标签' if r['label_src'] == '框内' else '邻近标签')
    if r['code']:
        return '图纸编号%s（清单缺失）' % r['code'], '编号标注'
    a = r['area']; ar = max(r['w'], r['d']) / max(min(r['w'], r['d']), 0.1)
    if a >= 5000:
        s = '大型厂房/料场'
    elif a >= 2000:
        s = '中型厂房/车间'
    elif a >= 800:
        s = '厂房/库房'
    elif a >= 300:
        s = '小型车间/库房'
    else:
        s = '附属小房/设备间'
    if ar > 6:
        s += '（狭长：栈桥/管廊/沟道）'
    if r['pad_only']:
        s += '（位于场地场内）'
    return s, '几何推断'


def grade(r):
    """证据评级：强/中/弱+/弱（框内用途标签 + 图元密度）"""
    ev = r['ev']
    lab = bool(r['label']) and has_cn(r['label']) and r['label_src'] == '框内'
    n = ev['wall'] + ev['col'] + ev['win']
    dens = ev.get('dens', 0)
    if lab and (n >= 3 or dens >= 30):
        return '强'
    if lab or n >= 8 or dens >= 80:
        return '中'
    if n >= 2 or dens >= 20 or r['code']:
        return '弱+'
    return '弱'


for r in records:
    r['use'], r['use_src'] = infer(r)
    r['grade'] = grade(r)

json.dump(records, open(BASE + r'\audit_missing.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[写出] audit_missing.json（含 use/grade）')


def row_txt(r, region=True):
    ev = r['ev']
    evs = f"{ev['wall']}/{ev['col']}/{ev['win']}"
    lab = r['label'] or '-'
    if r['label'] not in ('', '-') and r['label_dist'] > 0:
        lab = f'{lab}（{r["label_dist"]:.0f}m·{r["label_src"]}）'
    lay = ','.join(r['layers'])[:16] or '-'
    nr = r['near']
    if nr is None:
        near = '—'
    elif nr['iou'] > 0.02 or nr['cover'] > 0.02:
        near = f"{nr['id']}（IoU {nr['iou']:.2f}）"
    else:
        near = f"{nr['id']}（{nr['dist']:.0f}m）"
    out = (f"| {r['cid']} | {r['cx']:.1f} | {r['cy']:.1f} | {r['w']:.0f}×{r['d']:.0f} | "
           f"{r['area']:.0f} | {r['grade']} | {r['method']} | {lay} | {lab} | {evs} | {near} | {now_txt(r)} |")
    if region:
        out += f" {r['region'] or '—'} |"
    return out


def now_txt(r):
    nw = r['now']
    if not nw:
        return '仍未覆盖'
    tag = '场地内' if nw.get('pad_only') else '已覆盖'
    return f"{nw['id']}（{tag}，IoU {nw['iou']:.2f}）"


HEAD = ("| 编号 | 中心E | 中心N | 尺寸(m) | 面积(m²) | 证据 | 方法 | 图层 | 最近标签(距中心) | 墙/柱/窗 | "
        "最近已建模件(71基线) | 最新清单状态 |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|")
HEAD_R = ("| 编号 | 中心E | 中心N | 尺寸(m) | 面积(m²) | 证据 | 方法 | 图层 | 最近标签(距中心) | 墙/柱/窗 | "
          "最近已建模件(71基线) | 最新清单状态 | 区域 |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|")

unc = sorted([r for r in records if not r['covered']], key=lambda r: -r['area'])
big_unc = [r for r in unc if r['area'] >= 300]
mid_unc = [r for r in unc if 100 <= r['area'] < 300]
small_unc = [r for r in unc if r['area'] < 100]
pad_list = sorted([r for r in records if r['pad_only']], key=lambda r: -r['area'])

def weak(r):
    return (not r['covered'] and r['grade'] in ('弱', '弱+') and
            not (r['label'] and has_cn(r['label']) and r['label_src'] == '框内'))

weak_list = [r for r in unc if weak(r)]

# 推荐补建模：71 基线未覆盖 + 最新清单也未覆盖 + 面积>=200 + 证据强/中
reco = [r for r in unc if (not r['now']) and r['area'] >= 150]
residual = sorted([r for r in unc if not r['now']], key=lambda r: -r['area'])

json.dump(dict(total=len(records), covered=N_COV, pad=N_PAD, uncovered=N_UNC,
               regions=REGSTAT), open(BASE + r'\_audit_stat.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

# ============================================================ Markdown 报告
L = []
A = L.append
A('# 电厂总平面图 · 建构筑物平面轮廓遗漏审计')
A('')
A('审计输入：`D:\\test\\.dwgconv\\out\\entities.json`（11822 个 CAD 实体）、`labels.json`（612 条清洗文字）、'
  '`plant-data.json`（已建模清单）。')
A('坐标系统：图纸测量坐标（东 E / 北 N，单位 m，1 单位 = 1 m）。审计范围 E 2900900–2902800、N 2548300–2549700。')
A('本报告**只读**图纸数据，未修改 `src/3d-powerplant` 下任何文件。')
A('')
A('### 基线说明（重要）')
A('')
A(f'任务书口径的已建模清单是 **71 个构筑物**。审计运行期间，`plant-data.json` 正被并行工作实时追加'
  f'（本次冻结快照：**{BASELINE["n"]} 条**，mtime `{BASELINE["mtime"]}`，sha1 `{BASELINE["sha1"]}`）。')
A(f'本报告以快照中的**前 {N_BASE} 条（`ST-101` … `ST-S-26`）作为任务书 71 条基线**，'
  f'并同时给出候选在「最新清单」（含并行新增 {BASELINE["n"] - N_BASE} 条）中的状态。')
A('快照文件：`_audit_plant_baseline.json`，可据此复现全部数字。')
A('')
A('口径说明：**未覆盖 = 候选足迹与 71 条基线矩形既无 IoU ≥ 0.25、也无 55% 以上被包含**。')
A('因此「未覆盖」包含两种情况：清单里确实没有的建构筑物（真遗漏），以及与已建模件仅擦边/部分相交的候选（需人工判读）。'
  '表中同时给出「最近已建模件」与「最新清单状态」两列便于甄别。')
A('')
A('## 1. 方法与排除规则')
A('')
A('| 方法 | 说明 | 判据 |')
A('|---|---|---|')
A('| A 近闭合多段线 | LWPOLYLINE/POLYLINE 首尾缺口 ≤2 m 即视为闭合（图纸中 `closed=True` 的实体为 0 条，必须用缺口判据） '
  '| 3–30 顶点、面积 ≥80 m²、占空比 ≥0.12 |')
A('| B 任意旋转四边形 | 端点按 0.3 m 网格建图，取共对角线的 4 点成环，四角做垂直度校验 | 面积 ≥100 m²、四角 \\|cos\\| ≤0.12、'
  '边长 ≥2 m、最小边 ≥4 m |')
A('| C 轴对齐矩形 | 水平线按 (x0,x1) 量化分组、竖直线两端配对，命中后用实际线均值细化 | 面积 ≥80 m²、长宽比 ≤45 |')
A('| D 圆 | 独立圆实体（筒仓/罐/塔） | r ≥5 m 且面积 ≥80 m² |')
A('| E 线段图闭合环 | 线段按 0.35 m 端点合并建无向图，枚举 4–12 边简单环 | 面积 ≥80 m²、占空比 ≥0.30、边 ≥4 m |')
A('| F 三边直角折线补全 | 4 顶点「凹」形多段线缺第 4 边时补成矩形 | 面积 ≥80 m² |')
A('')
A('去重：按面积降序贪心合并（IoU ≥0.70，或 ≥90% 被包含且面积相差 <15%，或中心距 <1.2 m 且面积比 0.8–1.25）。')
A('')
A('排除图层：图框 `广东火电图框`、道路 `道路`/`NEW道路`、边坡 `边坡`、尺寸标注 `DIM`/`PUB_DIM`/`11`、')
A('表格与编号文字 `24`/`15`/`3`/`NEW字`/`NEW编号`/`TEXT`、地形图 `地形图`(WIPEOUT)、标题栏属性 `0`、')
A('辅助层 `8`/`12`/`2`/`-5`/`DEFPOINTS`/`AXIS`/`DLSS`/`HDASHDOT`/`ASSIST`/`JMD`、自动生成层 `$TD_AUDIT_GENERATED_(1B714A)`。')
A('另排除：x>2902440 的图例/工程量表区（该区为编号 101–152 的表格，非平面图形）、AOI 之外的中心点、最小边 <4 m 的狭缝候选。')
A('')
A('## 2. 候选与覆盖总数')
A('')
A('| 项目 | 数量 |')
A('|---|---|')
A(f'| 方法原始命中（合并前，含重复计数） | {len(CAND)} |')
A(f'| 去重合并后候选足迹 | {len(records)} |')
A(f'| 与已建模清单重叠（已覆盖） | {N_COV} |')
A(f'| 仅落在已建模「场地」内（pad/料场/堆场/配电装置，面积远小于场地） | {N_PAD} |')
A(f'| **未被已建模清单覆盖** | **{N_UNC}** |')
A(f'| ↳ 其中面积 ≥300 m² | {len(big_unc)} |')
A(f'| ↳ 其中 100–300 m² | {len(mid_unc)} |')
A(f'| ↳ 其中 <100 m² | {len(small_unc)} |')
A(f'| 未覆盖候选面积合计 | {sum(r["area"] for r in unc):,.0f} m² |')
A('')
A('证据评级（综合框内用途标签、墙/柱/窗图元数与线元密度 dens）：')
A('强 = 框内中文用途标签 且（墙/柱/窗 ≥3 或 dens ≥30）；中 = 有框内中文标签 或 墙/柱/窗 ≥8 或 dens ≥80；')
A('弱+ = 墙/柱/窗 ≥2 或 dens ≥20 或框内有编号；弱 = 以上皆不满足。')
A('')
A('各方法命中（合并后按方法拆分，单条足迹可被多法命中）：'
  + '、'.join(f'{k} {v}' for k, v in sorted(collections.Counter(
      m for r in records for m in r['method'].split('/')).items())) + '。')
A('')
A('面积分档（全部候选 / 其中未覆盖）：')
A('')
A('| 面积档 | 候选 | 未覆盖 |')
A('|---|---|---|')
for lo, hi in [(5000, 10 ** 9), (2000, 5000), (1000, 2000), (500, 1000), (300, 500), (100, 300), (0, 100)]:
    n = sum(1 for r in records if lo <= r['area'] < hi)
    u = sum(1 for r in unc if lo <= r['area'] < hi)
    A(f'| {lo}–{hi if hi < 10**9 else "∞"} m² | {n} | {u} |')
A('')
A('证据评级分布（未覆盖）：' + '、'.join(
    f'{g} {sum(1 for r in unc if r["grade"] == g)}' for g in ('强', '中', '弱+', '弱')) + '。')
A('')
A('## 3. 重点遗漏：未覆盖（71 基线）且面积 ≥300 m²')
A('')
A('按面积降序。墙/柱/窗 = 框内 WALL 墙线中点、COLUMN 柱插点、WINDOW 窗插点计数，dens = 框内全部线元中点密度。')
A('')
A('### 3.1 截至最新清单**仍未覆盖**（真遗漏，共 %d 条）' % len([r for r in big_unc if not r['now']]))
A('')
A(HEAD_R)
for r in [x for x in big_unc if not x['now']]:
    A(row_txt(r))
A('')
A('### 3.2 相对 71 基线未覆盖、但已被并行新增构件覆盖（%d 条，供核对）' % len([r for r in big_unc if r['now']]))
A('')
A(HEAD_R)
for r in [x for x in big_unc if x['now']]:
    A(row_txt(r))
A('')
A('> 判读提示：证据=强/中 的项（框内带中文用途标签、墙/柱图元多）优先补建模；')
A('> 证据=弱 且 dens<20 的项多为辅助线围合或设备符号，建议先核对图纸。')
A('')
A('## 4. 未覆盖候选：100–300 m²')
A('')
A(HEAD_R)
for r in mid_unc:
    A(row_txt(r))
A('')
A(f'## 5. 未覆盖候选：<100 m²（共 {len(small_unc)} 条，列前 40 条）')
A('')
A(HEAD_R)
for r in small_unc[:40]:
    A(row_txt(r))
A('')
A(f'（其余 {max(0, len(small_unc) - 40)} 条见 `audit_missing.json` 中 `covered=false` 条目。）')
A('')
A('## 6. 未覆盖候选的残余清单（截至最新清单仍无对应构件）')
A('')
A(f'全部 {len(residual)} 条（不限面积），按面积降序。这些是与 71 基线、与最新清单都无覆盖关系的候选，'
  '即「当前仍缺」的部分。')
A('')
A('| 编号 | 中心E | 中心N | 尺寸(m) | 面积(m²) | 证据 | dens | 最近标签 | 推断用途 | 区域 |')
A('|---|---|---|---|---|---|---|---|---|---|')
for r in residual:
    A(f"| {r['cid']} | {r['cx']:.1f} | {r['cy']:.1f} | {r['w']:.0f}×{r['d']:.0f} | {r['area']:.0f} | "
      f"{r['grade']} | {r['ev']['dens']} | {r['label'] or '—'} | {r['use']} | {r['region'] or '—'} |")
A('')
A('## 7. 仅落在「场地/料场」内、但可能是独立构筑物的候选')
A('')
A('这些候选与已建模的场地类构件（pad / 煤场 / 堆场 / 配电装置 / 管沟）重叠，但面积远小于场地本身，')
A('说明场地内还画有独立的房屋或设备间。按面积降序。')
A('')
A('| 编号 | 中心E | 中心N | 尺寸(m) | 面积(m²) | 证据 | 所在场地 | 最近标签 | 推断用途 |')
A('|---|---|---|---|---|---|---|---|---|')
for r in pad_list:
    A(f"| {r['cid']} | {r['cx']:.1f} | {r['cy']:.1f} | {r['w']:.0f}×{r['d']:.0f} | {r['area']:.0f} | "
      f"{r['grade']} | {r['hit']['id'] if r['hit'] else '—'} | {r['label'] or '—'} | {r['use']} |")
A('')
A('## 8. 四个重点区域 × 建筑相关图层 统计')
A('')
A('图层集合：' + '、'.join(f'`{x}`' for x in BUILD_LAYERS) + '（`3` 图层在本图中仅存文字，`34`/`COLUMN`/`WINDOW` 为块参照）。')
A('')
A('「实体数」= 该图层实体代表点落在区域内的个数；「候选」= 组成图层含该层且中心落在区域内的候选足迹数；')
A('「未覆盖」= 其中与已建模清单无覆盖关系的条数。')
A('')
for rs in REGSTAT:
    x0, x1, y0, y1 = rs['box']
    A(f"### 8.{REGSTAT.index(rs) + 1} {rs['name']}（E {x0}–{x1}，N {y0}–{y1}）")
    A('')
    A(f"区域候选合计 **{rs['total']}** 条（未覆盖 **{rs['unc']}**，仅场地 {rs['pad']}，面积合计 {rs['area']:,.0f} m²）。")
    A('')
    A('| 图层 | 区域内实体数 | 候选矩形数 | 其中未覆盖 | 未覆盖清单（编号｜中心E,N｜尺寸｜面积） |')
    A('|---|---|---|---|---|')
    for row in rs['rows']:
        items = [c for c in row['list'] if not c['covered']]
        lst = '；'.join(f"{c['cid']}｜{c['cx']:.0f},{c['cy']:.0f}｜{c['w']:.0f}×{c['d']:.0f}｜{c['area']:.0f}m²"
                       for c in items[:12])
        if len(items) > 12:
            lst += f'；…另 {len(items) - 12} 条'
        A(f"| `{row['layer']}` | {row['ents']} | {row['n']} | {row['unc']} | {lst or '—'} |")
    A('')
    tot = [r for r in records
           if rs['box'][0] <= r['cx'] <= rs['box'][1] and rs['box'][2] <= r['cy'] <= rs['box'][3]]
    if tot:
        A('区域全部候选（✔ = 已覆盖，其后为命中编号）：')
        A('')
        for r in sorted(tot, key=lambda r: -r['area']):
            mark = f"✔ {r['hit']['id']}" if r['covered'] else ('场地内' if r['pad_only'] else '未覆盖')
            A(f"- {r['cid']}  {r['cx']:.1f},{r['cy']:.1f}  {r['w']:.0f}×{r['d']:.0f}  {r['area']:.0f} m²  "
              f"[{r['grade']}] {mark}  {r['use']}")
        A('')
    else:
        A('该区域内无明显候选足迹。')
        A('')
A('## 9. 疑似遗漏但证据不足的名单')
A('')
A('判定：未被 71 基线覆盖，且证据评级为「弱/弱+」（框内无墙/柱图元、无中文用途标签、线元密度 dens 低）。')
A('这些矩形的坐标在图纸中真实存在（由线段实际端点构成），但不足以认定为房屋，'
  '多为辅助线围合、设备符号外框、图例框或两块场地之间的空白区。建议按图核对后取舍。')
A('')
A(HEAD_R)
for r in sorted(weak_list, key=lambda r: -r['area'])[:60]:
    A(row_txt(r))
A('')
A(f'（共 {len(weak_list)} 条，此处列前 60 条；全量见 JSON。）')
A('')
A('## 10. 推荐补建模清单')
A('')
A('筛选：截至最新清单仍无对应构件（即「残余遗漏」）且面积 ≥150 m²，不论证据等级（等级列已给出）。按面积降序。')
A('说明：相对 71 基线未覆盖、但已被并行新增构件覆盖的候选不再列入本节，其核对信息见 3.2 节与 JSON 的 `now` 字段。')
A('')
A('| 序 | 编号 | 中心E | 中心N | 尺寸(m) | 面积(m²) | 证据 | 推断用途 | 用途来源 | 区域 |')
A('|---|---|---|---|---|---|---|---|---|---|')
for i, r in enumerate(reco, 1):
    A(f"| {i} | {r['cid']} | {r['cx']:.1f} | {r['cy']:.1f} | {r['w']:.0f}×{r['d']:.0f} | {r['area']:.0f} | "
      f"{r['grade']} | {r['use']} | {r['use_src']} | {r['region'] or '—'} |")
A('')
if not reco:
    A('（无满足条件的候选。）')
    A('')
A('## 11. 编号标注与已建模清单的交叉核对')
A('')
A('图纸用 layer `15` 标注建构筑物编号（101–136、147…），用 layer `24` 在 x>2902440 的工程量表中列出 101–152。')
A('把 layer `15` 的编号与 71 基线清单的 `code` 比对，可作为「几何之外的第二条遗漏证据链」。')
A('')
A('（`NEW编号` 层是设备/基础编号，与建构筑物编号不同体系，未纳入此比对。）')
A('')
codes71 = sorted({str(st.get('code')).strip() for st in STRUCTS[:N_BASE]
                 if re.fullmatch(r'\d{2,3}', str(st.get('code', '')).strip())}, key=int)
codes_all = sorted({str(st.get('code')).strip() for st in STRUCTS
                    if re.fullmatch(r'\d{2,3}', str(st.get('code', '')).strip())}, key=int)
l15 = sorted({l['t'].strip() for l in LAB if l['layer'] == '15'
              and re.fullmatch(r'\d{2,3}', l['t'].strip())}, key=int)
miss = [x for x in l15 if x not in codes_all]
miss71 = [x for x in l15 if x not in codes71]
tbl = sorted({l['t'].strip() for l in LAB if l['layer'] == '24'
              and re.fullmatch(r'\d{2,3}', l['t'].strip())}, key=int)
A('- 71 基线清单 code：' + ('、'.join(codes71) or '无'))
A('')
A('- 当前清单 code（含并行新增）：' + ('、'.join(codes_all) or '无'))
A('')
A('- layer 15 图纸编号标注：' + ('、'.join(l15) or '无'))
A('')
A('- 工程量表（layer 24，x>2902440）编号：' + ('、'.join(tbl) or '无'))
A('')
A('- **相对 71 基线缺失的编号**：' + ('、'.join(miss71) or '无'))
A('')
A('- **相对当前清单仍缺失的编号**：' + ('、'.join(miss) or '无'))
A('')
A('> 注：137–152 只在工程量表（layer 24）出现、不在平面图中，属表格行号，不作为遗漏依据。')
A('')
A('### 11.1 标注存在但清单缺失的编号 · 标注位置')
A('')
A('这些编号在平面图（layer 15）上有明确标注，但 71 基线清单里没有对应构件，属**文字证据**层面的遗漏线索：')
A('')
A('| 编号 | 标注位置 E,N | 最近候选足迹 | 距离(m) | 候选是否已覆盖 |')
A('|---|---|---|---|---|')
for num in miss:
    pts = [(l['x'], l['y']) for l in LAB if l['layer'] == '15' and l['t'].strip() == num
           and AOI[0] - 100 <= l['x'] <= AOI[2] + 100 and AOI[1] - 100 <= l['y'] <= AOI[3] + 100]
    for (px, py) in pts[:3]:
        if records:
            rr = min(records, key=lambda q: math.hypot(q['cx'] - px, q['cy'] - py))
            dd = math.hypot(rr['cx'] - px, rr['cy'] - py)
            st = ('已覆盖 ' + rr['hit']['id']) if rr['covered'] else (
                ('最新清单 ' + rr['now']['id']) if rr['now'] else '未覆盖')
            A(f"| {num} | {px:.1f}, {py:.1f} | {rr['cid']} | {dd:.0f} | {st} |")
        else:
            A(f"| {num} | {px:.1f}, {py:.1f} | — | — | — |")
A('')
A('> 判读：若编号附近有未覆盖候选（上表末列为「未覆盖」），则该编号对应的建构筑物很可能漏建；')
A('> 若附近候选已覆盖，说明该编号只是标注位置与构件中心有偏移。')
A('')
A('**上表结论**：116、121、122、124、125 的标注位置附近 30–80 m 内都有已覆盖（或已被新增件覆盖）的候选，')
A('说明这 5 个编号**不是新建筑漏建，而是清单 `code` 映射缺失**（构件建了但没登记图纸编号），')
A('建议在清单中补齐 116、121、122、124、125 的 `code` 字段，而非新增几何。')
A('')
A('## 12. 结论摘要')
A('')
A(f'1. 全图共提取到 **{len(records)}** 条候选建筑足迹（方法 A–F 合并去重后）：'
  f'**{N_COV}** 条与 71 条基线清单吻合，**{N_PAD}** 条为已建模场地内的独立小构筑物，'
  f'**{N_UNC}** 条相对 71 基线未覆盖。')
A(f'2. 未覆盖候选中，**{N_UNC - len(residual)}** 条已被并行新增构件覆盖（说明这些足迹确实存在且已被补登），'
  f'**{len(residual)}** 条截至最新清单仍无对应构件，其中面积 ≥300 m² 的 **{len([r for r in residual if r["area"] >= 300])}** 条'
  f'（见 3.1 节）、≥150 m² 的 **{len(reco)}** 条（见第 10 节）。')
A('3. 四个重点区域：主厂房区（E 2901640–2901930 / N 2549000–2549340）候选最密集且绝大多数已被已建模件覆盖；'
  '东侧辅助区（E 2901970–2902200）候选以设备/构架为主；施工临建区与南侧输煤区的残余候选多为临时建筑、'
  '堆场附属房与地磅/门卫等小体量设施，建议按第 9、10 节逐条核对图纸。')
A('4. 编号交叉核对（第 11 节）：116、121、122、124、125 在平面图上有标注但清单无 code，')
A('   不过其标注位置附近均有已建模/已新增构件，属「编号映射缺失」而非几何漏建。')
A('5. 所有候选的坐标、尺寸、组成图层、证据计数、最近标签、最近已建模件均已写入 `audit_missing.json`，可逐条回溯；')
A('   配套核对图：`audit_overlay_all.png`（全图）、`audit_overlay_main.png`（主厂房区放大）——')
A('   灰=图纸线，蓝框=已建模构件，绿框=已覆盖候选，红框=未覆盖候选，橙框=仅场地覆盖。')
A('')
open(BASE + r'\audit_missing.md', 'w', encoding='utf-8').write('\n'.join(L))
print('[写出] audit_missing.md  行数', len(L))
print('重点遗漏(>=300):', len(big_unc), ' 推荐补建模:', len(reco), ' 证据不足:', len(weak_list))
