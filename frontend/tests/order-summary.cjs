const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const out = process.env.ORDER_SUMMARY_ARTIFACTS;
const line = { id: 1, line_no: 1, line_code: 'TM260001-01', task_id: 'drawing-original-001', source_type: 'drawing',
  quote_id: 147, product_name: '不锈钢镀铜门', door_type: '对开门', width: 2500, height: 2100, opening_direction: '右开内开', color: '2号色',
  quantity: 1, unit: '樘', unit_price: 6726, amount: 6726, drawing_revision: 'frozen-revision-001', remark: '',
  technical_details: { trim_type: '斜包套', main_door_style: '平板', lock_type: '指纹锁 / 连体锁', handle: '标配拉手 / 标配拉手', hinge: '可拆卸合页', material: '0.8mm', item_remark: '' },
  drawing_snapshot: { params: { fmks: '反面平板', frame_process: '折弯骨架工艺', glass_spec: '10mm钢化超白玻璃', dw: 900, dh: 2100, zmks: '旧款式不应覆盖确认值' } } };
const order = { id: 1, order_no: 'TM260001', version: 3, updated_at: '2026-09-19T06:52:24.456637Z', order_date: '2026-09-17', customer_name: '象山新时代',
  project_name: '住宅入户门', customer_phone: '13800000000', product_category: '入户门', delivery_date: '2026-09-19',
  salesperson: '销售小A', delivery_address: '浙江省宁波市象山县住宅项目', status: 'fulfilling', provisioning_status: 'ready', fulfillment_order_id: 4,
  subtotal: 6726, discount_amount: 726, total_amount: 6000, paid_amount: 1000, unpaid_amount: 5000,
  lines: [line], charge_lines: [{ id: 1, source_type: 'quote', item_type: '主门', product_name: '对开门 0.8mm不锈钢镀铜门 平板', specification: '2780 × 2240 mm', quantity: 6.228, unit: 'm2', unit_price: 1080, amount: 6726 }],
  payment_nodes: [{ id: 1, name: '定金', due_amount: 3000, planned_date: '2026-09-18', paid_amount: 1000, status: 'partial' }, { id: 2, name: '发货款', due_amount: 3000, planned_date: '', status: 'pending' }],
  receipts: [{ id: 11, receipt_no: 'SK260001', receipt_date: '2026-09-18', payment_method: '银行转账', reference: 'BANK-123', allocation_amount: 1000, status: 'confirmed' }],
  attachments: [], remark: '' };
const long = { ...structuredClone(order), id: 2, order_no: 'TM260002', status: 'confirmed', provisioning_status: 'failed', provisioning_error: '供应事项创建失败，测试重试入口',
  customer_name: '浙江众鼎门业有限公司及杭州兰庭新贵门业联合项目客户', project_name: '非常长的项目名称用于检查大屏和窄屏中的换行及信息完整性',
  delivery_address: '浙江省杭州市某项目一期三号楼一单元地下车库入口及住宅主要通道，请到场后电话联系项目负责人确认卸货位置。',
  lines: [{ ...structuredClone(line), source_changed: true, technical_details: { ...line.technical_details, main_door_style: '四边对角线条及大面积内嵌铜雕图案，内部空间竖条填充，保留完整文字不截断', item_remark: '门套与门框分体，现场安装，外包边和门框焊接在一起。' } },
    { ...structuredClone(line), id: 2, line_no: 2, line_code: 'TM260002-02', source_type: 'manual', task_id: 'manual:2', product_name: '手工补充门樘', quantity: 2, technical_details: undefined, drawing_snapshot: { params: { fmks: '历史反面款式' } } }],
  charge_lines: [...order.charge_lines, { id: 2, product_name: '内门套与门楣加长定制款（包含不锈钢基层及表面装饰）', item_type: '门套', specification: '内外轮廓净面积，门套与主门分开核算', quantity: 0.7536, unit: 'm2', unit_price: 756, amount: 570, source_type: 'quote' },
    { id: 3, product_name: '面积小数精度检查', item_type: '主门', specification: '1600 × 2370 mm', quantity: 3.792, unit: 'm2', unit_price: 100, source_type: 'quote' }],
  attachments: [{ id: 21, category: 'door_drawing', original_name: '门樘正反面及安装说明图纸.pdf' }, { id: 22, category: 'customer_signed', original_name: '客户签字确认图.pdf' }],
  remark: '按确认后的技术快照生产，附件仅用于核对。' };
const draft = { ...structuredClone(order), id: 3, order_no: 'TM260003', status: 'draft', provisioning_status: 'not_started', receipts: [], lines: [{ ...line, line_code: 'TM260003-01', source_type: 'manual', task_id: 'manual:3', quote_id: null }] };
const orders = [order, long, draft];
const summaries = orders.map(row => ({ ...row, line_count: row.lines.length, door_count: row.lines.reduce((n, line) => n + line.quantity, 0),
  first_door_type: '对开门', first_width: 2500, first_height: 2100 }));

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [], unexpected = [], mutations = [];
  let failDownload = true;
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1100 }, acceptDownloads: true });
    const user = { uid: 'A', role: '录入员', name: '销售小A', permissions: [], default_module: '任务总览' };
    await context.addCookies([{ name: 'auth_token', value: 'mock-orders', url: base }]);
    await context.addInitScript(user => { sessionStorage.setItem('door_token', 'mock-orders'); sessionStorage.setItem('door_user', JSON.stringify(user)); sessionStorage.setItem('door_module', '任务总览'); }, user);
    await context.route('**/api/**', async route => {
      const req = route.request(), p = new URL(req.url()).pathname, method = req.method();
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = body => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (method !== 'GET') mutations.push(p);
      if (p === '/api/auth/verify') return json(user);
      if (p === '/api/sales-orders') return json({ orders: summaries, total: summaries.length });
      if (p === '/api/sales-orders/suggestions') return json({ customer_name: [], project_name: [], delivery_address: [], customer_phone: [], product_category: [] });
      if (p === '/api/sales-orders/receipt-candidates') return json({ orders: [order] });
      if (/\/sales-orders\/\d+\/attachments\/\d+\/file$/.test(p)) {
        if (failDownload) return route.fulfill({ status: 503, headers, contentType: 'application/json', body: JSON.stringify({ detail: '模拟附件下载失败' }) });
        return route.fulfill({ headers, contentType: 'application/pdf', body: '%PDF-1.4\n% test download\n' });
      }
      if (p === '/api/sales-orders/2/retry-provisioning') return json({ order: { ...long, provisioning_status: 'ready' }, message: '履约资料已重新生成' });
      const match = p.match(/^\/api\/sales-orders\/(\d+)$/);
      if (match) return json({ order: orders.find(row => row.id === Number(match[1])) });
      unexpected.push(p); return json({});
    });
    const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/orders`);
    const select = async no => { await page.locator('.order-list__item').filter({ hasText: no }).click(); await page.locator('.order-summary__header h2').filter({ hasText: no }).waitFor(); };
    const snapshot = async name => { if (out) { fs.mkdirSync(out, { recursive: true }); await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(100); await page.screenshot({ path: path.join(out, name), fullPage: true }); } };
    await select('TM260001');
    const expected = ['订单概况', '门樘明细', '价格明细', '收款信息', '图纸附件'];
    assert.deepEqual(await page.locator('.order-summary h3').allTextContents(), expected);
    assert.equal(await page.getByText('图纸快照补充', { exact: true }).count(), 0);
    assert.equal(await page.getByText('旧款式不应覆盖确认值', { exact: true }).count(), 0);
    for (const text of ['反面平板', '折弯骨架工艺', '10mm钢化超白玻璃']) await page.locator('.order-summary-line__technical').getByText(text, { exact: true }).waitFor();
    assert.equal(await page.locator('.order-summary-line__source').getAttribute('open'), null);
    await page.getByText('来源记录', { exact: true }).click(); await page.getByText('frozen-revision-001', { exact: true }).waitFor();
    await page.getByText('来源记录', { exact: true }).click();
    assert.equal(await page.locator('.order-attachments__group').count(), 0); await page.getByText('暂无图纸附件', { exact: true }).waitFor();
    const fonts = await page.locator('.order-summary').evaluate(el => ({ heading: getComputedStyle(el.querySelector('h3')).fontSize, title: getComputedStyle(el.querySelector('h4')).fontSize, value: getComputedStyle(el.querySelector('dd')).fontSize, label: getComputedStyle(el.querySelector('dt')).fontSize }));
    assert.deepEqual(fonts, { heading: '18px', title: '16px', value: '14px', label: '12px' });
    const row = page.locator('.order-summary__charge').first();
    const [name, spec, amount] = await Promise.all(['.order-summary__charge-name', '.order-summary__charge-spec', '.order-summary__charge-amount'].map(selector => row.locator(selector).boundingBox()));
    assert.ok(spec.x >= name.x + name.width); assert.ok(amount.x >= spec.x + spec.width);
    assert.ok(Math.abs(spec.y + spec.height / 2 - (amount.y + amount.height / 2)) < 2);
    const doorOverview = await page.locator('.order-summary-line__overview').boundingBox();
    const doorAmount = await page.locator('.order-summary-line__amount').boundingBox();
    assert.ok(doorOverview.x + doorOverview.width <= doorAmount.x);
    await snapshot('orders-desktop.png');
    await page.getByRole('button', { name: '登记收款', exact: true }).click(); await page.getByRole('dialog', { name: '登记实际收款' }).waitFor();
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
    await page.getByRole('button', { name: '冲销收款单 SK260001' }).click(); await page.getByRole('dialog', { name: '冲销实际收款' }).waitFor();
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
    await select('TM260002');
    await page.getByText('来源图纸已变化，请取消原订单并重新确认。', { exact: true }).waitFor();
    assert.equal(await page.locator('.order-summary-line').count(), 2);
    assert.equal(await page.locator('.order-attachments__group').count(), 2);
    assert.equal(await page.locator('.order-summary__charge').nth(2).getByText('3.792 m2 × ¥100', { exact: true }).count(), 1);
    assert.equal(await page.locator('.order-summary__charge').nth(2).getByText('¥379', { exact: true }).count(), 1);
    for (const [label, width, height] of [['4k', 3840, 2160], ['desktop-long', 1600, 1100], ['tablet', 1024, 1000], ['mobile', 390, 900]]) {
      await page.setViewportSize({ width, height }); await page.waitForTimeout(250);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      assert.ok(overflow <= 1, `${label} whole-page overflow ${overflow}`);
      const clipped = await page.locator('.order-summary dd,.order-summary h4,.order-summary__charge-name,.order-summary__charge-spec,.order-summary__totals strong').evaluateAll(elements => elements.filter(el => el.clientWidth && el.scrollWidth > el.clientWidth + 1).map(el => el.textContent));
      assert.deepEqual(clipped, [], `${label} clipped values`);
      await snapshot(`orders-${label}.png`);
    }
    await page.setViewportSize({ width: 1600, height: 1100 });
    const downloadButton = page.getByRole('button', { name: '下载 门樘正反面及安装说明图纸.pdf', exact: true });
    await downloadButton.click(); await page.locator('.order-attachment-summary__error').waitFor();
    assert.ok((await page.locator('.order-attachment-summary__error').textContent()).trim());
    failDownload = false;
    const downloaded = page.waitForEvent('download'); await downloadButton.click();
    assert.equal((await downloaded).suggestedFilename(), '门樘正反面及安装说明图纸.pdf');
    assert.equal(await page.locator('.order-attachment-summary__error').count(), 0);
    await page.getByRole('button', { name: '重新生成', exact: true }).click(); await page.getByText('履约资料已重新生成', { exact: true }).waitFor();
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await select('TM260003'); await page.getByRole('button', { name: '编辑订单', exact: true }).click(); await page.locator('.order-editor__header').getByRole('button', { name: '保存草稿', exact: true }).waitFor();
    assert.deepEqual(mutations, ['/api/sales-orders/2/retry-provisioning']);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(JSON.stringify({ sections: expected, fonts, centeredSpecifications: true, mergedSnapshotFacts: true, sourceHistoryPreserved: true,
      decimalsUnchanged: true, emptyAttachmentsCompact: true, downloadErrorRetry: true, receiptAndEditorCallbacks: true, responsiveWidths: [3840, 1600, 1024, 390], errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
