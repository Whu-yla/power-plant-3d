// =============================================================================
// builders.js —— 电厂总平面「纯几何构建器」集合（经典脚本，非 ES Module）
// -----------------------------------------------------------------------------
// 设计约定（务必与 main.js 保持一致）：
//   1) 坐标系：图纸 (E, N) 减去 PLANT_DATA.meta.origin 得到世界 (x, y)，Z 轴向上：
//      worldX = E - origin.e，worldY = N - origin.n，worldZ = 高度（单位 m）。
//   2) 所有体量沿 +Z 拉伸/堆叠。Three.js 内核里 Y-up 的几何（Cylinder / Lathe /
//      Cone / Sphere / Torus）统一在辅助函数里 rotateX(+90°) 转成 Z-up
//      （cylZ / latheZ / coneZ），因此构建器内部一律按「z 为高度」书写。
//   3) 每个构筑物返回一个 THREE.Group，组原点位于其平面中心、地面 z=0 处；
//      group.userData = { structId, data, dim, materials }，
//      main.js 靠 structId 做射线拾取 → 高亮 / 告警变色 / 显隐 / 信息面板。
//   4) shape → 构建器映射（SHAPE_BUILDERS 表）：
//        box         → buildBox         普通矩形厂房（汽机房、锅炉房、配电间…）
//        gantry      → buildGantry      露天钢支架（送风机/引风机支架）
//        switchyard  → buildSwitchyard  500kV 户外配电装置（构架 + 设备基础）
//        transformer → buildTransformer 主变/厂用变（箱体 + 散热器 + 套管）
//        hyperbolic  → buildCoolingTower 双曲线冷却塔（LatheGeometry 旋转面）
//        chimney     → buildChimney     烟囱（红白每 30m 交替分段圆柱拼接）
//        tank        → buildTank        灰库/粉仓（锥斗 + 筒体 + 锥顶 + 支柱）
//        dome        → buildDome        圆形封闭煤仓（筒壁 + 穹顶）
//        coalheap    → buildCoalheap    条形煤堆（梯形断面沿长度挤出）
//        gallery     → buildGallery     栈桥/天桥（架空廊道 + 支架）
//        duct        → buildDuct        烟道（架空矩形断面 + 支架）
//        pipes       → buildPipes       循环水管（架空圆管 + 支墩）
//        pit         → buildPit         地下水池/油池/卸煤槽（坑壁 + 坑底）
//        pad         → buildPad         场地平整（薄板，按类别着色）
//        retaining   → buildRetaining   挡墙/挡煤墙（长条墙 + 压顶）
//   5) 每个构建器返回该构筑物的顶点高度 topZ（用于放置编号 sprite）。
// =============================================================================
window.PlantBuilders = (function () {
  'use strict';

  // ---------- 全局状态：图纸原点（由 main.js 在构建前注入） ----------
  var ORIGIN = { e: 2900800, n: 2548300 };

  // ---------- 材质调色板（PBR，白模偏工程展示色系） ----------
  var PALETTE = {
    concrete:     { color: 0xd8dbd6, roughness: 0.92, metalness: 0.02 },
    concreteMid:  { color: 0xc3c7c2, roughness: 0.90, metalness: 0.03 },
    concreteDark: { color: 0x9ba29c, roughness: 0.90, metalness: 0.03 },
    steel:        { color: 0x8b929a, roughness: 0.45, metalness: 0.62 },
    steelDark:    { color: 0x5d646b, roughness: 0.42, metalness: 0.66 },
    glass:        { color: 0x5a7280, roughness: 0.25, metalness: 0.35 },
    asphalt:      { color: 0x474c52, roughness: 0.96, metalness: 0.02 },
    gravel:       { color: 0xb8b2a2, roughness: 0.98, metalness: 0.00 },
    grass:        { color: 0x7d9a68, roughness: 1.00, metalness: 0.00 },
    dirt:         { color: 0xbfb193, roughness: 1.00, metalness: 0.00 },
    yard:         { color: 0xbdbcb2, roughness: 0.97, metalness: 0.00 },
    red:          { color: 0xbb3a30, roughness: 0.72, metalness: 0.04 },
    white:        { color: 0xe7e4dd, roughness: 0.82, metalness: 0.02 },
    water:        { color: 0x4d7488, roughness: 0.22, metalness: 0.25 },
    coal:         { color: 0x35383b, roughness: 0.95, metalness: 0.05 },
    wallOuter:    { color: 0xb2b6ae, roughness: 0.95, metalness: 0.02 },
    wallInner:    { color: 0xdadcd4, roughness: 0.95, metalness: 0.02 },
    coping:       { color: 0x8e948f, roughness: 0.90, metalness: 0.03 },
    shell:        { color: 0xd5d8d2, roughness: 0.88, metalness: 0.03, side: THREE.DoubleSide },
    shellDark:    { color: 0xb9beb8, roughness: 0.90, metalness: 0.03, side: THREE.DoubleSide },
    treeTrunk:    { color: 0x6b5a45, roughness: 0.95, metalness: 0.00 },
    treeCrown:    { color: 0x5f8a4e, roughness: 0.95, metalness: 0.00 }
  };

  // 各类别（cat）在左侧清单中的标识色
  var CATEGORY_COLORS = {
    main: '#c8813f', electrical: '#5f8fc4', cooling: '#49a29a',
    coal: '#7f858c', aux: '#8f83bb', living: '#c0779a', construction: '#a89a63',
    existing: '#9a9c93'
  };
  // 场地平整（pad）按类别取地面色
  var PAD_MAT = {
    construction: 'dirt', living: 'yard', coal: 'gravel',
    main: 'concreteMid', electrical: 'gravel', cooling: 'yard', aux: 'yard',
    existing: 'concreteMid'
  };

  // ====================== 基础工具 ======================
  function num(v, dflt) {
    return (typeof v === 'number' && isFinite(v) && v > 0) ? v : dflt;
  }
  function toW(p) { return { x: p[0] - ORIGIN.e, y: p[1] - ORIGIN.n }; }
  function prng(i) { // 确定性伪随机（树/细节变化用，保证每次打开一致）
    var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
    return x - Math.floor(x);
  }
  function lerp(a, b, t) { return a + (b - a) * t; }

  // 单一构筑物内共享材质（key 相同则复用），同时收集到 userData.materials 供高亮
  function matKit() {
    var cache = {}, list = [];
    return {
      get: function (key, opts) {
        var ck = key;
        if (opts) {
          if (opts.color !== undefined) ck += '|c' + opts.color;
          if (opts.side !== undefined) ck += '|s' + opts.side;
        }
        if (cache[ck]) return cache[ck];
        var spec = PALETTE[key] || PALETTE.concrete;
        var p = {}, k;
        for (k in spec) { if (Object.prototype.hasOwnProperty.call(spec, k)) p[k] = spec[k]; }
        if (opts) { for (k in opts) { if (Object.prototype.hasOwnProperty.call(opts, k)) p[k] = opts[k]; } }
        var m = new THREE.MeshStandardMaterial(p);
        m.userData.matKey = ck;
        cache[ck] = m;
        list.push(m);
        return m;
      },
      list: list
    };
  }

  function meshOf(kit, geom, key, opts) {
    var m = new THREE.Mesh(geom, kit.get(key, opts));
    m.castShadow = true;
    m.receiveShadow = true;
    return m;
  }

  // 合并同材质几何（避免每根梁都成为一个 draw call）。
  // 只保留 position / normal，够用且省显存。
  function mergeGeoms(geoms) {
    var src = [], total = 0, i;
    for (i = 0; i < geoms.length; i++) {
      var g = geoms[i].index ? geoms[i].toNonIndexed() : geoms[i];
      src.push(g);
      total += g.attributes.position.count;
    }
    var pos = new Float32Array(total * 3);
    var nor = new Float32Array(total * 3);
    var off = 0;
    for (i = 0; i < src.length; i++) {
      var a = src[i].attributes.position.array;
      pos.set(a, off);
      if (src[i].attributes.normal) nor.set(src[i].attributes.normal.array, off);
      off += a.length;
    }
    var out = new THREE.BufferGeometry();
    out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
    out.computeBoundingSphere();
    out.computeBoundingBox();
    return out;
  }

  // ---- 几何原语（全部 Z-up） ----
  // 矩形棱柱：平面 w×d，底面 z=0，顶面 z=h
  function rectPrism(w, d, h) {
    var sh = new THREE.Shape();
    sh.moveTo(-w / 2, -d / 2);
    sh.lineTo(w / 2, -d / 2);
    sh.lineTo(w / 2, d / 2);
    sh.lineTo(-w / 2, d / 2);
    sh.closePath();
    return new THREE.ExtrudeGeometry(sh, {
      depth: h, bevelEnabled: false, steps: 1, curveSegments: 8
    });
  }
  // 圆柱：轴沿 +Z，中心在 z=0，高度 h
  function cylZ(rTop, rBottom, h, seg, openEnded) {
    var g = new THREE.CylinderGeometry(rTop, rBottom, h, seg || 32, 1, !!openEnded);
    g.rotateX(Math.PI / 2);           // Y-up → Z-up
    return g;
  }
  // 圆锥：轴沿 +Z，底面 z=-h/2，锥尖 z=+h/2
  function coneZ(r, h, seg) {
    var g = new THREE.ConeGeometry(r, h, seg || 24);
    g.rotateX(Math.PI / 2);
    return g;
  }
  // 旋转面：pts = [{r, z}]，绕 Z 轴旋转（双曲线冷却塔 / 穹顶 / 灰库都靠它）
  function latheZ(pts, seg) {
    var v2 = [], i;
    for (i = 0; i < pts.length; i++) {
      v2.push(new THREE.Vector2(Math.max(pts[i].r, 0.001), pts[i].z));
    }
    var g = new THREE.LatheGeometry(v2, seg || 48);
    g.rotateX(Math.PI / 2);           // 母线 y（高度）→ z
    return g;
  }
  // 水平圆环（环梁）
  function torusZ(r, tube, seg) {
    return new THREE.TorusGeometry(r, tube, 8, seg || 48);
  }
  // 把 box 变换后塞进合并列表：rotZ 为绕 Z 旋转角（弧度）
  function pushBox(arr, w, d, h, x, y, z, rotZ) {
    var g = new THREE.BoxGeometry(w, d, h);
    if (rotZ) g.rotateZ(rotZ);
    g.translate(x, y, z);
    arr.push(g);
    return g;
  }
  // 两点之间的圆管（斜撑、支腿用）
  function pushTube(arr, ax, ay, az, bx, by, bz, r, seg) {
    var dx = bx - ax, dy = by - ay, dz = bz - az;
    var len = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (len < 0.05) return;
    var g = new THREE.CylinderGeometry(r, r, len, seg || 6, 1, true);
    var dir = new THREE.Vector3(dx / len, dy / len, dz / len);
    var q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    g.applyMatrix4(new THREE.Matrix4().makeRotationFromQuaternion(q));
    g.translate((ax + bx) / 2, (ay + by) / 2, (az + bz) / 2);
    arr.push(g);
  }

  // ---- 尺寸兜底：数据里 w/d/h 缺失时给出合理默认并 console.warn ----
  var CIRCULAR = { hyperbolic: 1, chimney: 1, tank: 1, dome: 1 };
  function resolveDims(s) {
    var w = num(s.w, 0), d = num(s.d, 0), h = num(s.h, 0), area = num(s.area, 0);
    if (CIRCULAR[s.shape]) {
      if (!d && w) { d = w; w = 0; }
      if (!d && area) { d = Math.sqrt(area * 4 / Math.PI); }
      if (!d) { d = 10; console.warn('[builders] ' + s.id + ' 缺少直径 d，取默认 10m'); }
      w = d;
    } else {
      if (!w && d) { w = d; }
      if (!d && w) { d = w; }
      if (!w && area) { w = Math.sqrt(area); }
      if (!w) { w = 12; console.warn('[builders] ' + s.id + ' 缺少 w，按默认 12m 处理'); }
      if (!d) { d = Math.max(4, area / w || 12); console.warn('[builders] ' + s.id + ' 缺少 d，按面积估算 d=' + d.toFixed(1) + 'm'); }
    }
    if (!h) { h = 6; console.warn('[builders] ' + s.id + ' 缺少高度 h，取默认 6m'); }
    return { w: w, d: d, h: h };
  }

  // ====================== 各 shape 构建器 ======================
  // 每个签名：function (kit, s, dim, group) → 返回顶点高度（米）

  // 【box】矩形厂房：主体 + 檐口 + 立面窗带（+ 大跨厂房屋脊通风器）
  function buildBox(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;

    var body = meshOf(kit, rectPrism(w, d, h), 'concrete');
    group.add(body);

    // 屋顶檐口 / 女儿墙
    var cap = meshOf(kit, rectPrism(w + 1.4, d + 1.4, 0.9), 'concreteMid');
    cap.position.z = h;
    group.add(cap);

    // 立面窗带：只在层高足够时出现，增强尺度感
    if (h >= 12) {
      var bands = [0.30, 0.55, 0.78];
      var bh = Math.min(2.4, Math.max(1.2, h * 0.05));
      for (var i = 0; i < bands.length; i++) {
        var band = meshOf(kit, rectPrism(w + 0.6, d + 0.6, bh), 'glass');
        band.position.z = h * bands[i];
        band.castShadow = false;
        group.add(band);
      }
    }

    // 大跨厂房（汽机房/锅炉房）加屋脊通风器
    if (h >= 30 && w >= 100) {
      var vent = meshOf(kit, rectPrism(w * 0.9, Math.max(3, d * 0.12), 4.2), 'steelDark');
      vent.position.z = h + 0.9;
      group.add(vent);
      return h + 5.1;
    }
    return h + 0.9;
  }

  // 【gantry】露天钢支架：四角柱 + 分层横梁 + 顶部平台 + 粗壮设备
  function buildGantry(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var geos = [];
    var col = Math.max(0.9, Math.min(w, d) * 0.05);
    var cx = w / 2 - col / 2, cy = d / 2 - col / 2;

    pushBox(geos, col, col, h, -cx, -cy, h / 2);
    pushBox(geos, col, col, h, cx, -cy, h / 2);
    pushBox(geos, col, col, h, cx, cy, h / 2);
    pushBox(geos, col, col, h, -cx, cy, h / 2);

    var levels = [0.35, 0.58, 0.80, 1.00];
    for (var i = 0; i < levels.length; i++) {
      var z = h * levels[i];
      pushBox(geos, w, 0.7, 0.7, 0, -cy, z);
      pushBox(geos, w, 0.7, 0.7, 0, cy, z);
      pushBox(geos, 0.7, d, 0.7, -cx, 0, z);
      pushBox(geos, 0.7, d, 0.7, cx, 0, z);
    }
    // 顶部平台
    pushBox(geos, w, d, 0.8, 0, 0, h);
    // 侧面 X 形斜撑（前后两面）
    pushTube(geos, -cx, -cy, 0.4, cx, -cy, h * 0.58, 0.35);
    pushTube(geos, cx, -cy, 0.4, -cx, -cy, h * 0.58, 0.35);
    pushTube(geos, -cx, cy, 0.4, cx, cy, h * 0.58, 0.35);
    pushTube(geos, cx, cy, 0.4, -cx, cy, h * 0.58, 0.35);

    var frame = meshOf(kit, mergeGeoms(geos), 'steelDark');
    group.add(frame);

    // 支架上的风机/设备体量
    var unit = meshOf(kit, cylZ(w * 0.20, w * 0.20, 4.5, 20), 'steel');
    unit.position.z = h + 3.0;
    group.add(unit);

    return h + 5.5;
  }

  // 【switchyard】500kV 户外配电装置：碎石场地 + 构架排 + 设备基础 + 软母线
  function buildSwitchyard(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;

    var pad = meshOf(kit, rectPrism(w, d, 0.22), 'gravel');
    group.add(pad);

    var geos = [];
    var rows = Math.max(2, Math.round(w / 32));
    var bay = w / rows;
    var armD = d * 0.78;
    var colW = 0.9;

    for (var i = 0; i < rows; i++) {
      var x = -w / 2 + bay * (i + 0.5);
      pushBox(geos, colW, colW, h, x, -armD / 2, h / 2);
      pushBox(geos, colW, colW, h, x, armD / 2, h / 2);
      pushBox(geos, colW * 0.85, armD, colW * 0.85, x, 0, h);           // 顶部横梁
      pushBox(geos, colW * 0.85, armD, colW * 0.85, x, 0, h * 0.80);    // 二层横梁
      // 设备基础（断路器/隔离开关基座）
      pushBox(geos, 7, 5, 4.5, x, 0, 2.6);
      pushBox(geos, 2.4, 2.4, 8.5, x, 0, 4.4);
    }
    // 纵向连梁 + 软母线（沿 w 方向）
    pushBox(geos, w, 0.6, 0.6, 0, -armD / 2, h * 0.92);
    pushBox(geos, w, 0.6, 0.6, 0, armD / 2, h * 0.92);
    pushTube(geos, -w / 2, -armD * 0.3, h * 0.70, w / 2, -armD * 0.3, h * 0.70, 0.28, 6);
    pushTube(geos, -w / 2, armD * 0.3, h * 0.70, w / 2, armD * 0.3, h * 0.70, 0.28, 6);
    pushTube(geos, -w / 2, 0, h * 0.62, w / 2, 0, h * 0.62, 0.28, 6);

    var frames = meshOf(kit, mergeGeoms(geos), 'steelDark');
    group.add(frames);

    return h + 2;
  }

  // 【transformer】主变/厂用变：基础 + 箱体 + 散热器 + 高压套管 + 储油柜
  function buildTransformer(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var geos = [];

    // 混凝土基础
    var base = meshOf(kit, rectPrism(w + 2.4, d + 2.4, 0.6), 'concreteMid');
    group.add(base);

    // 油箱主体
    var tankW = w * 0.70, tankD = d * 0.76, tankH = h * 0.58;
    var tank = meshOf(kit, rectPrism(tankW, tankD, tankH), 'steel');
    tank.position.z = 0.6;
    group.add(tank);

    // 散热器（两侧成组薄片）
    var radGeos = [];
    var rads = 5;
    for (var i = 0; i < rads; i++) {
      var y = -tankD / 2 + tankD * (i + 0.5) / rads;
      pushBox(radGeos, tankW * 0.16, tankD * 0.13, tankH * 0.72,
        -(tankW / 2 + tankW * 0.09), y, 0.6 + tankH * 0.42);
      pushBox(radGeos, tankW * 0.16, tankD * 0.13, tankH * 0.72,
        (tankW / 2 + tankW * 0.09), y, 0.6 + tankH * 0.42);
    }
    var rad = meshOf(kit, mergeGeoms(radGeos), 'steelDark');
    group.add(rad);

    // 高压套管（顶部三支）
    var busGeos = [];
    for (var b = 0; b < 3; b++) {
      var by = tankD * (b - 1) * 0.28;
      pushTube(busGeos, -tankW * 0.22, by, 0.6 + tankH,
        -tankW * 0.22, by, 0.6 + tankH + h * 0.26, 0.32, 8);
      pushBox(busGeos, 1.1, 1.1, 0.7, -tankW * 0.22, by, 0.6 + tankH + h * 0.26 + 0.3);
    }
    var bushings = meshOf(kit, mergeGeoms(busGeos), 'white');
    group.add(bushings);

    // 储油柜（顶部横置圆筒）
    var cons = meshOf(kit, cylZ(d * 0.16, d * 0.16, w * 0.5, 14), 'steelDark');
    cons.rotation.z = Math.PI / 2;      // 轴转为 X 方向
    cons.position.set(0, 0, 0.6 + tankH + h * 0.10);
    group.add(cons);

    return h;
  }

  // 【hyperbolic】双曲线冷却塔：LatheGeometry 真实双曲线母线 + 顶部环梁 + 进风口支腿
  function buildCoolingTower(kit, s, dim, group) {
    var r = dim.d / 2, H = dim.h;
    var rThroat = r * 0.50;             // 喉部半径 ≈ 0.5R（即 0.5·d/2）
    var zThroat = H * 0.80;             // 喉部高度 ≈ 0.8H
    var lowH = Math.min(10, H * 0.08);  // 进风口高度（底部敞开段）

    // 双曲线方程 r²/a² - (z-z0)²/b² = 1，a=rThroat，z0=zThroat，由 r(0)=r 反算 b
    var bDenom = Math.sqrt(Math.pow(r / rThroat, 2) - 1);
    var b = zThroat / bDenom;

    var profile = [], i, segs = 26;
    for (i = 0; i <= segs; i++) {
      var z = lowH + (H - lowH) * i / segs;
      var rr = rThroat * Math.sqrt(1 + Math.pow((z - zThroat) / b, 2));
      profile.push({ r: rr, z: z });
    }

    var shell = meshOf(kit, latheZ(profile, 64), 'shell');
    group.add(shell);

    // 顶部环梁（加强环）
    var topR = profile[profile.length - 1].r;
    var ring = meshOf(kit, torusZ(topR * 1.005, 1.15, 64), 'concreteMid');
    ring.position.z = H - 1.0;
    group.add(ring);

    // 塔筒下部环基
    var baseRing = meshOf(kit, cylZ(r * 1.05, r * 1.07, 1.6, 64), 'concreteMid');
    baseRing.position.z = 0.8;
    group.add(baseRing);

    // 进风口斜支腿（48 根，合并为一个 mesh）
    var legs = [], n = 48;
    for (i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2;
      var a2 = a + 0.06;
      pushTube(legs,
        Math.cos(a) * r * 0.995, Math.sin(a) * r * 0.995, 0.4,
        Math.cos(a2) * r * 0.945, Math.sin(a2) * r * 0.945, lowH + 2.5,
        0.62, 6);
    }
    var legMesh = meshOf(kit, mergeGeoms(legs), 'concreteDark');
    group.add(legMesh);

    return H;
  }

  // 【chimney】烟囱：每 30m 一段红白交替圆柱拼接（真实分段）+ 基础 + 顶部檐口
  function buildChimney(kit, s, dim, group) {
    var rBase = dim.d / 2, H = dim.h;
    var rTop = rBase * 0.55;
    var segCount = Math.max(2, Math.ceil(H / 30));
    var segH = H / segCount;

    // 基础承台
    var plinth = meshOf(kit, cylZ(rBase * 1.32, rBase * 1.55, 6, 40), 'concreteDark');
    plinth.position.z = 3;
    group.add(plinth);

    for (var i = 0; i < segCount; i++) {
      var z0 = i * segH, z1 = (i + 1) * segH;
      var r0 = lerp(rBase, rTop, z0 / H);
      var r1 = lerp(rBase, rTop, z1 / H);
      var segGeo = cylZ(r1 * 0.994, r0, z1 - z0, 40, true);
      var key = (i % 2 === 0) ? 'white' : 'red';
      var m = meshOf(kit, segGeo, key);
      m.position.z = (z0 + z1) / 2;
      group.add(m);
    }

    // 顶部檐口 + 内衬口
    var rim = meshOf(kit, cylZ(rTop * 1.07, rTop * 1.02, 2.6, 40), 'concreteMid');
    rim.position.z = H + 1.0;
    group.add(rim);

    var mouth = meshOf(kit, cylZ(rTop * 0.86, rTop * 0.86, 0.5, 32), 'coal');
    mouth.position.z = H + 1.0;
    group.add(mouth);

    return H + 2.4;
  }

  // 【tank】灰库/粉仓：支柱 + 锥斗 + 筒体 + 锥顶（整体用旋转面）
  function buildTank(kit, s, dim, group) {
    var r = dim.d / 2, H = dim.h;
    var legH = Math.min(9, H * 0.32);
    var roofH = Math.min(8, H * 0.20);
    var bodyTop = H - roofH;

    // 6 根支柱
    var legs = [], n = 6;
    for (var i = 0; i < n; i++) {
      var a = i / n * Math.PI * 2;
      pushBox(legs, 1.5, 1.5, legH, Math.cos(a) * r * 0.92, Math.sin(a) * r * 0.92, legH / 2);
    }
    var legMesh = meshOf(kit, mergeGeoms(legs), 'concreteMid');
    group.add(legMesh);

    // 锥斗 + 筒体 + 锥顶（一条母线，旋转成型）
    var profile = [
      { r: 0.9, z: legH * 0.35 },
      { r: r * 0.34, z: legH * 0.62 },
      { r: r, z: legH },
      { r: r, z: bodyTop },
      { r: r * 0.62, z: H - roofH * 0.45 },
      { r: 0.55, z: H }
    ];
    var shell = meshOf(kit, latheZ(profile, 40), 'shell');
    group.add(shell);

    // 筒顶环梁
    var ring = meshOf(kit, torusZ(r * 1.02, 0.55, 40), 'concreteDark');
    ring.position.z = bodyTop;
    group.add(ring);

    return H;
  }

  // 【dome】圆形封闭煤仓：环基 + 筒壁 + 穹顶（1/4 椭圆旋转面）
  function buildDome(kit, s, dim, group) {
    var r = dim.d / 2, H = dim.h;
    var wallH = H * 0.58, domeH = H - wallH;

    var base = meshOf(kit, cylZ(r * 1.04, r * 1.06, 1.4, 56), 'concreteMid');
    base.position.z = 0.7;
    group.add(base);

    var wall = meshOf(kit, cylZ(r, r, wallH, 56, true), 'shell');
    wall.position.z = wallH / 2;
    group.add(wall);

    // 穹顶：母线从 (r, wallH) 椭圆过渡到 (0.55, H)
    var pts = [], i, segs = 16;
    for (i = 0; i <= segs; i++) {
      var t = i / segs * Math.PI / 2;
      pts.push({ r: Math.max(0.55, r * Math.cos(t)), z: wallH + domeH * Math.sin(t) });
    }
    var dome = meshOf(kit, latheZ(pts, 56), 'shellDark');
    group.add(dome);

    // 筒壁顶部环梁 + 采光带
    var ring = meshOf(kit, torusZ(r * 1.01, 0.8, 56), 'concreteMid');
    ring.position.z = wallH;
    group.add(ring);

    var band = meshOf(kit, cylZ(r * 1.005, r * 1.005, 1.6, 56, true), 'glass');
    band.position.z = Math.min(wallH * 0.72, wallH - 1.2);
    group.add(band);

    return H;
  }

  // 【coalheap】条形煤堆：梯形断面沿长度方向挤出
  function buildCoalheap(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var tw = w * 0.28;  // 顶宽

    // 场地垫层
    var pad = meshOf(kit, rectPrism(w * 1.06, d, 0.3), 'gravel');
    group.add(pad);

    var sh = new THREE.Shape();
    sh.moveTo(-w / 2, 0);
    sh.lineTo(w / 2, 0);
    sh.lineTo(tw / 2, h);
    sh.lineTo(-tw / 2, h);
    sh.closePath();
    var geo = new THREE.ExtrudeGeometry(sh, { depth: d, bevelEnabled: false, steps: 1 });
    geo.rotateX(Math.PI / 2);      // 断面 y → z，挤出方向 z → -y
    geo.translate(0, d / 2, 0);    // 沿长度居中
    var heap = meshOf(kit, geo, 'coal');
    heap.position.z = 0.3;
    group.add(heap);

    return h + 0.3;
  }

  // 【gallery】栈桥/天桥：架空封闭廊道 + 支架 + 栏板
  function buildGallery(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var deckH = Math.min(3.8, Math.max(2.4, h * 0.36));
    var deckZ = h - deckH;

    var body = meshOf(kit, rectPrism(w, d, deckH), 'concrete');
    body.position.z = deckZ;
    group.add(body);

    var band = meshOf(kit, rectPrism(w + 0.12, d + 0.12, 1.1), 'glass');
    band.position.z = deckZ + deckH * 0.42;
    band.castShadow = false;
    group.add(band);

    // 支架：两端 + 中间各两榀
    var geos = [];
    var xs = [-w / 2 + 2, 0, w / 2 - 2];
    for (var i = 0; i < xs.length; i++) {
      pushBox(geos, 1.6, 1.6, deckZ, xs[i], -d / 2 + 1.2, deckZ / 2);
      pushBox(geos, 1.6, 1.6, deckZ, xs[i], d / 2 - 1.2, deckZ / 2);
      pushBox(geos, 2.0, d, 0.8, xs[i], 0, deckZ - 0.4);
    }
    var braces = meshOf(kit, mergeGeoms(geos), 'steelDark');
    group.add(braces);

    return h;
  }

  // 【duct】烟道：架空矩形断面 + 支墩
  function buildDuct(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var ductH = Math.min(h * 0.55, 9);
    var bottom = h - ductH;

    var body = meshOf(kit, rectPrism(w, d, ductH), 'steelDark');
    body.position.z = bottom;
    group.add(body);

    var geos = [];
    var xs = [-w / 2 + 4, 0, w / 2 - 4];
    for (var i = 0; i < xs.length; i++) {
      pushBox(geos, 2.4, d * 0.75, bottom, xs[i], 0, bottom / 2);
    }
    var legs = meshOf(kit, mergeGeoms(geos), 'concreteMid');
    group.add(legs);

    return h;
  }

  // 【pipes】循环水管：三根平行架空钢管 + 混凝土支墩
  function buildPipes(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var n = 3, r = Math.max(0.9, d * 0.11);
    var z0 = Math.max(1.6, h * 0.8);

    var tubeGeo = [], i;
    for (i = 0; i < n; i++) {
      var y = -d / 2 + d * (i + 0.5) / n;
      var g = cylZ(r, r, w, 14);
      g.rotateY(Math.PI / 2);     // 轴 Z → X
      g.translate(0, y, z0);
      tubeGeo.push(g);
    }
    var pipes = meshOf(kit, mergeGeoms(tubeGeo), 'steelDark');
    group.add(pipes);

    // 支墩（每 20m 一处）
    var geos = [];
    var step = 20;
    for (var x = -w / 2 + 2; x <= w / 2 - 2; x += step) {
      pushBox(geos, 3.0, d * 0.9, z0, x, 0, z0 / 2);
    }
    var supports = meshOf(kit, mergeGeoms(geos), 'concreteMid');
    group.add(supports);

    return h;
  }

  // 【pit】地下水池/油池：坑壁 + 坑底（水面/油面）
  function buildPit(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var rimH = Math.max(1.0, Math.min(h, 2.6));
    var t = Math.max(0.8, Math.min(w, d) * 0.05);

    var geos = [];
    pushBox(geos, w, t, rimH, 0, -d / 2 + t / 2, rimH / 2);
    pushBox(geos, w, t, rimH, 0, d / 2 - t / 2, rimH / 2);
    pushBox(geos, t, d - 2 * t, rimH, -w / 2 + t / 2, 0, rimH / 2);
    pushBox(geos, t, d - 2 * t, rimH, w / 2 - t / 2, 0, rimH / 2);
    var rim = meshOf(kit, mergeGeoms(geos), 'concreteDark');
    group.add(rim);

    var floor = meshOf(kit, rectPrism(w - 2 * t, d - 2 * t, 0.25), 'water');
    floor.position.z = 0.05;
    floor.castShadow = false;
    group.add(floor);

    return rimH;
  }

  // 【pad】场地平整：薄板，按类别取色
  function buildPad(kit, s, dim, group) {
    var matKey = PAD_MAT[s.cat] || 'dirt';
    var slab = meshOf(kit, rectPrism(dim.w, dim.d, Math.max(0.2, dim.h)), matKey);
    slab.castShadow = false;
    group.add(slab);
    return Math.max(0.2, dim.h);
  }

  // 【retaining】挡墙/挡煤墙：长条墙 + 压顶
  function buildRetaining(kit, s, dim, group) {
    var w = dim.w, d = dim.d, h = dim.h;
    var wall = meshOf(kit, rectPrism(w, d, h), 'concreteMid');
    group.add(wall);
    var cope = meshOf(kit, rectPrism(w + 0.3, d + 0.3, 0.35), 'concreteDark');
    cope.position.z = h;
    group.add(cope);
    return h + 0.35;
  }

  var SHAPE_BUILDERS = {
    box: buildBox,
    gantry: buildGantry,
    switchyard: buildSwitchyard,
    transformer: buildTransformer,
    hyperbolic: buildCoolingTower,
    chimney: buildChimney,
    tank: buildTank,
    dome: buildDome,
    coalheap: buildCoalheap,
    gallery: buildGallery,
    duct: buildDuct,
    pipes: buildPipes,
    pit: buildPit,
    pad: buildPad,
    retaining: buildRetaining
  };

  // ====================== 单个构筑物装配 ======================
  // 返回 group：位置 = 世界坐标，rot 绕 Z；userData 携带拾取所需的全部信息
  function buildStructure(s) {
    var dim = resolveDims(s);
    var kit = matKit();
    var group = new THREE.Group();
    group.name = 'struct-' + s.id;

    var builder = SHAPE_BUILDERS[s.shape];
    var topZ = dim.h;
    if (!builder) {
      console.warn('[builders] ' + s.id + ' 未知 shape=' + s.shape + '，按 box 处理');
      builder = buildBox;
    }
    try {
      topZ = builder(kit, s, dim, group) || dim.h;
    } catch (err) {
      console.error('[builders] ' + s.id + ' 构建失败：', err);
    }

    group.position.set(s.x - ORIGIN.e, s.y - ORIGIN.n, 0);
    // rot：数据中全为 0；非 0 时若绝对值 > 6.5 视为“度”，否则视为“弧度”
    var rot = typeof s.rot === 'number' ? s.rot : 0;
    group.rotation.z = (Math.abs(rot) > 6.5) ? rot * Math.PI / 180 : rot;

    group.userData.structId = s.id;
    group.userData.data = s;
    group.userData.dim = dim;
    group.userData.materials = kit.list;
    group.userData.topZ = topZ;
    group.traverse(function (o) {
      if (o.isMesh) {
        o.userData.structId = s.id;
        o.castShadow = true;
        o.receiveShadow = true;
      }
    });
    return group;
  }

  // ====================== 场地构件 ======================

  // 厂区围墙：沿折线逐段生成「内浅外深」双层薄墙 + 压顶（内外区分色）
  function buildBoundary(poly) {
    var group = new THREE.Group();
    group.name = 'boundary-wall';
    var H = 2.5, T = 0.4;
    var outer = [], inner = [], coping = [], i;
    var world = poly.map(toW);

    for (i = 0; i < world.length - 1; i++) {
      var a = world[i], b = world[i + 1];
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.sqrt(dx * dx + dy * dy);
      if (len < 0.2) continue;
      var ux = dx / len, uy = dy / len;
      var nx = -uy, ny = ux;
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      // 法线朝内判定：向 +n 偏移 1.5m 若落在厂区多边形内，则该侧为墙内侧
      var inward = pointInPoly(mx + nx * 1.5, my + ny * 1.5, world) ? 1 : -1;
      var ang = Math.atan2(uy, ux);

      pushBox(outer, len, T * 0.5, H, mx - nx * inward * T * 0.25, my - ny * inward * T * 0.25, H / 2, ang);
      pushBox(inner, len, T * 0.5, H, mx + nx * inward * T * 0.25, my + ny * inward * T * 0.25, H / 2, ang);
      pushBox(coping, len, T * 1.9, 0.22, mx, my, H + 0.11, ang);
    }

    var mOuter = new THREE.MeshStandardMaterial(PALETTE.wallOuter);
    var mInner = new THREE.MeshStandardMaterial(PALETTE.wallInner);
    var mCope = new THREE.MeshStandardMaterial(PALETTE.coping);

    var g1 = new THREE.Mesh(mergeGeoms(outer), mOuter);
    var g2 = new THREE.Mesh(mergeGeoms(inner), mInner);
    var g3 = new THREE.Mesh(mergeGeoms(coping), mCope);
    [g1, g2, g3].forEach(function (m) {
      m.castShadow = true; m.receiveShadow = true; group.add(m);
    });

    group.userData.materials = [mOuter, mInner, mCope];
    group.userData.segmentCount = Math.max(0, world.length - 1);
    return group;
  }

  function pointInPoly(x, y, poly) {
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var xi = poly[i].x, yi = poly[i].y;
      var xj = poly[j].x, yj = poly[j].y;
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }

  // 道路：140 个四边形合并成一个 BufferGeometry（z=0.06 铺在草地上，材质开 polygonOffset 防 Z 冲突）
  function buildRoads(roads) {
    var pos = [], nor = [], triCount = 0, i, k;
    var Z = 0.06;

    for (i = 0; i < roads.length; i++) {
      var quad = roads[i];
      if (!quad || quad.length < 3) continue;
      var pts = quad.map(toW);
      // 统一为俯视逆时针，保证三角面朝 +Z
      var area2 = 0;
      for (k = 0; k < pts.length; k++) {
        var q = pts[(k + 1) % pts.length];
        area2 += pts[k].x * q.y - q.x * pts[k].y;
      }
      if (area2 < 0) pts.reverse();
      for (k = 1; k < pts.length - 1; k++) {
        pos.push(pts[0].x, pts[0].y, Z, pts[k].x, pts[k].y, Z, pts[k + 1].x, pts[k + 1].y, Z);
        nor.push(0, 0, 1, 0, 0, 1, 0, 0, 1);
        triCount++;
      }
    }

    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    geo.computeBoundingSphere();

    var mat = new THREE.MeshStandardMaterial({
      color: PALETTE.asphalt.color, roughness: 0.96, metalness: 0.02
    });
    mat.polygonOffset = true;
    mat.polygonOffsetFactor = -2;
    mat.polygonOffsetUnits = -2;

    var mesh = new THREE.Mesh(geo, mat);
    mesh.receiveShadow = true;
    mesh.name = 'roads';

    var group = new THREE.Group();
    group.name = 'roads-group';
    group.add(mesh);
    group.userData.quadCount = roads.length;
    group.userData.triangleCount = triCount;
    group.userData.materials = [mat];
    return group;
  }

  // 绿化树：树干（圆柱）+ 树冠（圆锥）两个 InstancedMesh，192 株一次提交
  function buildTrees(trees) {
    var group = new THREE.Group();
    group.name = 'trees';

    var trunkGeo = new THREE.CylinderGeometry(0.42, 0.62, 3.6, 6);
    trunkGeo.rotateX(Math.PI / 2);
    trunkGeo.translate(0, 0, 1.8);
    var crownGeo = new THREE.ConeGeometry(2.9, 8.4, 8);
    crownGeo.rotateX(Math.PI / 2);
    crownGeo.translate(0, 0, 3.4 + 4.2);

    var matTrunk = new THREE.MeshStandardMaterial(PALETTE.treeTrunk);
    var matCrown = new THREE.MeshStandardMaterial(PALETTE.treeCrown);

    var n = trees.length;
    var trunk = new THREE.InstancedMesh(trunkGeo, matTrunk, n);
    var crown = new THREE.InstancedMesh(crownGeo, matCrown, n);

    var m4 = new THREE.Matrix4(), quat = new THREE.Quaternion();
    var scale = new THREE.Vector3(), pos = new THREE.Vector3();
    var axis = new THREE.Vector3(0, 0, 1);

    for (var i = 0; i < n; i++) {
      var p = toW(trees[i]);
      var r = prng(i);
      var s = 0.82 + r * 0.6;
      quat.setFromAxisAngle(axis, r * Math.PI * 2);
      scale.set(s, s, s * (0.9 + r * 0.3));
      pos.set(p.x, p.y, 0);
      m4.compose(pos, quat, scale);
      trunk.setMatrixAt(i, m4);
      crown.setMatrixAt(i, m4);
    }
    trunk.instanceMatrix.needsUpdate = true;
    crown.instanceMatrix.needsUpdate = true;
    trunk.castShadow = true; trunk.receiveShadow = true;
    crown.castShadow = true; crown.receiveShadow = true;
    trunk.name = 'tree-trunks';
    crown.name = 'tree-crowns';

    group.add(trunk);
    group.add(crown);
    group.userData.count = n;
    group.userData.materials = [matTrunk, matCrown];
    return group;
  }

  // 地面大平板（浅灰绿色）
  function buildGround(cx, cy, w, d) {
    var geo = new THREE.PlaneGeometry(w, d, 1, 1);
    var mat = new THREE.MeshStandardMaterial({
      color: 0xc8d1c2, roughness: 0.99, metalness: 0.0
    });
    var mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(cx, cy, -0.05);
    mesh.receiveShadow = true;
    mesh.name = 'ground';
    return mesh;
  }

  // 台账网格（100m 间距细线，可选显示）
  function buildGrid(cx, cy, w, d, step) {
    var pos = [], i;
    var x0 = cx - w / 2, x1 = cx + w / 2;
    var y0 = cy - d / 2, y1 = cy + d / 2;
    step = step || 100;
    for (i = Math.ceil(x0 / step) * step; i <= x1; i += step) {
      pos.push(i, y0, 0.02, i, y1, 0.02);
    }
    for (i = Math.ceil(y0 / step) * step; i <= y1; i += step) {
      pos.push(x0, i, 0.02, x1, i, 0.02);
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    var mat = new THREE.LineBasicMaterial({ color: 0x9fb0a2, transparent: true, opacity: 0.35 });
    var lines = new THREE.LineSegments(geo, mat);
    lines.name = 'site-grid';
    return lines;
  }

  // 指北针：地盘 + 箭头（+Y 为图纸正北），"N" 文字由 main.js 用 sprite 补上
  function buildCompass(x, y) {
    var group = new THREE.Group();
    group.name = 'compass';
    group.position.set(x, y, 0);

    var plate = new THREE.Mesh(cylZ(48, 48, 3, 40), new THREE.MeshStandardMaterial(PALETTE.concreteMid));
    plate.position.z = 1.5;
    plate.receiveShadow = true;
    group.add(plate);

    var shaft = new THREE.Mesh(new THREE.BoxGeometry(7, 95, 5), new THREE.MeshStandardMaterial(PALETTE.steelDark));
    shaft.position.set(0, 12, 5);
    group.add(shaft);

    var head = new THREE.Mesh(coneZ(17, 44, 4), new THREE.MeshStandardMaterial(PALETTE.red));
    head.position.set(0, 82, 5);
    group.add(head);

    return group;
  }

  // ====================== 导出 ======================
  var P = {
    PALETTE: PALETTE,
    CATEGORY_COLORS: CATEGORY_COLORS,
    setOrigin: function (o) { ORIGIN = { e: o.e, n: o.n }; },
    toWorld: toW,
    resolveDims: resolveDims,
    buildStructure: buildStructure,
    buildBoundary: buildBoundary,
    buildRoads: buildRoads,
    buildTrees: buildTrees,
    buildGround: buildGround,
    buildGrid: buildGrid,
    buildCompass: buildCompass,
    mergeGeoms: mergeGeoms,
    pointInPoly: pointInPoly
  };

  // 供下次构建复用（不必须，但便于调试）
  P.SHAPE_BUILDERS = SHAPE_BUILDERS;
  return P;
})();
