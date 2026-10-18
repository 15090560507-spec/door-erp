import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const ts = require('typescript');
function load(name, dependencies = {}) {
  const source = readFileSync(new URL(`../frontend/src/lib/${name}.ts`, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: dependency => {
    if (!dependencies[dependency]) throw new Error(`Unexpected dependency ${dependency}`);
    return dependencies[dependency];
  } });
  return exports;
}
const quote = load('quoteTypes');
const areas = load('doorAreas');
const { taskProjectLabel } = load('taskProjectLabel', { './doorAreas': areas });
const { salesOrderChargeAmount } = load('salesOrderPricing');
const group = { doorQuantity: 2, items: [{ productName: 'Door', width: 2580, height: 2890, unit: 'm2', unitPrice: 1480 }, { productName: 'Lock', quantity: 1, unit: '套', unitPrice: 580 }] };
assert.equal(quote.quoteGroupUnitTotal(group), 11615);
assert.equal(quote.quoteGroupTotal(group), 23230);
assert.equal(quote.quoteDoorQuantity({}), 1);
assert.equal(quote.quoteDoorQuantity({ doorQuantity: 1.5 }), 0);
assert.equal(quote.quoteDoorQuantity({ doorQuantity: NaN }), 0);
assert.equal(group.items[1].quantity, 1);
const base = { dw: 2300, dh: 2750, has_outer: true, trim_front_in: 160, overlap_front_lr: 20, overlap_front_top: 20 };
const task = params => ({ customer: 'Customer', project: 'Project', size: '2300 x 2750 (门框)', params });
assert.match(taskProjectLabel(task(base)), /2580 × 2890 \(外围\)/);
assert(!taskProjectLabel(task({ ...base, has_outer: false })).includes('外围'));
assert(!taskProjectLabel(task({})).includes('外围'));
const landscape = { ...base, has_outer: false, has_outer_landscape: true, outer_landscape_left_width: 300, outer_landscape_right_width: 400, outer_landscape_top_height: 200, outer_landscape_left_overlap: 20, outer_landscape_right_overlap: 30, outer_landscape_top_overlap: 40 };
assert.match(taskProjectLabel(task(landscape)), /2950 × 2910/);
const clear = { ...base, dw: 0, dh: 0, use_light_size: true, light_w: 980, light_h: 2050, fw_left_str: '55/160', fw_right_str: '55/160', fw_top_str: '55/195', th_str: '55/55', sel_nk: '内开', sel_qc: '玻璃', qc_height: 350 };
assert.match(taskProjectLabel(task(clear)), /1580 × 2790/);
assert.equal(salesOrderChargeAmount({ source_type: 'quote', quantity: 5.04, unit_price: 1680, rounding_door_quantity: 2 }), 8468);
assert.equal(salesOrderChargeAmount({ source_type: 'quote', quantity: 5.04, unit_price: 1680 }), 8467);
console.log('PASS quote quantity, legacy defaults, outer/landscape/clear-opening-transom labels and order rounding');
