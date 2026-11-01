# -*- coding: utf-8 -*-
"""二期编号(101-142) 在平面图上的位置标注：layer 15/3/24/8 且 x<2902440。"""
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
L = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))
rows = []
for l in L:
    x, y = l['x'], l['y']
    if not (2900800 < x < 2902440 and 2548300 < y < 2549800): continue
    t = l['t'].strip()
    if not re.fullmatch(r'\d{3}', t): continue
    n = int(t)
    if not (101 <= n <= 142): continue
    rows.append((n, x, y, l['layer'], l['ty']))
rows.sort()
print(len(rows), 'numbered plan labels')
for n, x, y, lay, ty in rows:
    print(f"  {n}  ({x:9.1f}, {y:9.1f})  {lay:<14} {ty}")
