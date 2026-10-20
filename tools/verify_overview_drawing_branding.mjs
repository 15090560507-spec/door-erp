import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const baseURL = process.env.DRAWING_UI_URL || 'http://127.0.0.1:3123';
const output = process.env.DRAWING_UI_OUTPUT || path.join(tmpdir(), 'door-erp-overview-branding');
await mkdir(output, { recursive: true });
const user = { uid: 'A', name: 'Navigation test', role: '管理员', permissions: [], default_module: '任务总览' };
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
try {
  for (const width of [1440, 390]) {
    const tasks = ['待绘制', '已通过'].map((status, index) => ({
      id: `overview-${index}`, customer: `跳转验证${index}`, project: `原项目${index}`,
      door_type: '单门', size: '900 x 2100 (门框)', status, date: '2026.10.20', history: [],
      params: { dhdw: `跳转验证${index}`, gdmc: `原项目${index}`, dw: 900 + index * 100,
        dh: 2100, order_title: '浙江西州将军铜门订货单', door_type: '单门',
        sl: '1', product_name: '不锈钢镀铜门', ys: '测试色', mshd: 80,
        sel_kx: '左开', sel_nk: '内开', zmks: '平板', fmks: '平板',
        zmls: '标配拉手', fmls: '背包拉手', st_val: '连体锁', sel_hys: '合页',
        fingerprint_lock: '无', trim_style_outer: '平板' },
    }));
    const writes = [];
    const errors = [];
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    await context.addCookies([{ name: 'auth_token', value: 'navigation-test', url: baseURL }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'navigation-test');
      sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '任务总览');
    }, user);
    await context.route('**/api/**', async route => {
      const request = route.request();
      const url = new URL(request.url());
      let result = {};
      if (request.method() !== 'GET' && request.method() !== 'OPTIONS') writes.push({ path: url.pathname, method: request.method(), data: request.postDataJSON() });
      if (url.pathname.endsWith('/auth/verify')) result = user;
      else if (url.pathname.endsWith('/tasks/overview')) result = {
        total: 2, today_created: 2, status_counts: { '待绘制': 1, '已通过': 1 },
        trend: [], customers: [], door_types: [],
      };
      else if (url.pathname.endsWith('/tasks')) {
        const statuses = url.searchParams.get('status')?.split(',');
        const filtered = statuses ? tasks.filter(task => statuses.includes(task.status)) : tasks;
        result = { tasks: filtered, total: filtered.length };
      } else if (/\/tasks\/overview-\d$/.test(url.pathname)) {
        const task = tasks.find(task => url.pathname.endsWith(`/${task.id}`));
        if (request.method() === 'PUT') Object.assign(task, request.postDataJSON());
        result = task;
      } else if (url.pathname.endsWith('/render/tasks')) result = { tasks: [] };
      else if (url.pathname.endsWith('/render/model-configs')) result = { configs: [] };
      else if (url.pathname.endsWith('/admin/dropdown-options')) result = { options: {} };
      else if (url.pathname.endsWith('/users')) result = { users: {} };
      await route.fulfill({ json: result });
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.setDefaultTimeout(12000);
    await page.goto(`${baseURL}/dashboard`);
    const card = index => page.locator('[role="button"]').filter({ hasText: `跳转验证${index}` }).first();
    const field = label => page.locator('label').filter({ hasText: new RegExp(`^\\*?${label}$`) }).locator('..').locator('input').first();
    const nav = async name => {
      if (width < 700) await page.getByRole('button', { name: '打开导航', exact: true }).click();
      await page.getByRole('link', { name, exact: true }).click();
    };
    await card(0).getByTitle('点击切换为已报价').click();
    assert.equal(await page.getByRole('link', { name: '任务总览', exact: true }).getAttribute('aria-current'), 'page');
    assert.equal(writes.length, 1);
    assert.equal(writes[0].data.quote_status, '已报价');
    writes.length = 0;
    await card(0).getByTitle('点击切换为未报价').press('Enter');
    await page.waitForFunction(() => document.querySelector('[title="点击切换为已报价"]'));
    assert.equal(await page.getByRole('link', { name: '任务总览', exact: true }).getAttribute('aria-current'), 'page');
    assert.equal(writes.length, 1);
    assert.equal(writes[0].data.quote_status, '未报价');
    writes.length = 0;
    page.once('dialog', dialog => dialog.dismiss());
    await page.locator('.task-list-row').filter({ hasText: '跳转验证0' }).getByRole('button', { name: '删除表单', exact: true }).click();
    assert.deepEqual(writes, []);
    await card(0).click();
    await page.getByRole('button', { name: '预览 DXF', exact: true }).waitFor();
    assert.equal(await page.getByRole('link', { name: '图纸绘制', exact: true }).getAttribute('aria-current'), 'page');
    assert.equal(await field('订货单位').inputValue(), '跳转验证0');
    assert.equal(await field('项目名称').inputValue(), '原项目0');
    assert.deepEqual(writes, []);
    const title = field('订货单抬头');
    await title.click();
    await page.locator('li').filter({ hasText: /^众鼎门业$/ }).click();
    assert.equal(await title.inputValue(), '众鼎门业');
    await title.fill('自定义门业订货单');
    await title.press('Enter');
    await nav('任务总览');
    await page.getByRole('button', { name: '继续编辑', exact: true }).click();
    assert.equal(await title.inputValue(), '自定义门业订货单');
    await nav('任务总览');
    await page.getByRole('button', { name: '不保存离开', exact: true }).click();
    await card(1).focus();
    await card(1).press('Enter');
    await page.getByRole('button', { name: '预览 DXF', exact: true }).waitFor();
    assert.equal(await field('订货单位').inputValue(), '跳转验证1');
    assert.equal(tasks[1].status, '已通过');
    assert.deepEqual(writes, []);
    await title.click();
    await page.locator('li').filter({ hasText: /^众鼎门业$/ }).click();
    await page.getByRole('button', { name: '保存修改', exact: true }).click();
    await page.waitForFunction(() => document.body.innerText.includes('保存成功'));
    assert.equal(tasks[1].params.order_title, '众鼎门业');
    assert.equal(tasks[1].status, '已通过');
    assert.equal(writes.length, 1);
    assert.equal(writes[0].path.split('/').at(-1), 'overview-1');
    assert.equal(writes[0].data.status, undefined);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await title.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, `drawing-${width}.png`) });
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${width}px: same task, drawing actions, keyboard, presets/custom, unsaved guard, save without workflow changes`);
  }
} finally { await browser.close(); }
