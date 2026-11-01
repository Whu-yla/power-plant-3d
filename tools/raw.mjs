import fs from 'fs';
import path from 'path';
import { Dwg_File_Type, LibreDwg } from '@mlightcad/libredwg-web';

const __dirname = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const wasmDir = path.join(__dirname, 'node_modules/@mlightcad/libredwg-web/wasm/');
const src = process.argv[2];
const wantType = process.argv[3] || 'TEXT';
const maxN = parseInt(process.argv[4] || '3', 10);

const libredwg = await LibreDwg.create(wasmDir);
const dwg = libredwg.dwg_read_data(fs.readFileSync(src), Dwg_File_Type.DWG);
const db = libredwg.convert(dwg);

let n = 0;
for (const e of db.entities || []) {
  if (e.type !== wantType) continue;
  console.log(JSON.stringify(e, (k, v) => (typeof v === 'number' ? Math.round(v * 1000) / 1000 : v), 1));
  if (++n >= maxN) break;
}
