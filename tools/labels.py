# -*- coding: utf-8 -*-
"""Clean text extraction: strip AutoCAD formatting codes, group labels by region."""
import json, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ENTS = json.load(open(r'D:\test\.dwgconv\out\entities.json', encoding='utf-8'))

FMT = re.compile(r'\{\\[^;{}]*;([^{}]*)\}')
def clean(s):
    if not s:
        return ''
    s = s.replace('%%c', 'Φ').replace('%%d', '°').replace('%%p', '±')
    prev = None
    while prev != s:
        prev = s
        s = FMT.sub(lambda m: m.group(1), s)
    s = s.replace('{', '').replace('}', '')
    s = s.replace('\\P', ' | ').replace('\\p', ' | ')
    s = re.sub(r'\\[A-Za-z][^;\\]*;', '', s)
    s = re.sub(r'\\[A-Za-z~]', '', s)
    return ' '.join(s.split())

labels = []
for e in ENTS:
    if e['type'] not in ('TEXT', 'MTEXT', 'ATTRIB'):
        continue
    p = e.get('position')
    t = clean(e.get('text'))
    if not p or not t:
        continue
    labels.append({'x': p[0], 'y': p[1], 't': t, 'layer': e['layer'], 'ty': e['type']})

print('labels', len(labels))
json.dump(labels, open(r'D:\test\.dwgconv\labels.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

def dump(x0, y0, x1, y1, title):
    print(f'\n===== {title}  x[{x0},{x1}] y[{y0},{y1}] =====')
    sel = [l for l in labels if x0 <= l['x'] <= x1 and y0 <= l['y'] <= y1]
    sel.sort(key=lambda l: (-l['y'], l['x']))
    for l in sel:
        print(f"({l['x']:9.1f},{l['y']:9.1f}) [{l['layer']:>10}] {l['t']}")

# Cluster A regions quadrants
dump(2900800, 2549000, 2902820, 2549760, 'A-TOP')
dump(2900800, 2548280, 2902820, 2549000, 'A-BOTTOM')
dump(2910650, 2534480, 2911780, 2535060, 'B')
