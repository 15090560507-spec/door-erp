const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const out = process.env.PURCHASE_TEST_ARTIFACTS;

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [], unexpected = [], writes = [];
  let failSave = false;
  const materials = [{ id: 1, code: 'LS-001', name: '标准拉手', specification: '300mm', unit: '付', reference_purchase_price: 8, can_purchase: 1, is_active: 1 },
    { id: 2, code: 'LS-002', name: '标准拉手', specification: '500mm', unit: '只', reference_purchase_price: 10, can_purchase: 1, is_active: 1 }];
  const suppliers = [{ id: 1, code: 'G01', name: '五金供应商甲', short_name: '甲', is_active: 1 }, { id: 2, code: 'G02', name: '五金供应商乙', is_active: 1 }];
  const supplies = [{ id: 1, material_id: 1, supplier_id: 1, tax_inclusive_price: 125, conversion_rate: 10 },
    { id: 2, material_id: 1, supplier_id: 2, tax_inclusive_price: 18, conversion_rate: 1 }];
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const user = { uid: 'A', name: '销售小A', role: '录入员', permissions: [], default_module: '任务总览' };
    await context.addCookies([{ name: 'auth_token', value: 'mock-purchase', url: base }]);
    await context.addInitScript(user => { sessionStorage.setItem('door_token', 'mock-purchase'); sessionStorage.setItem('door_user', JSON.stringify(user)); sessionStorage.setItem('door_module', '任务总览'); }, user);
    await context.route('**/api/**', async route => {
      const req = route.request(), p = new URL(req.url()).pathname;
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = (body, status = 200) => route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (p === '/api/auth/verify') return json(user);
      if (p === '/api/inventory/materials') return json({ materials });
      if (p === '/api/inventory/suppliers') return json({ suppliers });
      if (p === '/api/inventory/supplier-items') return json({ supplier_items: supplies });
      if (p === '/api/inventory/requirements') return json({ requirements: [] });
      if (p === '/api/inventory/purchasing/shortages') return json({ shortages: [] });
      if (p === '/api/inventory/receipts') return json({ receipts: [] });
      if (p === '/api/inventory/purchasing/orders' && req.method() === 'GET') return json({ orders: [] });
      if (p === '/api/inventory/purchasing/orders' && req.method() === 'POST') {
        writes.push(req.postDataJSON());
        return failSave ? json({ detail: '测试保存失败' }, 400) : json({ order: { id: 1 }, message: '采购草稿已保存' }, 201);
      }
      unexpected.push(`${req.method()} ${p}`); return json({});
    });
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
    await page.goto(`${base}/purchasing`);
    await page.getByRole('button', { name: '新建采购单', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '新建采购单' });
    await dialog.getByRole('combobox', { name: '供应商', exact: true }).waitFor();
    await dialog.getByRole('combobox', { name: '供应商', exact: true }).fill('临时新供应商');
    await dialog.getByRole('combobox', { name: '商品名称 1', exact: true }).fill('自由输入不建档测试');
    await dialog.getByRole('button', { name: '取消', exact: true }).click();
    assert.equal(writes.length, 0, 'cancel must not call any save endpoint');
    await page.getByRole('button', { name: '新建采购单', exact: true }).click();
    await dialog.getByRole('combobox', { name: '供应商', exact: true }).fill('G01');
    await dialog.getByRole('option').filter({ hasText: '五金供应商甲' }).click();
    await dialog.getByRole('combobox', { name: '商品名称 1', exact: true }).fill('300');
    await dialog.getByRole('option').filter({ hasText: 'LS-001' }).click();
    assert.equal(await dialog.getByLabel('采购单价 1', { exact: true }).inputValue(), '12.5');
    assert.equal(await dialog.getByLabel('规格 1', { exact: true }).isDisabled(), true);
    await dialog.getByLabel('数量 1', { exact: true }).fill('2.5');
    await dialog.getByRole('combobox', { name: '供应商', exact: true }).fill('G02');
    await dialog.getByRole('option').filter({ hasText: '五金供应商乙' }).click();
    assert.equal(await dialog.getByLabel('采购单价 1', { exact: true }).inputValue(), '18');
    await dialog.getByLabel('采购单价 1', { exact: true }).fill('19.25');
    await dialog.getByRole('combobox', { name: '供应商', exact: true }).fill('G01');
    await dialog.getByRole('option').filter({ hasText: '五金供应商甲' }).click();
    assert.equal(await dialog.getByLabel('采购单价 1', { exact: true }).inputValue(), '19.25', 'manual price must survive supplier changes');
    await dialog.getByRole('button', { name: '添加物料' }).click();
    await dialog.getByRole('combobox', { name: '商品名称 2', exact: true }).fill('新型门锁');
    await dialog.getByLabel('规格 2', { exact: true }).fill('定制50');
    await dialog.getByLabel('单位 2', { exact: true }).fill('套');
    await dialog.getByLabel('数量 2', { exact: true }).fill('3');
    await dialog.getByLabel('采购单价 2', { exact: true }).fill('100');
    await page.keyboard.press('Tab');
    if (out) { fs.mkdirSync(out, { recursive: true }); await page.screenshot({ path: path.join(out, 'desktop.png'), fullPage: true }); }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(150);
    assert.equal(await dialog.evaluate(el => el.scrollWidth > el.clientWidth + 1), false, 'dialog horizontal overflow');
    if (out) await page.screenshot({ path: path.join(out, 'mobile.png'), fullPage: true });
    failSave = true;
    await dialog.getByRole('button', { name: '保存采购草稿', exact: true }).click();
    await dialog.getByRole('alert').filter({ hasText: '测试保存失败' }).waitFor();
    const requestKey = writes[0].request_key;
    assert.equal(writes[0].supplier_id, 1);
    assert.equal(writes[0].items[0].material_id, 1);
    assert.equal(writes[0].items[1].material_name, '新型门锁');
    assert.equal(writes[0].items[1].material_id, undefined);
    failSave = false;
    await dialog.getByRole('button', { name: '保存采购草稿', exact: true }).click();
    await dialog.waitFor({ state: 'detached' });
    assert.equal(writes[1].request_key, requestKey, 'unchanged retry uses same request key');
    await page.getByText('按需求合并采购（0 项需求）', { exact: true }).waitFor();
    assert.equal(await page.getByText('手工备库', { exact: true }).count(), 0);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log('PASS: cancel, catalog search, spec/unit lock, converted supplier price, manual override, free input, mobile, failure/retry, demand purchase separation');
    await context.close();
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
