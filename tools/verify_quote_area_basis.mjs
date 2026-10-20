import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { renderQuoteArtifacts } from '../quote-template-pdf/src/exportArtifacts.mjs';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const baseURL = process.env.QUOTE_UI_URL || 'http://127.0.0.1:3123';
const output = process.env.QUOTE_UI_OUTPUT || path.join(tmpdir(), 'door-erp-quote-area-basis');
await mkdir(output, { recursive: true });
const user = { uid: 'A', name: 'Area test', role: '管理员', permissions: [], default_module: '报价系统' };
const task = { id: 'quote-area', customer: '面积回归', project: '一楼', door_type: '单门',
  size: '870 x 2270 (门框)', status: '已通过', date: '2026.10.20', history: [],
  params: { dw: 870, dh: 2270, has_outer: true, trim_front_in: 60, overlap_front_lr: 20,
    overlap_front_top: 20, door_type: '单门', material: '0.8mm', product_name: '不锈钢镀铜门',
    zmks: '拼100mm竖条/平板', fmks: '平板', dhdw: '面积回归', gdmc: '一楼',
    dhrq: '2026.10.20', sel_kx: '左开', sel_nk: '内开' },
};
const emptyTrim = { valid: true, error: '', outerBounds: null, innerBounds: null,
  outerArea: 0, innerArea: 0, baseArea: 0, lintelArea: 0, includedLintelArea: 0, quoteArea: 0 };
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
let exportQuote;
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    await context.addCookies([{ name: 'auth_token', value: 'area-test', url: baseURL }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'area-test');
      sessionStorage.setItem('door_user', JSON.stringify(user));
    }, user);
    let saved;
    await context.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      let result = {};
      if (url.pathname.endsWith('/auth/verify')) result = user;
      else if (url.pathname.endsWith('/tasks')) result = { tasks: [task], total: 1 };
      else if (url.pathname.endsWith('/tasks/quote-area')) result = task;
      else if (url.pathname.endsWith('/accessories')) result = { accessories: [
        { id: 1, category: '制作材料', name: '0.8mm', unit: 'm2', unitPrice: 1480 },
      ] };
      else if (url.pathname.endsWith('/accessories/remember-quote')) result = { remembered: 0 };
      else if (url.pathname.endsWith('/quotes/trim-metrics')) result = {
        source: 'cad-trim-contour-v1', lintelTarget: 'none',
        outer: { ...emptyTrim, side: 'outer' }, inner: { ...emptyTrim, side: 'inner' },
      };
      else if (url.pathname.endsWith('/quotes/551')) {
        if (route.request().method() === 'PUT') saved = { ...route.request().postDataJSON(), id: 551 };
        result = { quote: saved };
      } else if (url.pathname.endsWith('/quotes')) {
        if (route.request().method() === 'POST') {
          saved = { ...route.request().postDataJSON(), id: 551 };
          result = { quote: saved };
        } else result = { quotes: saved ? [saved] : [], total: saved ? 1 : 0, offset: 0, limit: 50 };
      }
      await route.fulfill({ json: result, headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${baseURL}/quote`);
    const combo = page.getByRole('combobox').first();
    await combo.click();
    await page.getByRole('option').filter({ hasText: '870 x 2270' }).click();
    const section = page.locator('section').filter({ has: combo }).first();
    const row = section.locator('tbody tr').first();
    const numbers = row.locator('input[type="number"]');
    const quantity = numbers.nth(2);
    const count = page.getByRole('spinbutton', { name: '第1组樘数', exact: true });
    async function expectRow(w, h, area, amount) {
      await page.waitForFunction(({ w, h, area }) => {
        const row = document.querySelector('section tbody tr');
        const inputs = row?.querySelectorAll('input[type="number"]');
        return inputs?.[0]?.value === w && inputs?.[1]?.value === h && inputs?.[2]?.value === area;
      }, { w, h, area });
      await row.getByText(amount, { exact: true }).waitFor();
    }
    await expectRow('950', '2310', '2.1945', '3248');
    assert.match(await page.locator('#quote-preview-area').innerText(), /2\.1945/);
    await page.getByRole('button', { name: '门框面积 × 单价 + 门套面积 × 单价', exact: true }).click();
    await expectRow('870', '2270', '2', '2960');
    await page.getByRole('button', { name: '外围面积 × 单价', exact: true }).click();
    await expectRow('950', '2310', '2.1945', '3248');
    await count.fill('2');
    await page.getByText('本组合计 ¥6,496', { exact: true }).waitFor();
    await count.fill('1');
    await quantity.fill('2.35');
    await row.getByText('3478', { exact: true }).waitFor();
    await quantity.fill('');
    await expectRow('950', '2310', '2.1945', '3248');
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await page.getByRole('button', { name: '确认保存', exact: true }).click();
    await page.getByText('保存成功', { exact: true }).waitFor();
    assert.equal(saved.doorGroups[0].items[0].quantity, null);
    assert.equal(saved.doorGroups[0].items[0].width, 950);
    assert.equal(saved.doorGroups[0].items[0].height, 2310);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    async function reload() {
      await page.getByRole('button', { name: '报价历史', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '报价历史' });
      await dialog.getByRole('button').filter({ hasText: '#551' }).click();
      await dialog.waitFor({ state: 'hidden' });
    }
    await reload();
    await expectRow('950', '2310', '2.1945', '3248');
    saved.doorGroups[0].items[0].quantity = 2;
    saved.items[0].quantity = 2;
    await reload();
    await expectRow('950', '2310', '2', '2960');
    await quantity.fill('');
    await expectRow('950', '2310', '2.1945', '3248');
    await page.getByRole('button', { name: '更新报价', exact: true }).click();
    await page.getByRole('button', { name: '确认保存', exact: true }).click();
    await page.getByText('更新成功', { exact: true }).waitFor();
    assert.equal(saved.doorGroups[0].items[0].quantity, null);
    assert.equal(saved.doorGroups[0].items[0].unitPrice, 1480);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await reload();
    await expectRow('950', '2310', '2.1945', '3248');
    await quantity.scrollIntoViewIfNeeded();
    await section.screenshot({ path: path.join(output, `area-${width}.png`) });
    assert.deepEqual(errors, []);
    exportQuote = structuredClone(saved);
    exportQuote.items = exportQuote.doorGroups.flatMap(group => group.items);
    await context.close();
    console.log(`PASS ${width}px: screenshot quantity, mode switch, door count, manual override, save/reload and legacy correction`);
  }
} finally { await browser.close(); }
const quotePath = path.join(output, 'area-quote.json');
await writeFile(quotePath, JSON.stringify(exportQuote), 'utf8');
await renderQuoteArtifacts({ quotePath, outputDir: output });
const html = await readFile(path.join(output, 'quote.html'), 'utf8');
assert.match(html, /2\.1945/);
assert.match(html, /3248/);
console.log('PASS shared HTML/JPG/PDF export: area 2.1945 and amount 3248');
