# tools — 图纸解析与数据生成工具链

本目录是可复现的"图纸 → 数据 → 三维"工具链。所有构件坐标都由这些脚本从 DWG 直接量取，
不存在手工改写的中间坐标。**运行时不需要它们**（网页只依赖根目录的 `plant-data.js`）。

## 目录与仓库结构

```
power-plant-3d/
├── index.html                  入口页（双击即可打开；也可 iframe 嵌入运维后台）
├── main.js                     场景/相机/渲染器/拾取/交互/扩展钩子
├── builders.js                 15 类构件几何构建器（白模 + PBR 材质）
├── plant-data.js               唯一数据源：129 构件 / 140 段道路 / 192 树点 / 18 点厂界
├── style.css                   样式：悬浮信息面板、左侧构件清单、工具栏
├── readme.md                   构件参数清单、尺寸说明、图纸来源、修改说明
├── preview.png                 默认视角渲染截图
├── vendor/                     three r128 UMD + OrbitControls（离线可用，无外链）
├── docs/archive/               归档说明（资产编号 PP-3D-2026-001）
├── source/                     源图纸 DWG（唯一布局基准）
└── tools/                      本目录：解析与生成脚本
```

## 依赖

- Node.js ≥ 18（解析 DWG 用）
- Python 3.10+，需 `Pillow`（光栅化看图）与 `numpy`
- 解析库：`@mlightcad/libredwg-web@0.8.2`（LibreDWG WASM）

```bash
cd tools
npm i @mlightcad/libredwg-web@0.8.2   # 或 pnpm add
```

WASM 目录位于 `node_modules/@mlightcad/libredwg-web/wasm/`，`dump.mjs` 用
`new URL(import.meta.url)` 定位，**不要改成 process.cwd()**（会 ENOENT）。

## 流水线（按顺序）

| 步骤 | 脚本 | 作用 |
|---|---|---|
| 1 | `node dump.mjs` | DWG → `out/entities.json`（11,822 个实体）。stderr 的 `error code: 64` 可忽略，实体完整 |
| 2 | `node raw.mjs <类型>` | 打印指定类型的原始字段（排查字段名，如 TEXT 的高度字段实为 `textHeight`） |
| 3 | `python labels.py` | 剥离 KaTi 格式码 → `labels.json`（612 条标注） |
| 4 | `python raster.py all` / `python crop.py main` | 自写 PIL 光栅化器出图，目视核对（支持 bulge 圆弧） |
| 5 | `python an17.py` | 提取 layer=15 的二期编号 101–142 平面锚点 |
| 6 | `python an10.py` / `an12.py` | 轴对齐矩形 / 任意旋转四边形轮廓检测 |
| 7 | `python an18.py` / `an19.py` | 道路平行双线配对 → `roads.json`（140 段路面四边形） |
| 8 | `python audit_geo.py` | 六类方法（闭合多段线/四边形/矩形/圆/线段环/三边补全）全量候选审计 → `audit_missing.json` + 报告 |
| 9 | `python mkextra.py` | 审计候选 + 手工补录 → `extra.json`（58 项补录，含过滤与去重规则） |
| 10 | `python mkdata.py` | 汇总 → `plant-data.js`（网页唯一数据源） |
| 11 | `node dumpdata.cjs` | 用 vm 沙箱加载 `plant-data.js` 校验语法并导出 `plant-data.json` |
| 12 | `python verify.py` | 把全部构件框叠回 DWG 线稿 → 跑位核对图 |
| 13 | `node build-docs.mjs` | 从 `plant-data.js` 重新生成 `readme.md` 与归档说明的参数表 |

改完 `plant-data.js` 后务必重跑第 11、13 步；第 13 步不会覆盖 readme 里 4 处静态数字
（文档头构件数、占地合计行、性能说明、归档占地行），需手工同步。

## 标定结论（重要）

**1 图纸单位 = 1 米。** 冷却塔在图纸中由"2 顶点、bulge=1 的多段线半圆"绘制而非 CIRCLE，
反算外圈半径 51 m；对照图纸自带《二期工程建构筑物一览表》"循环水冷却塔 16400 m²"：
2 × π × 51² = 16,342 ≈ 16,400（误差 0.35%）。全图据此按米解释。

## 坐标映射

图纸为测量坐标（东 E / 北 N），三维世界坐标 `world = (E − 2900800, N − 2548300)`，
Z 轴为高度。`plant-data.js` 里的 `x/y` 已换算为该世界坐标。

## 免责

`source/` 下图纸仅用于本工程内部复核，未经授权请勿外传；仓库默认私有即出于此考虑。
