const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const out = process.env.PRODUCTION_TEST_ARTIFACTS;
const orders = [1, 2, 150].map(id => ({ id, order_no: `ORDER-${id}`, customer: `Customer ${id}`, project: 'Project',
  due_date: '2026-12-01', sales_note: '', status: '待生产确认', representative_status: '待生产确认', door_count: 1,
  completed_count: 0, progress: 0, door_units: [{ id: id * 10, order_id: id, production_no: `DOOR-${id * 10}`, product_name: 'Door', specification: '1000x2200' }] }));
const door = id => ({ id, order_id: id / 10, production_no: `DOOR-${id}`, product_name: 'Door', specification: '1000x2200',
  status: '待生产确认', progress: 0, order_no: `ORDER-${id / 10}`, technical_package: { version: 1, status: '草稿', components: [], work_packages: [] },
  exceptions: [], events: [], changes: [], supplies: [], inspections: [], inventory_movements: [], component_inventory: [], shipments: [], payroll_drafts: [], unfinished_work_packages: [],
  workflow: { current_stage: 'preparation', current_stage_label: '生产准备', open_exception_count: 0,
    stages: [{ key: 'preparation', label: '生产准备', state: 'blocked', summary: 'BOM', blockers: ['未发布'] }] } });
const bom = id => ({ id, door_unit_id: id, order_id: id / 10, order_no: `ORDER-${id / 10}`, customer: `Customer ${id / 10}`,
  production_no: `DOOR-${id}`, product_name: 'Door', specification: '1000x2200', due_date: '2026-12-01', version: 1, status: '草稿',
  frame_trim_mode: 'separate', rows: [], groups: [], warnings: [], version_history: [], publish_blockers: [],
  downstream_impact: { requirement_count: 0, supply_count: 0, work_package_count: 0 }, frame_status: { errors: [], warnings: [] } });

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [], unexpected = [], counts = new Map();
  let pendingDone = false, failSelection = false;
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    await context.addCookies([{ name: 'auth_token', value: 'mock-production', url: base }]);
    await context.addInitScript(() => {
      sessionStorage.setItem('door_token', 'mock-production');
      sessionStorage.setItem('door_user', JSON.stringify({ uid: 'A', name: 'Loading Test', role: '录入员', default_module: '图纸绘制', permissions: [] }));
      sessionStorage.setItem('door_module', '图纸绘制');
    });
    await context.route('**/api/**', async route => {
      const url = new URL(route.request().url()), p = url.pathname;
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
      counts.set(p, (counts.get(p) || 0) + 1);
      const json = body => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (p === '/api/auth/verify') return json({ uid: 'A', name: 'Loading Test', role: '录入员', default_module: '图纸绘制', permissions: [] });
      if (p === '/api/fulfillment/dashboard') { assert.equal(url.searchParams.get('include_pending'), 'false'); return json({ status_counts: {}, pending_release: 0, due_risks: 0, open_exceptions: 0 }); }
      if (p === '/api/fulfillment/pending-release') { await new Promise(r => setTimeout(r, 2000)); pendingDone = true; return json({ tasks: [] }); }
      if (p === '/api/fulfillment/people') return json({ people: [] });
      if (p === '/api/fulfillment/orders') return json({ orders });
      if (/\/api\/fulfillment\/orders\/\d+$/.test(p)) {
        assert.equal(url.searchParams.get('include_first_door'), 'true');
        const id = Number(p.split('/').pop());
        await new Promise(r => setTimeout(r, id === 1 ? 650 : 40));
        if (failSelection) return route.fulfill({ status: 500, headers, contentType: 'application/json', body: JSON.stringify({ detail: '模拟加载失败' }) });
        return json({ order: orders.find(order => order.id === id), door_unit: door(id * 10) });
      }
      if (/\/api\/bom\/door-units\/\d+$/.test(p)) return json({ bom: bom(Number(p.split('/').pop())) });
      if (p === '/api/inventory/materials') return json({ materials: [] });
      unexpected.push(p); return json({});
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/production`);
    const order = id => page.getByRole('button', { name: `选择订单 ORDER-${id}`, exact: true });
    await order(1).waitFor();
    assert.equal(pendingDone, false, 'slow pending/overview must not block the list');
    await order(1).click(); await order(2).click();
    await page.getByRole('heading', { name: 'DOOR-20', exact: true }).waitFor();
    await page.waitForTimeout(800);
    assert.equal(await order(2).getAttribute('aria-pressed'), 'true');
    assert.equal(await page.getByRole('heading', { name: 'DOOR-10', exact: true }).count(), 0);
    const beforeRepeat = counts.get('/api/fulfillment/orders/1');
    await order(1).click();
    await page.getByRole('heading', { name: 'DOOR-10', exact: true }).waitFor();
    assert.equal(counts.get('/api/fulfillment/orders/1'), beforeRepeat, 'repeat visit uses page-local cache');
    await order(150).click(); await page.getByRole('heading', { name: 'DOOR-1500', exact: true }).waitFor();
    assert.equal(counts.get('/api/bom/workbench') || 0, 0, 'embedded BOM must not select from first 100 global doors');
    assert.equal(counts.get('/api/fulfillment/door-units/1500') || 0, 0, 'first door arrives in the order response');
    const overviewCalls = counts.get('/api/fulfillment/dashboard'), listCalls = counts.get('/api/fulfillment/orders'), peopleCalls = counts.get('/api/fulfillment/people');
    const search = page.getByPlaceholder('单号、客户、项目、生产编号');
    await search.pressSequentially('Customer', { delay: 20 }); await page.waitForTimeout(500);
    assert.equal(counts.get('/api/fulfillment/orders'), listCalls + 1);
    assert.equal(counts.get('/api/fulfillment/dashboard'), overviewCalls);
    assert.equal(counts.get('/api/fulfillment/people'), peopleCalls);
    await search.fill(''); await page.waitForTimeout(200);
    const beforeRefresh = counts.get('/api/fulfillment/orders/150');
    await page.getByRole('button', { name: '刷新数据', exact: true }).click();
    await page.waitForTimeout(150);
    assert.equal(counts.get('/api/fulfillment/orders/150'), beforeRefresh + 1, 'refresh invalidates detail cache');
    failSelection = true;
    await order(2).click(); await page.getByText('模拟加载失败', { exact: true }).waitFor();
    await page.getByRole('button', { name: /知道了|确定/ }).click();
    failSelection = false;
    await order(2).click(); await page.getByRole('heading', { name: 'DOOR-20', exact: true }).waitFor();
    if (out) { fs.mkdirSync(out, { recursive: true }); await page.screenshot({ path: path.join(out, 'production-desktop.png') }); }
    await page.setViewportSize({ width: 390, height: 900 });
    const mobileOverflowPx = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    if (out) await page.screenshot({ path: path.join(out, 'production-mobile.png') });
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(JSON.stringify({ independentList: true, latestSelectionWins: true, combinedDetail: true, embeddedBomExactDoor: true,
      repeatCache: true, debouncedSearch: true, refreshInvalidates: true, failureRetry: true, mobileOverflowPx, errors, unexpected, requests: Object.fromEntries(counts) }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
