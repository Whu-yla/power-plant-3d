# -*- coding: utf-8 -*-
"""Dump ALL non-numeric text labels in cluster A, grouped by area, to find missed structures."""
import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
L = json.load(open(r'D:\test\.dwgconv\labels.json', encoding='utf-8'))
num = re.compile(r'^[\d\.,:\s\+\-=/()mA-Za-z\u00b1\u03a6\u00b0]{1,14}$')
seen = set()
rows = []
for l in L:
    x, y = l['x'], l['y']
    if not (2900900 < x < 2902450 and 2548300 < y < 2549700):
        continue
    t = l['t'].strip()
    if len(t) < 2 or num.match(t):
        continue
    # 去掉纯尺寸/标高
    if re.fullmatch(r'[\d\.]+', t):
        continue
    k = (round(x / 3), round(y / 3), t[:14])
    if k in seen:
        continue
    seen.add(k)
    rows.append((round(y), round(x), l['layer'], t[:60]))
rows.sort(reverse=True)
print(len(rows), 'labels')
for y, x, lay, t in rows:
    print(f"{x:8d} {y:8d} {lay:<14} {t}")
