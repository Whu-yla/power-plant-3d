// build-docs.mjs —— 由 plant-data.js 生成 readme.md 与 docs/archive/3d-powerplant-asset.md
// 用法：node build-docs.mjs  （在 D:\test\.dwgconv 下）
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const HERE = 'D:/test/.dwgconv';
const SRC_DIR = 'D:/test/src/3d-powerplant';
const OUT_README = path.join(SRC_DIR, 'readme.md');
const OUT_ASSET = 'D:/test/docs/archive/3d-powerplant-asset.md';

// ---------- 1. 载入数据 ----------
const code = fs.readFileSync(path.join(SRC_DIR, 'plant-data.js'), 'utf8');
const win = {};
vm.createContext(win);
vm.runInContext(code, win);
const D = win.PLANT_DATA;
const S = D.structures, ROADS = D.roads, BOUND = D.boundary, TREES = D.trees;

// ---------- 2. 常量与工具 ----------
const CAT_ORDER = ['main', 'electrical', 'aux', 'cooling', 'coal', 'living', 'construction'];
const CAT_LABEL = {
  main: '主厂房及生产系统',
  electrical: '电气与配电装置',
  aux: '辅助生产设施',
  cooling: '循环水系统',
  coal: '输煤贮煤系统',
  living: '生活与场前区',
  construction: '施工临建',
};
const CAT_DESC = {
  main: '汽机房、除氧煤仓间、锅炉房、电除尘、烟囱、烟道、天桥等',
  electrical: '500 kV 配电装置、主变/厂用变/备用变、防火墙、事故油池',
  aux: '石灰石粉仓、门卫、干灰库、气化风机房、净水站、制氢站、化水间',
  cooling: '两座双曲线冷却塔、循环水泵房、加氯间、压力钢管',
  coal: '条形煤场、挡煤墙、圆形封闭煤仓、卸煤槽',
  living: '食堂、宿舍楼、停车场、水池',
  construction: '施工临建场地、库房、组合场、办公与生活区（26 项）',
};
const MARK = '【图纸信息不足';
const fmt = (n) => (n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 1 }));
const isCircular = (s) => s.w == null;
const dimText = (s) => (isCircular(s) ? `Ø${fmt(s.d)}` : `${fmt(s.w)}×${fmt(s.d)}`);
const hText = (s) => (s.h === 0 ? '0（场坪）' : fmt(s.h));
const cell = (t) => String(t).replace(/\|/g, '／').replace(/\r?\n/g, ' ');
const brief = (note, max = 26) => {
  let t = String(note || '').split('；')[0].trim();
  if (t.length > max) t = t.slice(0, max) + '…';
  return t || '—';
};
const isEst = (s) => (String(s.src || '') + String(s.note || '')).includes(MARK);
const srcTag = (s) => {
  const t = String(s.src || '') + String(s.note || '');
  let k;
  if (/实测|同上|圆心|半径|圆弧/.test(t)) k = '实测';
  else if (/推定|推判|未见/.test(t)) k = '推定';
  else if (/一览表/.test(t)) k = '一览表';
  else k = '标注';
  return isEst(s) ? `${k}·估算` : k;
};

// 估算原因映射（按 id，覆盖全部 58 项）
const R = {
  'ST-108': '烟囱高度 210 m 与底径 Ø16.4 m 由一览表面积反推，图面无高度标注',
  'ST-127A': '塔高 130 m 按常规取值；塔径 102 m 由图面半圆反算',
  'ST-104A': '送风机支架平面按 18×12 m 常规估算',
  'ST-104B': '送风机支架平面按 18×12 m 常规估算',
  'ST-105A': '电除尘器按 2,820 m² 两台均分、单体约 40×35 m 估算',
  'ST-105B': '电除尘器按 2,820 m² 两台均分、单体约 40×35 m 估算',
  'ST-106A': '引风机支架平面按 26×18 m 常规估算',
  'ST-106B': '引风机支架平面按 26×18 m 常规估算',
  'ST-107': '烟道平面按 30×14 m 常规估算，断面尺寸图面未标注',
  'ST-109': '空压机及电除尘配电室平面、高度为常规估算',
  'ST-119': '26,300 m² 取自一览表；200×131 m 场地划分与 26 m 构架为估算',
  'ST-130D': '直径 Ø72 m 为图面 R36 圆弧实测；圆形煤仓功能定位按相邻输煤设施推判',
  'ST-130E': '直径 Ø72 m 为图面 R36 圆弧实测；圆形煤仓功能定位按相邻输煤设施推判',
  'ST-110A': '主变压器外形与间距按常规估算',
  'ST-110B': '主变压器外形与间距按常规估算',
  'ST-111A': '厂用变压器外形按常规估算',
  'ST-111B': '厂用变压器外形按常规估算',
  'ST-112': '防火墙长度与断面按常规估算',
  'ST-113': '备用变压器外形按常规估算',
  'ST-117': '变压器事故油池尺寸按常规估算',
  'ST-118': '透平机事故油池尺寸按常规估算',
  'ST-114': '石灰石粉仓直径（Ø14 m）与高度为常规估算',
  'ST-123': '传达门卫平面与高度为常规估算',
  'ST-129': '循环水泵加氯间平面为常规估算',
  'ST-131': '干灰库高度按常规估算；图面文字 Ф15 m 与数据 Ø17 m 存在差异',
  'ST-132': '气化风机房平面为常规估算',
  'ST-135': '净水站 2,180 m² 取一览表，50×44 m 布置为估算',
  'ST-C01': '食堂平面尺寸为常规估算',
  'ST-C02': '宿舍楼平面尺寸为常规估算',
  'ST-120': '连接天桥跨度与断面为常规估算',
  'ST-136': '图中无明确标注点，位置按铁路线与输煤系统走向推定；尺寸为估算',
  'ST-128': '管线走向按两处编号点推定，长度与面积为常规估算（记录面积与外包矩形偏差较大）',
};
for (let i = 1; i <= 26; i++) {
  R['ST-S-' + String(i).padStart(2, '0')] = '平面尺寸按标注面积换算，建筑高度与形式为估算';
}
const reasonOf = (s) => R[s.id] || '图纸信息不足，按常规工程取值';

// ---------- 3. 统计 ----------
const stats = { cats: {}, areaAll: 0, est: 0, tall: 0, flat: 0 };
for (const s of S) {
  stats.cats[s.cat] = stats.cats[s.cat] || { n: 0, area: 0 };
  stats.cats[s.cat].n++;
  stats.cats[s.cat].area += s.area || 0;
  stats.areaAll += s.area || 0;
  if (isEst(s)) stats.est++;
  if ((s.h || 0) > 0.5) stats.tall++; else stats.flat++;
}

// ---------- 4. 生成各段 ----------
// 4.3 构件清单
let structTables = '';
for (const cat of CAT_ORDER) {
  const list = S.filter((s) => s.cat === cat);
  structTables += `#### ${CAT_LABEL[cat]}（\`${cat}\`，${list.length} 项）\n\n`;
  structTables += '| 编号 | 名称 | 平面尺寸(m) | 高度(m) | 占地面积(m²) | 数据来源 | 备注（`id` · 说明） |\n';
  structTables += '|---|---|---|---:|---:|---|---|\n';
  for (const s of list) {
    structTables += `| ${cell(s.code)} | ${cell(s.name)} | ${dimText(s)} | ${hText(s)} | ${fmt(s.area)} | ${srcTag(s)} | \`${s.id}\` · ${cell(brief(s.note))} |\n`;
  }
  structTables += '\n';
}

// 4.4 类别统计
let catTable = '| 类别 | 代码 | 构件数 | 占地面积(m²) | 占构件占地 | 主要内容 |\n|---|---|---:|---:|---:|---|\n';
for (const cat of CAT_ORDER) {
  const c = stats.cats[cat];
  const pct = ((c.area / stats.areaAll) * 100).toFixed(1) + '%';
  catTable += `| ${CAT_LABEL[cat]} | \`${cat}\` | ${c.n} | ${fmt(c.area)} | ${pct} | ${CAT_DESC[cat]} |\n`;
}
catTable += `| **合计** | — | **${S.length}** | **${fmt(stats.areaAll)}** | 100% | 含施工临建 ${fmt(stats.cats.construction.area)} m²（临时用地） |\n`;

// 5.2 估算项清单
const estList = S.filter(isEst);
let estTable = '| 编号 | 名称 | 数据 id | 估算内容与依据 |\n|---|---|---|---|\n';
for (const s of estList) {
  estTable += `| ${cell(s.code)} | ${cell(s.name)} | \`${s.id}\` | ${cell(reasonOf(s))} |\n`;
}
const noReason = S.filter((s) => isEst(s) && !R[s.id]).map((s) => s.id);
if (noReason.length) console.error('!! 缺少估算原因:', noReason.join(', '));

// 附录 A
let appendix = '';
for (const s of S) {
  appendix += `- \`${s.id}\` **${s.name}**（编号 ${s.code}）：${s.src || '—'}\n`;
}

// 文件清单
const FILE_PURPOSE = [
  ['index.html', '页面骨架：三维视口、信息面板、工具栏（线框/光照/标注/显隐/复位）、文字标注层'],
  ['style.css', '深色主题界面样式（面板、工具条、按钮、标注标签）'],
  ['main.js', '场景与相机初始化、交互（旋转/缩放/平移/双击聚焦）、拾取与信息面板、显示开关、`PlantApp` 钩子与 `postMessage` 桥接'],
  ['builders.js', '各类 `shape` 的几何构建函数注册表（box/gantry/duct/chimney/transformer/tank/pit/switchyard/gallery/hyperbolic/pipes/coalheap/retaining/dome/pad）'],
  ['plant-data.js', '唯一数据源：`meta` + `structures` + `roads` + `boundary` + `trees`'],
  ['readme.md', '项目说明文档（本文件，由 `build-docs.mjs` 从数据文件生成表格）'],
  ['vendor/three.min.js', 'Three.js r13x UMD 构建（全局 `THREE`），本地引入、离线可用'],
  ['vendor/OrbitControls.js', '轨道控制器 UMD 版本（旋转/缩放/平移/阻尼）'],
];
const sizeText = (p) => {
  try {
    const b = fs.statSync(p).size;
    return b < 1024 ? `${b} B` : `${(b / 1024).toFixed(1)} KB`;
  } catch {
    return '—（并行开发中）';
  }
};
const kbLabel = (n) => `${(n / 1024).toFixed(1)} KB`;
const buildFileTable = (readmeSize) => {
  let t = '| 文件 | 用途 | 大小 |\n|---|---|---:|\n';
  for (const [rel, purpose] of FILE_PURPOSE) {
    const size = rel === 'readme.md' && readmeSize ? readmeSize : sizeText(path.join(SRC_DIR, rel));
    t += `| \`${rel}\` | ${purpose} | ${size} |\n`;
  }
  return t;
};

// 解析过程资产
const PROC = [
  ['dump.mjs', '调用 `@mlightcad/libredwg-web` 导出模型空间实体（类型/图层/坐标/多段线顶点与 bulge/文字）', '约 4 KB'],
  ['labels.py', '清洗文字实体，生成 `labels.json`（612 条）', '约 2 KB'],
  ['raster.py / raster2.py', '按图层光栅化核对（`g_all.png`、`g_main.png`、`g_sub.png` 及局部放大图）', '各约 3 KB'],
  ['an14.py / an17.py', 'bulge=1 半圆反算圆心与半径；编号标注点坐标定位', '各约 4 KB'],
  ['an19.py', '道路双线配对为路面四边形，输出 `quads.json`（140 段）', '约 5 KB'],
  ['mkdata.py', '按标定结果组装 `plant-data.js`（坐标换算、构件属性、道路、边界、树点）', '约 20 KB'],
  ['docstats.mjs', '统计校核（类别/面积/偏差/道路宽度），支撑文档数字', '约 3 KB'],
  ['build-docs.mjs', '由 `plant-data.js` 生成 `readme.md` 与本资产说明，保证文档数字与数据同源', '约 13 KB'],
  ['package.json', '解析依赖声明：`{"@mlightcad/libredwg-web": "^0.8.2"}`', '< 1 KB'],
  ['labels.json', '图纸文字实体清洗结果（含《二期工程建构筑物一览表》表体文字）', '约 60 KB'],
  ['polys.json / rects.json / roads.json', '多段线、矩形轮廓、道路双线中间数据', '数十 KB'],
  ['quads.json', '道路路面四边形（渲染 `roads` 的来源）', '约 40 KB'],
  ['zoom_towers.png / view_A.png 等', '冷却塔、主厂房局部光栅化核对图', '每张数百 KB'],
];
let procTable = '| 文件/目录 | 用途 | 大小量级 |\n|---|---|---:|\n';
for (const [f, p, s] of PROC) procTable += `| \`${f}\` | ${p} | ${s} |\n`;

// ---------- 5. 替换占位符 ----------
const MAP = {
  '{{N_STRUCT}}': String(S.length),
  '{{N_ROADS}}': String(ROADS.length),
  '{{N_BOUNDARY}}': String(BOUND.length),
  '{{N_TREES}}': String(TREES.length),
  '{{N_EST}}': String(stats.est),
  '{{N_EXACT}}': String(S.length - stats.est),
  '{{STRUCT_TABLES}}': structTables,
  '{{CAT_TABLE}}': catTable,
  '{{EST_TABLE}}': estTable,
  '{{APPENDIX_SRC}}': appendix,
  '{{FILE_TABLE}}': buildFileTable(null),
  '{{PROC_TABLE}}': procTable,
};
for (const k of Object.keys(MAP)) MAP[k] = MAP[k].trimEnd();
const renderText = (tplPath) => {
  let t = fs.readFileSync(tplPath, 'utf8');
  for (const [k, v] of Object.entries(MAP)) t = t.split(k).join(v);
  const left = t.match(/\{\{[A-Z_]+\}\}/g);
  if (left) throw new Error(`${tplPath} 仍有未替换占位符: ${[...new Set(left)].join(', ')}`);
  return t.replace(/\n{3,}/g, '\n\n'); // 规范空行：段落间最多一个空行
};
const writeOut = (outPath, t) => {
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, t, 'utf8');
  console.log(`写出 ${outPath}（${(Buffer.byteLength(t) / 1024).toFixed(1)} KB，${t.split('\n').length} 行）`);
};

// readme.md 自身大小需回填到文件表：渲染→取长度→重建表→再渲染，直至 KB 标签稳定
const readmeTpl = path.join(HERE, 'doc-readme.tpl.md');
let readmeText = '';
let sizeLabel = null;
for (let i = 0; i < 4; i++) {
  MAP['{{FILE_TABLE}}'] = buildFileTable(sizeLabel);
  readmeText = renderText(readmeTpl);
  const next = kbLabel(Buffer.byteLength(readmeText, 'utf8'));
  if (next === sizeLabel) break;
  sizeLabel = next;
}
writeOut(OUT_README, readmeText);
writeOut(OUT_ASSET, renderText(path.join(HERE, 'doc-asset.tpl.md')));

// ---------- 6. 校验 ----------
console.log('--- 校验 ---');
console.log('构件', S.length, '| 估算', stats.est, '| 道路', ROADS.length, '| 边界点', BOUND.length, '| 树', TREES.length);
console.log('占地合计', fmt(stats.areaAll), '| h>0.5', stats.tall, '| 场坪', stats.flat);
console.log('类别:', CAT_ORDER.map((c) => `${c}=${stats.cats[c].n}/${fmt(stats.cats[c].area)}`).join('  '));
console.log('永久设施占地(不含施工临建):', fmt(stats.areaAll - stats.cats.construction.area));
const roadLen = ROADS.reduce((a, q) => a + Math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1]), 0);
console.log('道路长边合计', fmt(Math.round(roadLen)), 'm');
// 占地合计随补录构件变化，readme 由本脚本生成，无需与固定值比对
// 估算项数量随数据变化
