import fs from 'fs';
import path from 'path';
import { Dwg_File_Type, LibreDwg } from '@mlightcad/libredwg-web';

const __dirname = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const wasmDir = path.join(__dirname, 'node_modules/@mlightcad/libredwg-web/wasm/');
const src = process.argv[2];
const outDir = process.argv[3] || './out';

const libredwg = await LibreDwg.create(wasmDir);
const content = fs.readFileSync(src);
const dwg = libredwg.dwg_read_data(content, Dwg_File_Type.DWG);
if (!dwg) {
  console.error('FAILED to parse dwg');
  process.exit(1);
}
const db = libredwg.convert(dwg);

const summary = {
  header: {},
  layers: [],
  blocks: [],
  entityCount: db.entities ? db.entities.length : 0,
  byType: {},
  byLayer: {},
};

// header vars
try {
  const h = db.header;
  const keys = ['INSUNITS', 'MEASUREMENT', 'EXTMIN', 'EXTMAX', 'LIMMIN', 'LIMMAX', 'DIMSCALE'];
  for (const k of keys) summary.header[k] = h ? h[k] : undefined;
} catch (e) { summary.headerError = String(e); }

if (db.tables && db.tables.layers) {
  for (const l of db.tables.layers) {
    summary.layers.push({ name: l.name, color: l.colorIndex, off: l.off, frozen: l.frozen, lineType: l.lineType });
  }
}

const ents = [];
for (const e of db.entities || []) {
  const t = e.type;
  summary.byType[t] = (summary.byType[t] || 0) + 1;
  summary.byLayer[e.layer] = (summary.byLayer[e.layer] || 0) + 1;
  const rec = { type: t, layer: e.layer, handle: e.handle };
  switch (t) {
    case 'LINE':
      rec.start = [e.startPoint.x, e.startPoint.y, e.startPoint.z];
      rec.end = [e.endPoint.x, e.endPoint.y, e.endPoint.z];
      break;
    case 'LWPOLYLINE':
    case 'POLYLINE':
      rec.vertices = (e.vertices || []).map(v => [v.x, v.y, v.bulge === undefined ? 0 : v.bulge]);
      rec.closed = !!e.shape || !!e.closed;
      break;
    case 'CIRCLE':
      rec.center = [e.center.x, e.center.y, e.center.z];
      rec.radius = e.radius;
      break;
    case 'ARC':
      rec.center = [e.center.x, e.center.y, e.center.z];
      rec.radius = e.radius;
      rec.startAngle = e.startAngle;
      rec.endAngle = e.endAngle;
      break;
    case 'TEXT':
      rec.text = e.text;
      rec.position = [e.startPoint.x, e.startPoint.y, e.startPoint.z];
      rec.height = e.height;
      break;
    case 'MTEXT':
      rec.text = e.text;
      rec.position = e.insertionPoint ? [e.insertionPoint.x, e.insertionPoint.y, e.insertionPoint.z] : null;
      rec.height = e.height;
      break;
    case 'INSERT':
      rec.blockName = e.name;
      rec.position = [e.insertionPoint.x, e.insertionPoint.y, e.insertionPoint.z];
      rec.scale = e.scale ? [e.scale.x, e.scale.y, e.scale.z] : [1, 1, 1];
      rec.rotation = e.rotation;
      rec.columnCount = e.columnCount; rec.rowCount = e.rowCount;
      break;
    default:
      rec.raw = Object.keys(e);
  }
  ents.push(rec);
}

fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'summary.json'), JSON.stringify(summary, null, 1), 'utf8');
fs.writeFileSync(path.join(outDir, 'entities.json'), JSON.stringify(ents), 'utf8');
console.log('entities:', ents.length);
console.log('types:', JSON.stringify(summary.byType, null, 1));
console.log('layers:', summary.layers.length);
console.log('header:', JSON.stringify(summary.header));
