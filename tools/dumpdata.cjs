// Load plant-data.js as a browser-like global and dump JSON (also validates JS syntax).
const fs = require('fs');
const vm = require('vm');
const path = 'D:\\test\\src\\3d-powerplant\\plant-data.js';
const code = fs.readFileSync(path, 'utf8');
const sandbox = { console };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(code, sandbox, { filename: 'plant-data.js' });
const D = sandbox.PLANT_DATA;
if (!D) throw new Error('PLANT_DATA not exported');
fs.writeFileSync('D:\\test\\.dwgconv\\plant-data.json', JSON.stringify(D, null, 1), 'utf8');
const byCat = {};
for (const s of D.structures) byCat[s.cat] = (byCat[s.cat] || 0) + 1;
console.log('OK structures=' + D.structures.length, 'roads=' + D.roads.length,
  'trees=' + D.trees.length, 'boundary=' + D.boundary.length);
console.log('byCat', JSON.stringify(byCat));
console.log('shapes', JSON.stringify([...new Set(D.structures.map(s => s.shape))]));
