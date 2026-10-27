const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const out = process.env.SECURITY_TEST_ARTIFACTS;
const catalog = [
  { key: 'payroll.read', label: '查看工资' }, { key: 'payroll.approve', label: '工资审核与锁定' },
  { key: 'payroll.unlock', label: '撤销工资审批/解锁' },
];
const entry = { id: 1, employee_no: 'E01', name: '员工一', team: '生产一组', base_salary: 5000, piecework_amount: 200,
  overtime_amount: 0, allowance: 0, bonus: 0, deduction: 0, social_insurance: 0, tax: 0, other_withholding: 0, payable_amount: 5200, remark: '' };
const summary = { id: 1, order_no: 'ORDER-1', customer: '测试客户', project: '测试项目', status: '已入库待发货', door_count: 1,
  completed_count: 0, progress: 100, door_units: [{ id: 10, order_id: 1, production_no: 'DOOR-10', product_name: '测试门', specification: '900x2100' }] };
const door = { id: 10, order_id: 1, production_no: 'DOOR-10', product_name: '测试门', specification: '900x2100',
  status: '已入库待发货', progress: 100, technical_package: { status: '已确认', version: 1 },
  sales_finance: { order_no: 'TM-1', total_amount: 1000, paid_amount: 100, unpaid_amount: 900 },
  exceptions: [], events: [], changes: [], supplies: [], inspections: [], inventory_movements: [], shipments: [], payroll_drafts: [],
  workflow: { current_stage: 'delivery', current_stage_label: '发货完成', open_exception_count: 0,
    stages: [{ key: 'delivery', label: '发货完成', state: 'blocked', summary: '待发货', blockers: [] }] } };

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [];
  async function scenario(user, status, perform) {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    let period = { id: 1, month: '2026-10', status, approved_by: 'A', entries: [entry], audit_events: [] };
    let assignment, shipment, transition, payrollReads = 0;
    let accounts = { A: { uid: 'A', name: '销售小A', role: '录入员', permissions: [] }, E: { uid: 'E', name: '普通账号', role: '录入员', permissions: ['payroll.read'] } };
    await context.addCookies([{ name: 'auth_token', value: 'mock-security', url: base }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'mock-security'); sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '任务总览');
    }, user);
    await context.route('**/api/**', async route => {
      const req = route.request(), p = new URL(req.url()).pathname, method = req.method();
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = body => route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (p === '/api/auth/verify') return json(user);
      if (p === '/api/operations/payroll') { payrollReads++; return json({ periods: [period] }); }
      if (p === '/api/operations/payroll/1/status') {
        transition = req.postDataJSON(); period = { ...period, status: transition.status, approved_by: transition.status === '草稿' ? '' : user.uid };
        return json({ period, message: '工资状态已更新' });
      }
      if (p === '/api/operations/payroll/1') return json({ period });
      if (p === '/api/operations/employees') return json({ employees: [{ id: 1, employee_no: 'E01', name: '员工一', is_active: true }] });
      if (p === '/api/operations/attendance') return json({ attendance: [] });
      if (p === '/api/business-access') return json({ catalog, users: accounts });
      if (p === '/api/business-access/E' && method === 'PUT') {
        assignment = req.postDataJSON(); accounts.E = { ...accounts.E, management_permissions: assignment.permissions, permissions: assignment.permissions };
        return json({ users: accounts, message: '经营权限已更新，后端立即生效' });
      }
      if (/\/business-access\/[^/]+\/history$/.test(p)) return json({ events: [] });
      if (p === '/api/tasks/overview') return json({ total: 0, today_created: 0, trend: [], customers: [], door_types: [], status_counts: {} });
      if (p === '/api/tasks') return json({ tasks: [], total: 0 });
      if (p === '/api/tasks/stats') return json({ status_counts: {} });
      if (p === '/api/admin/dropdown-options') return json({});
      if (p === '/api/fulfillment/dashboard') return json({ status_counts: {}, pending_release: 0, due_risks: 0, open_exceptions: 0 });
      if (p === '/api/fulfillment/pending-release') return json({ tasks: [] });
      if (p === '/api/fulfillment/people') return json({ people: [] });
      if (p === '/api/fulfillment/orders') return json({ orders: [summary] });
      if (p === '/api/fulfillment/orders/1') return json({ order: summary, door_unit: door });
      if (p === '/api/fulfillment/door-units/10/shipments') { shipment = req.postDataJSON(); return json({ door_unit: door, message: '发货已登记' }); }
      return json({});
    });
    const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
    try { await perform(page, () => ({ assignment, shipment, transition, payrollReads })); }
    finally { await context.close(); }
  }
  try {
    await scenario({ uid: 'A', role: '录入员', name: '销售小A', permissions: [] }, '已锁定', async (page, result) => {
      await page.goto(`${base}/payroll`); await page.getByLabel('工资期间').selectOption('1');
      await page.getByRole('button', { name: '解锁为草稿', exact: true }).click();
      const dialog = page.getByRole('dialog');
      assert.equal(await dialog.getByRole('button', { name: '确认', exact: true }).isEnabled(), false);
      await page.getByLabel('工资操作原因').fill('核对补贴后重新审核');
      await dialog.getByRole('button', { name: '确认', exact: true }).click();
      await page.getByText('工资状态已更新', { exact: true }).waitFor();
      assert.deepEqual(result().transition, { status: '草稿', reason: '核对补贴后重新审核', expected_status: '已锁定' });
      await page.getByRole('button', { name: '知道了' }).click();
      if (out) { fs.mkdirSync(out, { recursive: true }); await page.screenshot({ path: path.join(out, 'payroll-desktop.png') }); }
      await page.setViewportSize({ width: 390, height: 900 });
      await page.waitForTimeout(300);
      if (out) await page.screenshot({ path: path.join(out, 'payroll-mobile.png') });
      await page.setViewportSize({ width: 1600, height: 1000 });
      await page.goto(`${base}/dashboard`); await page.getByText('经营权限管理', { exact: true }).click();
      await page.getByLabel('权限账号').selectOption('E'); await page.getByLabel('工资审核与锁定', { exact: true }).check();
      await page.getByLabel('授权调整原因').fill('负责月度工资审核'); await page.getByRole('button', { name: '保存权限', exact: true }).click();
      await page.getByText('经营权限已更新，后端立即生效', { exact: true }).waitFor();
      assert.ok(result().assignment.permissions.includes('payroll.approve'));
      if (out) await page.screenshot({ path: path.join(out, 'permissions-desktop.png'), fullPage: false });
      await page.getByLabel('权限账号').selectOption('A');
      await page.getByText('超级管理员和销售小A固定保留全部经营管理权限。', { exact: true }).waitFor();
      await page.goto(`${base}/production`); await page.getByRole('button', { name: '选择订单 ORDER-1', exact: true }).click();
      await page.getByLabel('批准本次欠款发货').check();
      assert.equal(await page.getByRole('button', { name: '确认出库发货' }).isEnabled(), false);
      await page.getByLabel('欠款放行原因').fill('约定月末付款');
      await page.getByText('审批账号：销售小A（A）', { exact: true }).waitFor();
      assert.equal(await page.getByPlaceholder('授权人（放行时必填）').count(), 0);
      await page.getByRole('button', { name: '确认出库发货' }).click();
      await page.getByText('发货已登记', { exact: true }).waitFor();
      assert.equal(result().shipment.authorize_release, true); assert.equal('authorized_by' in result().shipment, false);
    });
    await scenario({ uid: 'F', role: '财务', name: '工资录入', permissions: ['payroll.read', 'payroll.write', 'personnel.read'] }, '已审批', async page => {
      await page.goto(`${base}/payroll`); await page.getByLabel('工资期间').selectOption('1'); await page.getByText('已审批 · 1 人', { exact: false }).waitFor();
      assert.equal(await page.getByRole('button', { name: '汇总计算' }).isEnabled(), false);
      assert.equal(await page.getByRole('button', { name: '保存', exact: true }).isEnabled(), false);
      assert.equal(await page.getByRole('button', { name: /解锁为草稿|撤销审批|审批通过/ }).count(), 0);
    });
    await scenario({ uid: 'R', role: '审核', name: '工资审核', permissions: ['payroll.read', 'payroll.approve', 'personnel.read'] }, '待审核', async page => {
      await page.goto(`${base}/payroll`); await page.getByLabel('工资期间').selectOption('1');
      await page.getByRole('button', { name: '审批通过' }).waitFor();
      assert.equal(await page.getByRole('button', { name: '汇总计算' }).count(), 0);
      assert.equal(await page.getByRole('button', { name: '保存', exact: true }).isEnabled(), false);
      await page.getByRole('button', { name: '退回草稿' }).click();
      assert.equal(await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).isEnabled(), false);
    });
    await scenario({ uid: 'E', role: '录入员', name: '普通录入', permissions: ['sales.read', 'production.read'] }, '草稿', async (page, result) => {
      await page.goto(`${base}/payroll`); await page.waitForURL('**/dashboard');
      assert.equal(result().payrollReads, 0); assert.equal(await page.getByText('经营权限管理', { exact: true }).count(), 0);
      assert.equal(await page.getByRole('link', { name: '工资管理', exact: true }).count(), 0);
    });
    await scenario({ uid: 'S', role: '发货员', name: '发货员', permissions: ['production.read', 'production.shipping'] }, '草稿', async page => {
      await page.goto(`${base}/production`); await page.getByRole('button', { name: '选择订单 ORDER-1', exact: true }).click();
      await page.getByRole('heading', { name: '发货与财务放行' }).waitFor();
      assert.equal(await page.getByLabel('批准本次欠款发货').count(), 0);
      assert.equal(await page.getByLabel('欠款放行原因').count(), 0);
    });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ aRetainsAll: true, permissionEditor: true, reasonedUnlock: true, approvedReadOnly: true,
      approverCannotEdit: true, blockedDirectPayrollURL: true, realShippingIdentity: true, ordinaryShipperCannotApprove: true, errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
