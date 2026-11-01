# -*- coding: utf-8 -*-
"""Build extra.json (omitted structures) from the geometric audit + manual fixes."""
import json, math, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA = json.load(open(r'D:\test\.dwgconv\plant-data.json', encoding='utf-8'))
AUD = json.load(open(r'D:\test\.dwgconv\audit_missing.json', encoding='utf-8'))
EST = '【图纸信息不足，尺寸为火电工程常规估算值，待复核】'
EXCLUDE_CID = {'C0012', 'C0019', 'C0020', 'C0030'}   # 出线走廊/冷却塔区围合，证据不足以判定为建筑
LV = re.compile(r'^\d{2,3}\.\d{1,2}$')

def box(s):
    w, d, rot = s.get('w', 0), s.get('d', 0), math.radians(s.get('rot', 0) or 0)
    c, si = abs(math.cos(rot)), abs(math.sin(rot))
    return (s['x'] - (w/2*c + d/2*si), s['y'] - (w/2*si + d/2*c),
            s['x'] + (w/2*c + d/2*si), s['y'] + (w/2*si + d/2*c))
SB = [box(s) for s in DATA['structures']
      if not (s['id'].startswith('ST-Y') or s['id'] == 'ST-X00' or s['id'] in ('ST-C05', 'ST-C06', 'ST-C07'))]

def ov(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return 0.0 if x1 <= x0 or y1 <= y0 else (x1 - x0) * (y1 - y0)

items = []

# ---------- 1) 手工补录：图上明确存在但首版遗漏的构筑物 ----------
MAN = [
 dict(id='ST-C05', code='配电房', name='施工配电房', cat='existing', shape='box',
      x=2901370, y=2549155, w=12, d=8, h=5, rot=0, area=96,
      note='施工区配电房（图纸“配电房”标注），邻近“水池”标注',
      src='位置：图纸 PUB_TEXT 标注“配电房”(2901370,2549155)；平面尺寸按常规配电房估算' + EST),
 dict(id='ST-C06', code='一期', name='一期综合楼（餐厅/杂物间/农药间/化肥间）', cat='existing', shape='box',
      x=2901564, y=2548893, w=47, d=28, h=8, rot=0, area=1316,
      note='图面标注餐厅、房间×10、杂物间×3、农药间×2、化肥间，附窗/柱插入块，判断为单层后勤综合楼',
      src='平面轮廓：图纸 WINDOW/COLUMN 插入块与房间标注范围 (2901540,2548878)-(2901587,2548910)；层高按单层常规值' + EST),
 dict(id='ST-C07', code='一期', name='养护池', cat='existing', shape='pit',
      x=2901535, y=2548601, w=20, d=12, h=2.5, rot=0, area=240,
      note='混凝土构件养护池', src='位置：图纸 PUB_TEXT 标注“养护池”(2901535,2548601)；尺寸估算' + EST),
 dict(id='ST-X00', code='130', name='条形露天煤场（3#煤场条带）', cat='coal', shape='coalheap',
      x=2902225.4, y=2549125.6, w=45, d=128, h=12, rot=0, area=5760,
      note='与1#、2#干煤棚并列的第三条煤场条带（图面实测45×128m），按露天堆煤考虑',
      src='平面轮廓：图纸实测矩形 (2902203,2549062)-(2902248,2549190)'),
]

CJK = re.compile(r'[\u4e00-\u9fff]')
MANB = [box(m) for m in MAN]

BND = [tuple(p) for p in DATA['boundary']]
def in_boundary(x, y):
    n, c = len(BND), False
    j = n - 1
    for i in range(n):
        xi, yi = BND[i]; xj, yj = BND[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            c = not c
        j = i
    return c

def quad_edges(pts):
    """edge lengths of a 4-point outline"""
    n = len(pts)
    L = [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]
    return L

for r in AUD:
    if r['area'] < 120:
        continue
    if r.get('cid') in EXCLUDE_CID:
        continue
    if not (2900900 < r['cx'] < 2902450 and 2548500 < r['cy'] < 2549700):
        continue
    if not in_boundary(r['cx'], r['cy']):
        continue                                    # 厂界之外的图面元素（边坡/沟/一期用地）不纳入
    if any((l.get('t') or '').strip() in ('hm', 'hm2', 'hm²') for l in (r.get('labels') or [])):
        continue                                    # 用地指标表框，非建筑
    bb = (r['x0'], r['y0'], r['x1'], r['y1'])
    ar = max(1e-6, (bb[2] - bb[0]) * (bb[3] - bb[1]))
    if any(ov(bb, b) / ar > 0.30 for b in SB):
        continue
    if any(ov(bb, b) / ar > 0.30 for b in MANB):
        continue
    a = r['area']
    lab = (r['label'] or '').strip()
    reg = r['region'] or '厂区'
    # 真实矩形边长：旋转四边形取两条相邻边，其余退回 bbox
    w, d = round(r['w'], 1), round(r['d'], 1)
    ol = r.get('outline') or []
    if len(ol) == 4 and abs(r['rot']) > 0.5:
        L = quad_edges([tuple(p) for p in ol])
        w, d = round(L[0], 1), round(L[1], 1)
        if w * d < 0.6 * a:              # 兜底
            w, d = round(r['w'], 1), round(r['d'], 1)
    # 类别与体量
    nelect = min(w, d)
    near_water = math.hypot(r['cx'] - 2902119, r['cy'] - 2549404) < 95
    if a >= 9000:
        sh, h, cat = 'pad', 0.4, 'construction'
    elif nelect < 3.5 and max(w, d) > 25:
        sh, h, cat = 'retaining', 3, 'existing'
    elif near_water and a < 1500:
        sh, h, cat = 'pit', 4, 'aux'
    elif a >= 3000:
        sh, h, cat = 'box', 8, 'existing'
    elif a < 300:
        sh, h, cat = 'box', 6, 'existing'
    elif a < 1200:
        sh, h, cat = 'box', 10, 'existing'
    else:
        sh, h, cat = 'box', 14, 'existing'
    extra, cjk = '', ''
    if LV.match(lab):
        extra = f'；图注室内地坪标高 {lab} m（据此判定为建筑物）'
    elif re.match(r'^\d{1,3}$', lab):
        extra = f'；图注编号 {lab}（一期既有编号体系）'
    elif CJK.search(lab) and len(lab) <= 14:
        cjk = lab
    if sh == 'pit':
        nm = f'净水站水池/沉淀池（{w}×{d}m）'
    elif sh == 'retaining':
        nm = f'挡墙/围墙段（{w}×{d}m）'
    elif sh == 'pad':
        nm = f'场地（{reg} {w}×{d}m）'
    else:
        nm = f'建构筑物（{cjk or (reg + " " + str(w) + "×" + str(d) + "m")}）'
    items.append(dict(
        id='ST-Y%02d' % (len(items) + 1), code=(lab if re.match(r'^\d{1,3}$', lab) else ''),
        name=nm, cat=cat, shape=sh, x=round(r['cx'], 1), y=round(r['cy'], 1),
        w=w, d=d, h=h, rot=(round(r['rot'], 1) if abs(r['rot']) >= 6.5 else 0), area=round(a),
        note=f'平面轮廓由图面闭合线实测（{w}×{d}m，旋转 {r["rot"]:.1f}°），图纸未标注中文名称' + extra,
        src='图纸闭合轮廓自动提取，与已建构件及一览表比对后补录；功能待现场复核'))

MAN2 = [
 dict(id='ST-Z01', code='', name='输煤栈桥（煤场东段）', cat='coal', shape='gallery',
      x=2902351.9, y=2549212.4, w=4, d=28, h=9, rot=0, area=112,
      note='煤场至输煤系统的架空输煤栈桥段，图面实测宽4m；按转角处两段简化为一段',
      src='图面实测狭长闭合轮廓 (2902349,2549205)-(2902355,2549220)；' + EST),
 dict(id='ST-Z02', code='', name='输煤转运站（煤场北侧，推定）', cat='coal', shape='box',
      x=2902313.4, y=2549214.6, w=13, d=8, h=18, rot=0, area=110,
      note='栈桥转向处转运站，方形小体量建筑，高度按常规转运站估算',
      src='图面实测轮廓 13×8m；功能按位置推定为输煤转运站（一览表137–142未在平面标注）' + EST),
 dict(id='ST-Z03', code='', name='输煤转运站（煤场西侧，推定）', cat='coal', shape='box',
      x=2902273.1, y=2549185.8, w=8, d=13, h=18, rot=0, area=110,
      note='煤场西侧栈桥转运站', src='图面实测轮廓 8×13m；' + EST),
 dict(id='ST-Z04', code='', name='建构筑物（东侧辅助区 36.0×18.0m）', cat='aux', shape='box',
      x=2902065.9, y=2549080.3, w=36, d=18, h=10, rot=0, area=648,
      note='图面闭合轮廓实测，未标注中文名称，邻近图注编号22；按附属生产建筑建模',
      src='图面实测闭合轮廓；高度为常规估算值' + EST),
 dict(id='ST-Z05', code='', name='建构筑物（东侧辅助区 46.8×12.0m）', cat='aux', shape='box',
      x=2902130.3, y=2549113.3, w=46.8, d=12, h=10, rot=0, area=562,
      note='图面闭合轮廓实测，框内标注 90.70 地坪标高，判定为建筑物',
      src='图面实测闭合轮廓；' + EST),
 dict(id='ST-Z06', code='', name='建构筑物（主厂房区 18.0×22.3m）', cat='main', shape='box',
      x=2901918.4, y=2549244.8, w=18, d=22.3, h=12, rot=0, area=401,
      note='主厂房东侧附属建筑，图面实测轮廓，未标注名称', src='图面实测闭合轮廓；' + EST),
 dict(id='ST-Z07', code='', name='建构筑物（东侧辅助区 28.0×14.0m）', cat='aux', shape='box',
      x=2902060.1, y=2549049.6, w=28, d=14, h=10, rot=0, area=385,
      note='东侧辅助区附属建筑，邻近图注编号30', src='图面实测闭合轮廓；' + EST),
 dict(id='ST-Z08', code='', name='建构筑物（东侧辅助区 20.0×18.0m）', cat='aux', shape='box',
      x=2901994.9, y=2549049.6, w=20, d=18, h=10, rot=0, area=360,
      note='东侧辅助区附属建筑，框内标注 90.70 地坪标高', src='图面实测闭合轮廓；' + EST),
 dict(id='ST-Z09', code='S-27', name='施工板房建筑群（办公及班房）', cat='construction', shape='box',
      x=2901408.7, y=2549139.4, w=152, d=49, h=6, rot=0, area=6188,
      note='图面框内含 93 段墙线、114 个柱点与 2 处处窗，判定为活动板房/临建房屋群，含施工办公与班房',
      src='图面闭合轮廓 152×49m 且框内 WALL/COLUMN 实体密集（审计 C0007）；层高按活动板房估算' + EST),
 dict(id='ST-Z10', code='S-28', name='构件预制场（围栏场地）', cat='construction', shape='pad',
      x=2901540.5, y=2549469.7, w=121, d=44, h=0.4, rot=0, area=5276,
      note='构件预制场实际围合范围（较原标注面积换算范围更大），场地平整+硬化',
      src='图面闭合轮廓 121×44m（审计 C0011），与“构件预制场5200m2”标注对应'),
 dict(id='ST-Z11', code='', name='建构筑物（施工区 35.0×31.0m）', cat='construction', shape='box',
      x=2901647.2, y=2548982.2, w=35, d=31, h=6, rot=0, area=1096,
      note='重大件堆场内独立建筑/棚库，图面实测轮廓', src='图面实测闭合轮廓（审计 C0023）；' + EST),
 dict(id='ST-Z12', code='147', name='输煤栈桥（147，主厂房西侧）', cat='coal', shape='gallery',
      x=2901846.0, y=2549092.0, w=8.2, d=216, h=13, rot=0, area=1771,
      note='南北向架空输煤栈桥，南接输煤系统、北接除氧煤仓间；图面为三道平行线围合的 8.2m 宽廊道，长 216m',
      src='图面实测：x=2901841.8/2901845.9/2901850.0 三道平行线，y 2548984–2549200；'
          '图纸编号标注 147（层15，圆心 2901838.7,2549081.7），一览表未列该项，属后期变更'),
 dict(id='ST-Z13', code='', name='施工用电场地（变压器E4 区）', cat='construction', shape='pad',
      x=2901581.2, y=2549039.3, w=160, d=25, h=0.4, rot=0, area=4059,
      note='施工区变压器 E4（630KVA）及其配电线路走廊围合场地',
      src='图面闭合轮廓 160×25m（审计 C0014）；框内无墙线/柱点，按场地处理'),
]



# 互斥去重：被更大候选覆盖 55% 以上的视为同一构筑物的重复检出
items.sort(key=lambda d: -d['area'])
_kept = []
for it in items:
    bb = (it['x'] - it['w'] / 2, it['y'] - it['d'] / 2, it['x'] + it['w'] / 2, it['y'] + it['d'] / 2)
    a = max(1e-6, it['w'] * it['d'])
    dup = False
    for k in _kept:
        kb = (k['x'] - k['w'] / 2, k['y'] - k['d'] / 2, k['x'] + k['w'] / 2, k['y'] + k['d'] / 2)
        if ov(bb, kb) / a > 0.55:
            dup = True
            break
    if not dup:
        _kept.append(it)
items = sorted(_kept, key=lambda d: -d['area'])
for i, it in enumerate(items):
    it['id'] = 'ST-Y%02d' % (i + 1)

MAN3 = [
 dict(id='ST-D01', code='124', name='边坡（东侧纵向段）', cat='construction', shape='retaining',
      x=2902173.5, y=2548989.0, w=481, d=2, h=1.2, rot=0, area=962,
      note='厂区东侧挖填边坡坡顶线，图面实测线长 481 m', src='图面“边坡”图层实测线段 (2901933,2548989)-(2902414,2548989)'),
 dict(id='ST-D02', code='124', name='边坡（南侧段）', cat='construction', shape='retaining',
      x=2902274.0, y=2548967.0, w=324, d=2, h=1.2, rot=0, area=648,
      note='厂区南侧边坡线', src='图面“边坡”图层实测线段 (2902112,2548967)-(2902436,2548967)'),
 dict(id='ST-D03', code='124', name='边坡（煤场东侧纵向段）', cat='construction', shape='retaining',
      x=2902176.5, y=2549147.0, w=2, d=254, h=1.2, rot=0, area=508,
      note='煤场东侧边坡（双线，取中线 x=2902176.5）', src='图面实测 (2902174/2902179, 2549020-2549274)'),
 dict(id='ST-D04', code='124', name='边坡（东边界段）', cat='construction', shape='retaining',
      x=2902414.5, y=2549111.5, w=2, d=245, h=1.2, rot=0, area=490,
      note='厂区东边界边坡', src='图面实测 (2902414.5, 2548989-2549234)'),
 dict(id='ST-D05', code='124', name='边坡（东北段）', cat='construction', shape='retaining',
      x=2902343.0, y=2549234.0, w=144, d=2, h=1.2, rot=0, area=288,
      note='东北角边坡', src='图面实测 (2902271-2902415, 2549234)'),
 dict(id='ST-D06', code='124', name='边坡（北侧段）', cat='construction', shape='retaining',
      x=2902204.0, y=2549491.0, w=2, d=152, h=1.2, rot=0, area=304,
      note='北侧边坡', src='图面实测 (2902204, 2549415-2549567)'),
 dict(id='ST-D07', code='124', name='边坡（东北斜向段）', cat='construction', shape='retaining',
      x=2902225.0, y=2549279.0, w=128, d=2, h=1.2, rot=-44.4, area=256,
      note='东北角斜向边坡（旋转 44.4°）', src='图面实测 (2902179,2549324)-(2902271,2549234)'),
 dict(id='ST-D08', code='116', name='围栅（500kV 配电装置北侧）', cat='electrical', shape='retaining',
      x=2901759.0, y=2549444.5, w=200, d=0.3, h=2.2, rot=0, area=60,
      note='升压站围栅，镀锌钢丝网+立柱，高 2.2 m', src='位置：图纸“围栅”标注点(2901843,2549242)；范围按119场地外扩围合'),
 dict(id='ST-D09', code='116', name='围栅（南侧）', cat='electrical', shape='retaining',
      x=2901759.0, y=2549313.5, w=200, d=0.3, h=2.2, rot=0, area=60,
      note='升压站围栅南段', src='同上'),
 dict(id='ST-D10', code='116', name='围栅（西侧）', cat='electrical', shape='retaining',
      x=2901659.0, y=2549379.0, w=0.3, d=131, h=2.2, rot=0, area=39,
      note='升压站围栅西段', src='同上'),
 dict(id='ST-D11', code='116', name='围栅（东侧）', cat='electrical', shape='retaining',
      x=2901859.0, y=2549379.0, w=0.3, d=131, h=2.2, rot=0, area=39,
      note='升压站围栅东段', src='同上'),
 dict(id='ST-D12', code='44', name='净水站沉淀池（编号44）', cat='aux', shape='pit',
      x=2902129.9, y=2549350.9, w=41.4, d=17.6, h=4, rot=0, area=729,
      note='净水站反应沉淀池组之一，框内标注编号 44', src='图面实测闭合轮廓 41.4×17.6m（审计 C0030）'),
]

out = MAN + MAN2 + MAN3 + items
for o in out:
    if '图纸信息不足' not in (o.get('note') or ''):
        o['note'] = (o.get('note') or '') + EST
    if '图纸信息不足' not in (o.get('src') or '') and '实测' not in (o.get('src') or ''):
        o['src'] = (o.get('src') or '') + EST
json.dump(out, open(r'D:\test\.dwgconv\extra.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('manual', len(MAN), 'audited', len(items), 'total', len(out))
for o in out:
    print(f"{o['id']:9s} {o['area']:7d} {o['w']:6.1f}x{o['d']:6.1f} {o['shape']:9s} h={str(o['h']):<5} ({o['x']:.0f},{o['y']:.0f}) {o['name']}")
