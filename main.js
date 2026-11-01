// =============================================================================
// main.js —— 电厂三维总平面主程序（经典脚本，非 ES Module；可直接 file:// 双击打开）
// -----------------------------------------------------------------------------
// 结构：
//   1. 渲染器 / 场景 / 相机（Z-up）/ OrbitControls
//   2. 光照 + 阴影（PCFSoft，方向光覆盖约 1500×1600m）
//   3. 场地：地面大板 / 台账网格 / 道路 / 树 / 围墙 / 指北针
//   4. 71 个构筑物（builders.js 逐个生成）
//   5. 编号 sprite 标注、射线拾取、悬停高亮、双击聚焦、信息面板
//   6. 工具栏与左侧图层清单
//   7. 扩展钩子 window.PlantApp + window.postMessage（Hermes 8090 后台联动）
//
// 坐标约定：worldX = 图纸 E - meta.origin.e；worldY = 图纸 N - meta.origin.n；
//          Z = 高度（米）。相机 up = (0,0,1)，所有几何沿 +Z 生长。
// =============================================================================
(function () {
  'use strict';

  var DATA = window.PLANT_DATA;
  var B = window.PlantBuilders;

  // ---------- 类别（cat）中文名与顺序 ----------
  var CATS = [
    { key: 'main', name: '主厂房' },
    { key: 'electrical', name: '电气' },
    { key: 'cooling', name: '循环水' },
    { key: 'coal', name: '输煤煤场' },
    { key: 'aux', name: '辅助' },
    { key: 'living', name: '生活' },
    { key: 'construction', name: '施工临建' },
    { key: 'existing', name: '图面实测（未标注名称）' }
  ];
  var CAT_NAME = {};
  CATS.forEach(function (c) { CAT_NAME[c.key] = c.name; });

  var SHAPE_NAME = {
    box: '矩形建筑', gantry: '露天钢支架', switchyard: '配电装置', transformer: '变压器',
    hyperbolic: '双曲线冷却塔', chimney: '烟囱', tank: '灰库/粉仓', dome: '圆形煤仓',
    coalheap: '条形煤堆', gallery: '栈桥/天桥', duct: '烟道', pipes: '循环水管',
    pit: '水池/油池', pad: '场地平整', retaining: '挡墙'
  };
  var CIRCULAR_SHAPES = { hyperbolic: 1, chimney: 1, tank: 1, dome: 1 };

  var STATUS_COLOR = {
    normal: 0x3fae6a, warning: 0xe0a13a, alarm: 0xd2453c, offline: 0x8f959b
  };

  // ---------- DOM ----------
  var elCanvas = document.getElementById('scene');
  var elLoading = document.getElementById('loading');
  var elLoadingText = document.getElementById('loadingText');
  var elPanelTree = document.getElementById('tree');
  var elStatCount = document.getElementById('statCount');
  var elHdrStats = document.getElementById('hdrStats');
  var elInfo = document.getElementById('infoCard');
  var elInfoTitle = document.getElementById('infoTitle');
  var elInfoMeta = document.getElementById('infoMeta');
  var elInfoBody = document.getElementById('infoBody');
  var elInfoClose = document.getElementById('infoClose');
  var elHud = document.getElementById('hud');
  var elFatal = document.getElementById('fatal');
  var elToolbar = document.getElementById('toolbar');

  if (!DATA || !B) {
    fatal('缺少依赖：plant-data.js 或 builders.js 未能加载。请确认 4 个脚本的引入顺序。');
    return;
  }

  var ORIGIN = DATA.meta.origin;
  B.setOrigin(ORIGIN);

  function fatal(msg) {
    if (elFatal) {
      elFatal.textContent = msg;
      elFatal.classList.remove('hidden');
    }
    if (elLoading) elLoading.classList.add('hidden');
    console.error('[main] ' + msg);
  }

  // ===========================================================================
  // 1. 渲染器 / 场景 / 相机 / 控制器
  // ===========================================================================
  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas: elCanvas, antialias: true, alpha: false });
  } catch (err) {
    fatal('WebGL 初始化失败：' + err.message);
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  // 说明：本工程的配色（builders.js 的 PALETTE）直接按显示色书写。
  // three r128 没有 colorSpace 管理，若把 outputEncoding 设为 sRGBEncoding，
  // 所有材质色会被再做一次 linear→sRGB 提亮，整屏发灰发白；因此保持默认
  // LinearEncoding（即“所见即所写”），保证白模工程图对比度。
  if ('outputEncoding' in renderer && THREE.LinearEncoding) renderer.outputEncoding = THREE.LinearEncoding;
  renderer.setClearColor(0xeef1f4, 1);

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0xeef1f4);
  scene.fog = null;                 // 雾默认关闭（工具栏「雾」可开）

  // ---- 场地范围（世界坐标，单位 m） ----
  function toWorldPt(p) { return { x: p[0] - ORIGIN.e, y: p[1] - ORIGIN.n }; }

  var bounds = (function () {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    function add(x, y) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
    (DATA.boundary || []).forEach(function (p) { var w = toWorldPt(p); add(w.x, w.y); });
    (DATA.roads || []).forEach(function (q) {
      q.forEach(function (p) { var w = toWorldPt(p); add(w.x, w.y); });
    });
    (DATA.structures || []).forEach(function (s) { add(s.x - ORIGIN.e, s.y - ORIGIN.n); });
    (DATA.trees || []).forEach(function (p) { var w = toWorldPt(p); add(w.x, w.y); });
    return {
      minX: minX, minY: minY, maxX: maxX, maxY: maxY,
      cx: (minX + maxX) / 2, cy: (minY + maxY) / 2,
      w: maxX - minX, h: maxY - minY
    };
  })();

  // 地面大板 1700×1500m（覆盖厂区 + 道路 + 施工临建）
  var GROUND_W = 1700, GROUND_D = 1500;
  var CENTER = new THREE.Vector3(bounds.cx, bounds.cy, 0);

  var camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 1, 12000);
  // Z-up：必须在 new OrbitControls 之前设置（OrbitControls 构造时按 camera.up 建四元数）
  camera.up.set(0, 0, 1);
  var HOME_POS = new THREE.Vector3(CENTER.x + 620, CENTER.y - 965, 800);
  camera.position.copy(HOME_POS);
  camera.lookAt(CENTER);

  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.copy(CENTER);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.55;
  controls.zoomSpeed = 0.9;
  controls.panSpeed = 0.85;
  controls.screenSpacePanning = false;        // 沿地面（XY 平面）平移
  controls.minDistance = 20;
  controls.maxDistance = 5000;
  controls.maxPolarAngle = Math.PI * 0.495;   // 不允许钻到地面以下
  controls.update();

  // ===========================================================================
  // 2. 光照 + 阴影
  // ===========================================================================
  var ambient = new THREE.AmbientLight(0xffffff, 0.12);
  scene.add(ambient);

  var hemi = new THREE.HemisphereLight(0xdfe9f5, 0x8d9184, 0.40);
  scene.add(hemi);

  var sun = new THREE.DirectionalLight(0xfff2df, 1.05);
  sun.position.set(CENTER.x - 620, CENTER.y - 980, 1250);
  sun.target.position.copy(CENTER);
  scene.add(sun.target);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -900;
  sun.shadow.camera.right = 900;
  sun.shadow.camera.top = 950;
  sun.shadow.camera.bottom = -950;
  sun.shadow.camera.near = 100;
  sun.shadow.camera.far = 4200;
  sun.shadow.camera.updateProjectionMatrix();
  sun.shadow.bias = -0.0006;
  sun.shadow.normalBias = 0.6;
  scene.add(sun);

  // ===========================================================================
  // 3. 场地：地面 / 网格 / 围墙 / 道路 / 树 / 指北针
  // ===========================================================================
  var ground = B.buildGround(bounds.cx, bounds.cy, GROUND_W, GROUND_D);
  scene.add(ground);

  var grid = B.buildGrid(bounds.cx, bounds.cy, GROUND_W, GROUND_D, 100);
  scene.add(grid);

  var siteLayer = new THREE.Group();   // 「场地」层：道路 + 树 + 围墙
  siteLayer.name = 'site-layer';
  scene.add(siteLayer);

  var wallGroup = B.buildBoundary(DATA.boundary || []);
  siteLayer.add(wallGroup);

  var roadGroup = B.buildRoads(DATA.roads || []);
  siteLayer.add(roadGroup);

  var treeGroup = B.buildTrees(DATA.trees || []);
  siteLayer.add(treeGroup);

  var inspectLayer = new THREE.Group(); // 巡检点标记层
  inspectLayer.name = 'inspect-layer';
  scene.add(inspectLayer);

  // ===========================================================================
  // 4. 编号 sprite（Canvas 贴图，depthTest 关闭 → 始终可见）
  // ===========================================================================
  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function makeLabelSprite(text, opt) {
    opt = opt || {};
    var fontSize = opt.fontSize || 56;
    var pad = 24;
    var c = document.createElement('canvas');
    var ctx = c.getContext('2d');
    var font = '600 ' + fontSize + 'px "Microsoft YaHei","PingFang SC","Segoe UI",Arial,sans-serif';
    ctx.font = font;
    var tw = Math.ceil(ctx.measureText(text).width);
    var w = Math.max(tw + pad * 2, fontSize * 1.6 + pad);
    var h = fontSize + pad * 2;
    c.width = w;
    c.height = h;

    ctx = c.getContext('2d');
    ctx.font = font;
    ctx.fillStyle = opt.bg || 'rgba(16,30,42,0.82)';
    roundRect(ctx, 3, 3, w - 6, h - 6, 16);
    ctx.fill();
    ctx.strokeStyle = opt.border || 'rgba(160,200,228,0.85)';
    ctx.lineWidth = 3;
    ctx.stroke();

    ctx.fillStyle = opt.color || '#e9f2f9';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, w / 2, h / 2 + 2);

    var tex = new THREE.CanvasTexture(c);
    // 贴图按“显示色”直接使用（与 renderer 的 LinearEncoding 输出一致），
    // 若改成 sRGBEncoding 会让标注文字比画布上的颜色更深。
    tex.needsUpdate = true;

    var mat = new THREE.SpriteMaterial({
      map: tex, transparent: true, depthTest: false, depthWrite: false
    });
    var sp = new THREE.Sprite(mat);
    var hh = opt.height || 18;
    sp.scale.set(hh * (w / h), hh, 1);
    sp.renderOrder = 30;
    return sp;
  }

  // ===========================================================================
  // 5. 构建 71 个构筑物
  // ===========================================================================
  var entries = [];        // 全部构件条目
  var byId = {};           // id → entry
  var pickables = [];      // 参与拾取的 mesh

  var structRoot = new THREE.Group();
  structRoot.name = 'structures';
  scene.add(structRoot);

  var labelGroup = new THREE.Group();
  labelGroup.name = 'labels';
  scene.add(labelGroup);

  if (elLoadingText) elLoadingText.textContent = '正在生成 ' + DATA.structures.length + ' 个构筑物…';

  DATA.structures.forEach(function (s) {
    var group;
    try {
      group = B.buildStructure(s);
    } catch (err) {
      console.error('[main] 构建 ' + s.id + ' 失败：', err);
      return;
    }
    structRoot.add(group);

    var entry = {
      id: s.id,
      data: s,
      group: group,
      materials: group.userData.materials || [],
      topZ: group.userData.topZ || (s.h || 10),
      status: 'normal',
      blink: false,
      visible: true,
      label: null,
      ui: null
    };
    entries.push(entry);
    byId[s.id] = entry;

    // 拾取列表：射线命中的 mesh → userData.structId
    group.traverse(function (o) {
      if (o.isMesh) pickables.push(o);
    });

    // 编号 sprite 标注（放在构件顶点上方，跟随构件世界位置）
    var label = makeLabelSprite(String(s.code || s.id), { fontSize: 54, height: 12 });
    label.position.set(group.position.x, group.position.y, entry.topZ + 7);
    label.userData.structId = s.id;
    labelGroup.add(label);
    entry.label = label;
  });

  // 指北针（放在厂区西北角外，+Y 指向图纸正北）
  var compass = B.buildCompass(bounds.minX - 90, bounds.maxY + 120);
  siteLayer.add(compass);
  var northSprite = makeLabelSprite('N', {
    fontSize: 64, height: 30, bg: 'rgba(170,54,46,0.9)', border: 'rgba(255,210,200,0.95)'
  });
  northSprite.position.set(compass.position.x, compass.position.y + 118, 26);
  siteLayer.add(northSprite);

  // ===========================================================================
  // 6. 材质收集（线框切换用）
  // ===========================================================================
  var allMats = [];
  function collectMaterials() {
    var list = [];
    scene.traverse(function (o) {
      var m = o.material;
      if (!m) return;
      var arr = Array.isArray(m) ? m : [m];
      arr.forEach(function (mm) {
        if (mm && mm.isMeshStandardMaterial && list.indexOf(mm) === -1) list.push(mm);
      });
    });
    allMats = list;
  }
  collectMaterials();

  // ===========================================================================
  // 7. 外观状态（悬停 / 选中 / 告警 / 离线）
  // ===========================================================================
  var hovered = null;
  var selected = null;
  var dirty = true;

  function baseOf(m) {
    if (!m.userData._base) {
      m.userData._base = {
        color: m.color ? m.color.getHex() : 0xffffff,
        emissive: m.emissive ? m.emissive.getHex() : 0x000000,
        ei: (m.emissiveIntensity === undefined ? 1 : m.emissiveIntensity)
      };
    }
    return m.userData._base;
  }

  function applyAppearance(entry) {
    if (!entry) return;
    var isSel = (entry === selected);
    var isHov = (entry === hovered);
    var mats = entry.materials || [];
    for (var i = 0; i < mats.length; i++) {
      var m = mats[i];
      if (!m) continue;
      var base = baseOf(m);
      if (m.color) m.color.setHex(base.color);
      if (m.emissive) m.emissive.setHex(base.emissive);
      m.emissiveIntensity = base.ei;

      if (entry.status === 'alarm') {
        if (m.color) m.color.setHex(0xd2453c);
        if (m.emissive) m.emissive.setHex(0x8d1d17);
        m.emissiveIntensity = 0.55;
      } else if (entry.status === 'warning') {
        if (m.color) m.color.lerp(new THREE.Color(0xe0a13a), 0.7);
        if (m.emissive) m.emissive.setHex(0x6b3f00);
        m.emissiveIntensity = 0.32;
      } else if (entry.status === 'offline') {
        if (m.color) m.color.multiplyScalar(0.42);
        if (m.emissive) m.emissive.setHex(0x000000);
        m.emissiveIntensity = 0;
      }

      if (isSel) {
        if (m.emissive) m.emissive.setHex(0x1b4f7d);
        m.emissiveIntensity = 0.62;
        if (m.color) m.color.offsetHSL(0, 0.04, 0.05);
      } else if (isHov) {
        if (m.emissive) m.emissive.setHex(0x14405f);
        m.emissiveIntensity = 0.40;
      }
    }
    dirty = true;
  }

  function refreshAllAppearance() {
    entries.forEach(function (e) { applyAppearance(e); });
  }

  // 告警闪烁（只在有闪烁构件时持续重绘）
  function updateBlink(now) {
    var any = false;
    for (var i = 0; i < entries.length; i++) {
      var e = entries[i];
      if (e.status === 'alarm' && e.blink && e.visible) {
        any = true;
        var k = 0.30 + 0.70 * (0.5 + 0.5 * Math.sin(now * 0.006));
        for (var j = 0; j < e.materials.length; j++) {
          e.materials[j].emissiveIntensity = 0.22 + k * 0.75;
        }
      }
    }
    return any;
  }

  // ===========================================================================
  // 8. 拾取
  // ===========================================================================
  var raycaster = new THREE.Raycaster();
  var pointer = new THREE.Vector2();
  var groundPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);

  function setPointer(ev) {
    pointer.x = (ev.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -(ev.clientY / window.innerHeight) * 2 + 1;
  }

  // 射线命中 mesh 后向上查找 userData.structId（构件根节点的 id）
  function findStructId(obj) {
    var o = obj;
    while (o) {
      if (o.userData && o.userData.structId) return o.userData.structId;
      o = o.parent;
    }
    return null;
  }

  function pickAt(ev) {
    setPointer(ev);
    raycaster.setFromCamera(pointer, camera);
    var hits = raycaster.intersectObjects(pickables, false);
    for (var i = 0; i < hits.length; i++) {
      var id = findStructId(hits[i].object);
      if (!id) continue;
      var entry = byId[id];
      if (entry && entry.visible) return entry;
    }
    return null;
  }

  var pointerDown = null;

  elCanvas.addEventListener('pointerdown', function (ev) {
    pointerDown = { x: ev.clientX, y: ev.clientY, button: ev.button };
  });

  elCanvas.addEventListener('pointerup', function (ev) {
    if (!pointerDown) return;
    var dist = Math.sqrt(Math.pow(ev.clientX - pointerDown.x, 2) + Math.pow(ev.clientY - pointerDown.y, 2));
    var button = pointerDown.button;
    pointerDown = null;
    if (button !== 0 || dist > 6) return;  // 拖动旋转/右键平移不触发选择
    var entry = pickAt(ev);
    select(entry ? entry.id : null);
  });

  elCanvas.addEventListener('pointermove', function (ev) {
    updateHud(ev);
    var entry = pickAt(ev);
    if (entry !== hovered) {
      var prev = hovered;
      hovered = entry;
      if (prev) applyAppearance(prev);
      if (hovered) applyAppearance(hovered);
      syncListHover();
    }
    elCanvas.style.cursor = hovered ? 'pointer' : 'default';
  });

  elCanvas.addEventListener('pointerleave', function () {
    if (hovered) {
      var prev = hovered;
      hovered = null;
      applyAppearance(prev);
      syncListHover();
    }
  });

  elCanvas.addEventListener('dblclick', function (ev) {
    var entry = pickAt(ev);
    if (entry) focusOn(entry.id);       // 双击聚焦到选中构件
  });

  // ===========================================================================
  // 9. 信息面板
  // ===========================================================================
  function fmt(v) {
    if (v === undefined || v === null || !isFinite(v)) return '—';
    return (Math.round(v * 10) / 10).toString();
  }

  function showInfo(entry) {
    if (!entry) {
      elInfo.classList.add('hidden');
      return;
    }
    var s = entry.data;
    var dim = entry.group.userData.dim || { w: s.w, d: s.d, h: s.h };
    var isCircle = !!CIRCULAR_SHAPES[s.shape];
    var dimText = isCircle
      ? ('Ø ' + fmt(dim.d) + ' × H ' + fmt(dim.h) + ' m')
      : (fmt(dim.w) + ' × ' + fmt(dim.d) + ' × ' + fmt(dim.h) + ' m');

    elInfoTitle.textContent = s.name || s.id;
    elInfoMeta.textContent = '编号 ' + (s.code || '—') + ' · ' +
      (CAT_NAME[s.cat] || s.cat) + ' · ' + (SHAPE_NAME[s.shape] || s.shape);

    var rows = [
      ['类别', (CAT_NAME[s.cat] || s.cat) + '（' + s.cat + '）'],
      ['构件类型', (SHAPE_NAME[s.shape] || s.shape) + '（' + s.shape + '）'],
      ['设计尺寸', dimText],
      ['占地面积', fmt(s.area) + ' m²'],
      ['平面坐标', 'E ' + fmt(s.x) + ' / N ' + fmt(s.y) + '（图纸测量坐标）'],
      ['世界坐标', 'x ' + fmt(s.x - ORIGIN.e) + ' / y ' + fmt(s.y - ORIGIN.n) + ' / z 0'],
      ['备注', s.note || '—'],
      ['数据来源', s.src || '—']
    ];

    elInfoBody.innerHTML = '';
    rows.forEach(function (r) {
      var row = document.createElement('div');
      row.className = 'info-row';
      var k = document.createElement('div');
      k.className = 'info-k';
      k.textContent = r[0];
      var v = document.createElement('div');
      v.className = 'info-v';
      v.textContent = r[1];
      row.appendChild(k);
      row.appendChild(v);
      elInfoBody.appendChild(row);
    });

    elInfo.classList.remove('hidden');
  }

  elInfoClose.addEventListener('click', function () { select(null); });

  function select(id) {
    var next = id ? (byId[id] || null) : null;
    if (next && !next.visible) setVisible(id, true);  // 隐藏的构件先显示再选中
    if (next === selected) {
      showInfo(next);
      return;
    }
    var prev = selected;
    selected = next;
    if (prev) applyAppearance(prev);
    if (selected) applyAppearance(selected);
    showInfo(selected);
    dirty = true;

    // 对外回调：DSH / Hermes 侧边栏可据此同步选中状态
    if (app && typeof app.onSelect === 'function') {
      try {
        app.onSelect(selected ? {
          id: selected.id,
          name: selected.data.name,
          cat: selected.data.cat,
          data: selected.data,
          group: selected.group
        } : null);
      } catch (err) {
        console.error('[main] onSelect 回调异常：', err);
      }
    }
    postToHost({
      type: 'plant:selected',
      id: selected ? selected.id : null,
      name: selected ? selected.data.name : null
    });
  }

  // ===========================================================================
  // 10. 视角聚焦（带补间动画）
  // ===========================================================================
  var tween = null;
  var HOME_TARGET = CENTER.clone();

  function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
  }

  function startTween(toPos, toTarget, dur) {
    tween = {
      t0: performance.now(),
      dur: dur || 720,
      fromPos: camera.position.clone(),
      fromTarget: controls.target.clone(),
      toPos: toPos.clone(),
      toTarget: toTarget.clone()
    };
    dirty = true;
  }

  function focusOn(id) {
    var entry = byId[id];
    if (!entry) {
      console.warn('[main] focusOn: 未找到构件 ' + id);
      return false;
    }
    if (!entry.visible) setVisible(id, true);

    var box = new THREE.Box3().setFromObject(entry.group);
    var center = box.getCenter(new THREE.Vector3());
    var size = box.getSize(new THREE.Vector3());
    var radius = Math.max(12, size.length() / 2);

    // 保持当前观察方向，收缩到合适距离
    var dir = new THREE.Vector3().subVectors(camera.position, controls.target);
    if (dir.lengthSq() < 1) dir.set(0.6, -0.9, 0.75);
    dir.normalize();

    var dist = Math.max(radius * 2.8, 45) + 25;
    var toPos = center.clone().add(dir.multiplyScalar(dist));
    startTween(toPos, center, 720);
    select(id);
    return true;
  }

  function resetView() {
    startTween(HOME_POS.clone(), HOME_TARGET.clone(), 800);
  }

  // ===========================================================================
  // 11. 显示控制
  // ===========================================================================
  function setVisible(id, visible) {
    var entry = byId[id];
    if (!entry) {
      console.warn('[main] setVisible: 未找到构件 ' + id);
      return false;
    }
    entry.visible = !!visible;
    entry.group.visible = entry.visible;
    if (entry.label) entry.label.visible = entry.visible && state.labels;
    if (!entry.visible) {
      if (selected === entry) select(null);
      if (hovered === entry) hovered = null;
    }
    if (entry.ui && entry.ui.cb) entry.ui.cb.checked = entry.visible;
    updateGroupCheckboxes();
    dirty = true;
    return true;
  }

  function setStatus(id, status) {
    var entry = byId[id];
    if (!entry) {
      console.warn('[main] setStatus: 未找到构件 ' + id);
      return false;
    }
    if (['normal', 'warning', 'alarm', 'offline'].indexOf(status) === -1) {
      console.warn('[main] setStatus: 非法状态 ' + status);
      return false;
    }
    entry.status = status;
    entry.blink = (status === 'alarm');
    applyAppearance(entry);
    return true;
  }

  // 告警：level 数字（1 轻微 / 2 闪烁 / 3 强闪烁）；也可传 'alarm'
  function setAlarm(id, level) {
    var entry = byId[id];
    if (!entry) {
      console.warn('[main] setAlarm: 未找到构件 ' + id);
      return false;
    }
    entry.status = 'alarm';
    entry.blink = (level === undefined || level === null) ? true : (Number(level) >= 2);
    applyAppearance(entry);
    dirty = true;
    return true;
  }

  // 巡检点：{id, name, x, y, z, status}
  // 注意：x / y 为「世界坐标」（已减 meta.origin）；若传入图纸坐标请先减 origin。
  var inspectSeq = 0;
  function addInspectionPoint(o) {
    o = o || {};
    var id = o.id || ('IP-' + (++inspectSeq));
    var status = o.status || 'normal';
    var color = STATUS_COLOR[status] || STATUS_COLOR.normal;

    var group = new THREE.Group();
    group.name = 'inspect-' + id;
    group.position.set(Number(o.x) || 0, Number(o.y) || 0, Number(o.z) || 0);

    var poleGeo = new THREE.CylinderGeometry(0.5, 0.5, 6, 8);
    poleGeo.rotateX(Math.PI / 2);
    var pole = new THREE.Mesh(poleGeo, new THREE.MeshStandardMaterial({ color: 0x8d949b, roughness: 0.6, metalness: 0.4 }));
    pole.position.z = 3;
    group.add(pole);

    var mat = new THREE.MeshStandardMaterial({
      color: color, emissive: color, emissiveIntensity: 0.55, roughness: 0.4, metalness: 0.2
    });
    var ball = new THREE.Mesh(new THREE.SphereGeometry(3.4, 18, 12), mat);
    ball.position.z = 7;
    ball.castShadow = true;
    group.add(ball);

    var ringGeo = new THREE.TorusGeometry(6.5, 0.55, 6, 32);
    var ring = new THREE.Mesh(ringGeo, new THREE.MeshStandardMaterial({
      color: color, emissive: color, emissiveIntensity: 0.35, roughness: 0.5
    }));
    ring.position.z = 0.4;
    group.add(ring);

    if (o.name) {
      var sp = makeLabelSprite(String(o.name), {
        fontSize: 44, height: 13,
        bg: 'rgba(16,30,42,0.86)', border: 'rgba(180,215,240,0.9)'
      });
      sp.position.z = 16;
      group.add(sp);
    }

    group.userData.id = id;
    group.userData.name = o.name || id;
    group.userData.status = status;
    group.userData.markerMaterial = mat;
    // 便于外部链路更新单个巡检点状态
    group.userData.setStatus = function (st) {
      var c = STATUS_COLOR[st] || STATUS_COLOR.normal;
      group.userData.status = st;
      mat.color.setHex(c);
      mat.emissive.setHex(c);
      ring.material.color.setHex(c);
      ring.material.emissive.setHex(c);
      dirty = true;
    };

    inspectLayer.add(group);
    dirty = true;
    return group;
  }

  // ===========================================================================
  // 12. 左侧构件清单（按 cat 分组，可勾选显隐）
  // ===========================================================================
  var itemRows = [];

  function updateGroupCheckboxes() {
    var heads = elPanelTree.querySelectorAll('.cat-head input');
    for (var i = 0; i < heads.length; i++) {
      var cb = heads[i];
      var cat = cb.getAttribute('data-cat');
      var list = entries.filter(function (e) { return e.data.cat === cat; });
      var visibleCount = list.filter(function (e) { return e.visible; }).length;
      cb.checked = visibleCount > 0;
      cb.indeterminate = visibleCount > 0 && visibleCount < list.length;
    }
  }

  function buildPanelTree() {
    elPanelTree.innerHTML = '';

    CATS.forEach(function (cat) {
      var items = entries.filter(function (e) { return e.data.cat === cat.key; });
      if (!items.length) return;

      var wrap = document.createElement('div');
      wrap.className = 'cat-group';

      var head = document.createElement('div');
      head.className = 'cat-head';

      var gcb = document.createElement('input');
      gcb.type = 'checkbox';
      gcb.checked = true;
      gcb.setAttribute('data-cat', cat.key);
      gcb.title = '整组显示 / 隐藏';

      var dot = document.createElement('span');
      dot.className = 'cat-dot';
      dot.style.background = B.CATEGORY_COLORS[cat.key] || '#8b929a';

      var name = document.createElement('span');
      name.className = 'cat-name';
      name.textContent = cat.name;

      var count = document.createElement('span');
      count.className = 'cat-count';
      count.textContent = items.length;

      head.appendChild(gcb);
      head.appendChild(dot);
      head.appendChild(name);
      head.appendChild(count);

      var list = document.createElement('div');
      list.className = 'cat-items';

      items.forEach(function (entry) {
        var row = document.createElement('div');
        row.className = 'item';
        row.setAttribute('data-id', entry.id);

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = true;
        cb.title = '显示 / 隐藏该构件';

        var idot = document.createElement('span');
        idot.className = 'item-dot';
        idot.style.background = B.CATEGORY_COLORS[cat.key] || '#8b929a';

        var nm = document.createElement('span');
        nm.className = 'item-name';
        nm.textContent = entry.data.name;
        nm.title = entry.data.name + '（点击聚焦）';

        var code = document.createElement('span');
        code.className = 'item-code';
        code.textContent = entry.data.code;

        row.appendChild(cb);
        row.appendChild(idot);
        row.appendChild(nm);
        row.appendChild(code);

        cb.addEventListener('change', function () { setVisible(entry.id, cb.checked); });
        nm.addEventListener('click', function () { focusOn(entry.id); });
        row.addEventListener('mouseenter', function () {
          if (!entry.visible) return;
          hovered = entry;
          applyAppearance(entry);
          syncListHover();
        });
        row.addEventListener('mouseleave', function () {
          if (hovered === entry) {
            hovered = null;
            applyAppearance(entry);
            syncListHover();
          }
        });

        entry.ui = { cb: cb, row: row };
        itemRows.push({ entry: entry, row: row });
        list.appendChild(row);
      });

      // 组勾选：整组显隐
      gcb.addEventListener('change', function () {
        items.forEach(function (entry) { setVisible(entry.id, gcb.checked); });
      });

      // 折叠
      name.addEventListener('click', function () {
        wrap.classList.toggle('collapsed');
      });

      wrap.appendChild(head);
      wrap.appendChild(list);
      elPanelTree.appendChild(wrap);
    });

    if (elStatCount) {
      elStatCount.textContent = DATA.structures.length + ' 个构件 / ' + CATS.length + ' 类';
    }
    // 顶部徽标同样取自数据，随补录构件自动更新
    if (elHdrStats) {
      elHdrStats.textContent = DATA.structures.length + ' 构筑物 · ' +
        (DATA.roads ? DATA.roads.length : 0) + ' 道路 · ' +
        (DATA.trees ? DATA.trees.length : 0) + ' 绿化';
    }
    updateGroupCheckboxes();
  }

  function syncListHover() {
    for (var i = 0; i < itemRows.length; i++) {
      var r = itemRows[i];
      var on = (r.entry === hovered || r.entry === selected) && r.entry.visible;
      if (on) r.row.classList.add('is-active');
      else r.row.classList.remove('is-active');
    }
  }

  // ===========================================================================
  // 13. 工具栏
  // ===========================================================================
  var state = {
    wireframe: false,
    lightsOn: true,
    labels: true,
    site: true,
    grid: true,
    fog: false
  };

  function setActive(act, on) {
    var btn = elToolbar.querySelector('[data-act="' + act + '"]');
    if (btn) {
      btn.classList.toggle('active', !!on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
  }

  function toggleWireframe() {
    state.wireframe = !state.wireframe;
    for (var i = 0; i < allMats.length; i++) allMats[i].wireframe = state.wireframe;
    setActive('wireframe', state.wireframe);
    dirty = true;
  }

  function toggleLights() {
    state.lightsOn = !state.lightsOn;
    if (state.lightsOn) {
      sun.intensity = 1.05;
      ambient.intensity = 0.12;
      hemi.intensity = 0.40;
    } else {
      sun.intensity = 0.0;
      ambient.intensity = 0.42;
      hemi.intensity = 0.80;
    }
    setActive('lights', !state.lightsOn);   // 按钮高亮表示「已关闭直射光」
    dirty = true;
  }

  function toggleLabels() {
    state.labels = !state.labels;
    labelGroup.visible = state.labels;
    entries.forEach(function (e) {
      if (e.label) e.label.visible = state.labels && e.visible;
    });
    setActive('labels', state.labels);
    dirty = true;
  }

  function toggleSite() {
    state.site = !state.site;
    siteLayer.visible = state.site;
    setActive('site', !state.site);         // 按钮高亮表示「已隐藏场地」
    dirty = true;
  }

  function toggleGrid() {
    state.grid = !state.grid;
    grid.visible = state.grid;
    setActive('grid', state.grid);
    dirty = true;
  }

  function toggleFog() {
    state.fog = !state.fog;
    scene.fog = state.fog ? new THREE.Fog(0xeef1f4, 1100, 3600) : null;
    setActive('fog', state.fog);
    dirty = true;
  }

  elToolbar.addEventListener('click', function (ev) {
    var btn = ev.target.closest ? ev.target.closest('button[data-act]') : null;
    if (!btn) return;
    var act = btn.getAttribute('data-act');
    if (act === 'wireframe') toggleWireframe();
    else if (act === 'lights') toggleLights();
    else if (act === 'labels') toggleLabels();
    else if (act === 'site') toggleSite();
    else if (act === 'grid') toggleGrid();
    else if (act === 'fog') toggleFog();
    else if (act === 'reset') resetView();
  });

  // 全部显示 / 全部隐藏
  document.getElementById('btnShowAll').addEventListener('click', function () {
    entries.forEach(function (e) { setVisible(e.id, true); });
  });
  document.getElementById('btnHideAll').addEventListener('click', function () {
    entries.forEach(function (e) { setVisible(e.id, false); });
  });

  // Esc 关闭信息面板
  window.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') select(null);
  });

  // ===========================================================================
  // 14. 鼠标所指世界坐标（HUD）
  // ===========================================================================
  function updateHud(ev) {
    setPointer(ev);
    raycaster.setFromCamera(pointer, camera);
    var hit = new THREE.Vector3();
    if (!raycaster.ray.intersectPlane(groundPlane, hit)) {
      elHud.textContent = '—';
      return;
    }
    var e = hit.x + ORIGIN.e;
    var n = hit.y + ORIGIN.n;
    elHud.textContent =
      'E ' + e.toFixed(1) + ' m   N ' + n.toFixed(1) + ' m   Z 0.0 m' +
      '   ｜   Z-up 高度模式（世界原点 = 图纸 E' + ORIGIN.e + ' / N' + ORIGIN.n + '）';
  }

  // ===========================================================================
  // 15. 视图大小变化
  // ===========================================================================
  window.addEventListener('resize', function () {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight, false);
    dirty = true;
  });

  // ===========================================================================
  // 16. 渲染循环（只做 controls.update + render，几何不重建）
  // ===========================================================================
  controls.addEventListener('change', function () { dirty = true; });

  function frame(now) {
    requestAnimationFrame(frame);
    var t = (typeof now === 'number') ? now : performance.now();

    if (tween) {
      var k = Math.min(1, (t - tween.t0) / tween.dur);
      var e = easeInOut(k);
      camera.position.lerpVectors(tween.fromPos, tween.toPos, e);
      controls.target.lerpVectors(tween.fromTarget, tween.toTarget, e);
      camera.lookAt(controls.target);
      if (k >= 1) tween = null;
      dirty = true;
    }

    if (controls.update()) dirty = true;

    var blinking = updateBlink(t);
    if (dirty || blinking) {
      renderer.render(scene, camera);
      dirty = false;
    }
  }

  // ===========================================================================
  // 17. 扩展钩子 window.PlantApp
  // ---------------------------------------------------------------------------
  // 用法示例（浏览器控制台 / Hermes 后台 iframe 父页面）：
  //   PlantApp.setAlarm('ST-127A', 3)          // 冷却塔强闪烁告警（红色）
  //   PlantApp.setStatus('ST-108', 'offline')  // 烟囱离线（灰暗）
  //   PlantApp.setVisible('ST-S-25', false)    // 隐藏大件堆场
  //   PlantApp.focusOn('ST-119')               // 相机飞向 500kV 配电装置
  //   PlantApp.addInspectionPoint({id:'IP-1', name:'1号塔巡检', x:-500, y:900, z:5, status:'warning'})
  //   PlantApp.onSelect = function (info) { console.log(info); }   // 选中回调
  //
  // exportGLB：本文件不实现（项目禁止额外依赖）。若后续需要导出，
  //   可在此处挂 THREE.GLTFExporter（需另加 vendor/GLTFExporter.js）并
  //   调用 new THREE.GLTFExporter().parse(scene, cb) 生成 .glb 二进制。
  // ===========================================================================
  var app = window.PlantApp = {
    scene: scene,
    camera: camera,
    renderer: renderer,
    controls: controls,
    structures: entries,          // [{id, data, group, materials, status, visible}]
    data: DATA,
    version: '1.0.0',
    focusOn: focusOn,
    setVisible: setVisible,
    setAlarm: setAlarm,
    setStatus: setStatus,
    addInspectionPoint: addInspectionPoint,
    select: select,
    getSelected: function () { return selected ? selected.id : null; },
    resetView: resetView,
    requestRender: function () { dirty = true; },
    onSelect: null
  };

  // ===========================================================================
  // 18. window.postMessage 联动（Hermes 后台 8090 端口 iframe 集成）
  // ---------------------------------------------------------------------------
  // 集成方式：Hermes（http://127.0.0.1:8090）中通过 <iframe src=".../index.html">
  // 嵌入本页面，父页面用下面三条协议驱动三维场景：
  //   父 → iframe：iframe.contentWindow.postMessage({type:'plant:focus',  id:'ST-127A'}, '*')
  //                iframe.contentWindow.postMessage({type:'plant:alarm',  id:'ST-108', level:3}, '*')
  //                iframe.contentWindow.postMessage({type:'plant:status', id:'ST-119', status:'warning'}, '*')
  //   还支持 plant:visible（id, visible）与 plant:inspect（point）。
  //   iframe → 父：选中构件时回发 {type:'plant:selected', id, name}（见 postToHost）。
  // 注意：file:// 直接打开时页面 origin 为 "null"，此处不校验 ev.origin 以便本地调试；
  //   部署到 8090 同源或固定端口后，建议改为白名单校验：
  //   if (ev.origin !== 'http://127.0.0.1:8090') return;
  // ===========================================================================
  var HOST_ORIGIN = 'http://127.0.0.1:8090';

  function postToHost(payload) {
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(payload, HOST_ORIGIN);
      }
    } catch (err) {
      /* 跨域/未嵌入时静默失败 */
    }
  }
  app.postToHost = postToHost;

  window.addEventListener('message', function (ev) {
    var d = ev.data;
    if (typeof d === 'string') {
      try { d = JSON.parse(d); } catch (err) { return; }
    }
    if (!d || typeof d !== 'object' || !d.type) return;

    switch (d.type) {
      case 'plant:focus':
        focusOn(d.id);
        break;
      case 'plant:alarm':
        setAlarm(d.id, d.level);
        break;
      case 'plant:status':
        setStatus(d.id, d.status);
        break;
      case 'plant:visible':
        setVisible(d.id, d.visible !== false);
        break;
      case 'plant:inspect':
        addInspectionPoint(d.point || d);
        break;
      default:
        break;
    }
  });

  // ===========================================================================
  // 19. 启动
  // ===========================================================================
  buildPanelTree();
  setActive('labels', true);
  setActive('grid', true);

  // 首帧渲染 + 关闭加载遮罩
  renderer.render(scene, camera);
  dirty = false;
  requestAnimationFrame(frame);

  if (elLoading) {
    setTimeout(function () {
      elLoading.classList.add('hidden');
    }, 260);
  }

  console.log('[main] 电厂三维总平面已就绪：' +
    entries.length + ' 个构筑物 / ' + (DATA.roads || []).length + ' 条道路 / ' +
    (DATA.trees || []).length + ' 棵树；钩子见 window.PlantApp');
})();
