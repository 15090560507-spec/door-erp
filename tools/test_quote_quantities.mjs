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
function quoteRowBuilder() {
  const source = readFileSync(new URL('../frontend/src/app/quote/page.tsx', import.meta.url), 'utf8');
  const ast = ts.createSourceFile('quote.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const functions = ast.statements.filter(node => ts.isFunctionDeclaration(node) && node.name?.text !== 'QuotePage')
    .map(node => node.getText(ast)).join('\n');
  const exports = {};
  const compiled = ts.transpileModule(`${functions}\nexport {buildQuoteRowsFromTask};`, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  vm.runInNewContext(compiled, { exports, ...quote, ...areas, DEFAULT_QUOTE_ROW_COUNT: 5 });
  return exports.buildQuoteRowsFromTask;
}
const build = quoteRowBuilder();
const screenshot = { dw: 870, dh: 2270, has_outer: true, trim_front_in: 60,
  overlap_front_lr: 20, overlap_front_top: 20, door_type: '单门' };
const outerRow = build(screenshot, [], 'outerArea', 0)[0];
assert.equal(outerRow.width, 950);
assert.equal(outerRow.height, 2310);
assert.equal(quote.quoteItemQuantityText(outerRow), '2.1945');
assert.equal(quote.quoteItemAmountText({ ...outerRow, unitPrice: 1480 }), '3248');
assert.equal(quote.quoteGroupTotal({ items: [{ ...outerRow, unitPrice: 1480 }], doorQuantity: 2 }), 6496);
const frameRow = build(screenshot, [], 'framePlusTrim', 0)[0];
assert.equal(frameRow.width, 870);
assert.equal(frameRow.height, 2270);
assert.equal(frameRow.quantity, 2);
assert.equal(quote.quoteItemQuantityText(build({ ...screenshot, dw: 800, dh: 2100 }, [], 'outerArea', 0)[0]), '2.0000');
assert.equal(quote.quoteItemQuantityText(build({ ...screenshot, dw: 1000, dh: 2000, has_outer: false }, [], 'outerArea', 0)[0]), '2.0000');
assert.equal(quote.quoteItemQuantityText({ ...outerRow, quantity: 2.35 }), '2.3500');
assert.equal(quote.quoteItemQuantityText(build({ ...screenshot, dw: 0, dh: 0, has_outer: false }, [], 'outerArea', 0)[0]), '');
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
console.log('PASS screenshot area basis, minimum-area boundaries, manual overrides, quote quantity, outer labels and order rounding');
