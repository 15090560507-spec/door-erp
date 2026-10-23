import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const url = process.env.DISC_UI_URL || 'http://127.0.0.1:3133';
const output = process.env.DISC_ARTIFACT_DIR || 'F:/codex/disc-panel-verification';
await mkdir(output, { recursive: true });
const user = { uid: 'A', name: 'Disc test', role: '管理员', permissions: [], default_module: '图纸绘制' };
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
try {
  for (const width of [1440, 390]) {
    const task = { id: 'disc-test', customer: '圆盘验证', project: '三种款式', status: '待绘制',
      door_type: '子母门', size: '2200 x 2600 (门框)', date: '2026.10.23', history: [],
      params: { dhdw: '圆盘验证', gdmc: '三种款式', sl: '1', dw: 2200, dh: 2600, mother_door_width: 900,
        door_type: '子母门', product_name: '不锈钢镀铜门', ys: '测试色', mshd: 80,
        sel_kx: '右开', sel_nk: '内开', zmks: '平板', fmks: '平板', zmls: '标配拉手',
        fmls: '背包拉手', st_val: '连体锁', sel_hys: '合页', fingerprint_lock: '无',
        trim_style_outer: '平板', back_panel_same_as_front: false, child_back_same_as_front: false } };
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    await context.addCookies([{ name: 'auth_token', value: 'disc-test', url }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'disc-test');
      sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '图纸绘制');
    }, user);
    let saved;
    await context.route('**/api/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      let result = {};
      if (pathname.endsWith('/auth/verify')) result = user;
      else if (pathname.endsWith('/tasks/overview')) result = { total: 1, today_created: 1, status_counts: {}, trend: [], customers: [], door_types: [] };
      else if (pathname.endsWith('/tasks')) result = { tasks: [task], total: 1 };
      else if (pathname.endsWith('/tasks/disc-test')) {
        if (route.request().method() === 'PUT') {
          saved = route.request().postDataJSON();
          Object.assign(task, saved);
        }
        result = task;
      } else if (pathname.endsWith('/render/tasks')) result = { tasks: [] };
      else if (pathname.endsWith('/render/model-configs')) result = { configs: [] };
      else if (pathname.endsWith('/admin/dropdown-options')) result = { options: {} };
      await route.fulfill({ json: result });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${url}/dashboard`);
    await page.locator('.task-list-row__main').filter({ hasText: '圆盘验证' }).click();
    const details = page.locator('details').filter({ has: page.locator('summary').filter({ hasText: /^门板设置/ }) });
    await details.locator('summary').click();
    const panelStyle = title => details.locator('label').filter({ hasText: new RegExp(`^${title}样式$`) }).locator('..').locator('select');
    for (const title of ['正面门板', '反面门板', '子门正面', '子门反面']) {
      await panelStyle(title).selectOption('圆盘造型');
      await page.getByLabel(`${title}圆盘款式`, { exact: true }).selectOption('圆形牡丹花');
      assert.equal(await page.getByLabel(`${title}圆盘半径(mm)`, { exact: true }).inputValue(), '700');
      assert.equal(await page.getByLabel(`${title}圆盘外部填充`, { exact: true }).inputValue(), '竖条');
    }
    await page.getByLabel('正面门板圆盘款式', { exact: true }).selectOption('四叶草牡丹花');
    await page.getByLabel('正面门板圆心高度(mm)', { exact: true }).fill('1300');
    await page.getByLabel('正面门板圆盘外部填充', { exact: true }).selectOption('');
    await page.getByLabel('反面门板圆心高度(mm)', { exact: true }).fill('1250');
    await page.getByRole('button', { name: '反面门板恢复跟随拉手高度', exact: true }).click();
    assert.equal(await page.getByLabel('反面门板圆心高度(mm)', { exact: true }).inputValue(), '');
    await page.getByLabel('子门正面圆盘半径(mm)', { exact: true }).fill('250');
    await page.getByLabel('子门反面圆盘半径(mm)', { exact: true }).fill('300');
    await page.getByRole('button', { name: '保存修改', exact: true }).click();
    await page.getByText('修改已保存', { exact: true }).waitFor();
    assert.equal(saved.params.panel_disc_style, '四叶草牡丹花');
    assert.equal(saved.params.panel_disc_center_height, 1300);
    assert.equal(saved.params.panel_disc_outer_fill, '');
    assert.equal(saved.params.back_panel_disc_center_height, null);
    assert.equal(saved.params.child_panel_disc_radius, 250);
    assert.equal(saved.params.child_back_panel_disc_radius, 300);
    assert.equal(saved.status, undefined);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await page.getByLabel('正面门板圆盘款式', { exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, `controls-${width}.png`) });
    const fields = page.getByLabel('正面门板圆盘款式', { exact: true });
    assert.ok((await fields.boundingBox()).width > 100);
    await page.reload();
    await page.locator('.task-list-row__main').filter({ hasText: '圆盘验证' }).click();
    await details.locator('summary').click();
    assert.equal(await page.getByLabel('正面门板圆盘款式', { exact: true }).inputValue(), '四叶草牡丹花');
    assert.equal(await page.getByLabel('正面门板圆心高度(mm)', { exact: true }).inputValue(), '1300');
    assert.equal(await page.getByLabel('正面门板圆盘外部填充', { exact: true }).inputValue(), '');
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${width}px: four groups, subtype/radius/default fill, auto/manual height, save/reload, no workflow mutation`);
  }
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
  for (const stem of ['YXMDH', 'SBMDH']) {
    await page.setContent(await readFile(path.join(output, `${stem}.svg`), 'utf8'));
    await page.screenshot({ path: path.join(output, `${stem}-preview.png`), fullPage: true });
  }
  await page.close();
} finally { await browser.close(); }
