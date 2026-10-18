import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { renderQuoteArtifacts } from '../quote-template-pdf/src/exportArtifacts.mjs';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const baseURL = process.env.QUOTE_UI_URL || 'http://127.0.0.1:3123';
const output = process.env.QUOTE_UI_OUTPUT || path.join(tmpdir(), 'door-erp-quote-quantity');
await mkdir(output, { recursive: true });
const sample = {
  id: 147, customerName: '上海李帅', projectName: '惠农村', quoteDate: '2026-10-17',
  noticeText: '本报价不含税工厂结算价，不含木箱。',
  doorGroups: [{ groupName: '第1组门', doorQuantity: 2, taskId: 'same-spec', pricingMode: 'outerArea', trimUnitPrice: 0, items: [
    { productName: '对开门 不锈钢镀铜门 拼150mm竖条/平板', width: 2580, height: 2890, unit: 'm2', unitPrice: 1480, quantity: null, openDirection: '右内开', accessoryId: null },
    { productName: 'AF12指纹锁', width: null, height: null, unit: '套', unitPrice: 580, quantity: 1, openDirection: '', accessoryId: null },
  ] }],
};
sample.items = sample.doorGroups.flatMap(group => group.items);
const task = { id: 'same-spec', customer: '上海李帅', project: '惠农村', door_type: '对开门',
  size: '2300 x 2750 (门框)', status: '已通过', date: '2026.10.17', history: [],
  params: { dw: 2300, dh: 2750, has_outer: true, trim_front_in: 160, overlap_front_lr: 20, overlap_front_top: 20 },
};
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
try {
  for (const width of [1440, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    await context.addCookies([{ name: 'auth_token', value: 'ui-test-only', url: baseURL }]);
    const user = { uid: 'A', name: 'UI test', role: '管理员', permissions: [], default_module: '报价系统' };
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'ui-test-only'); sessionStorage.setItem('door_user', JSON.stringify(user));
    }, user);
    let saved = structuredClone(sample);
    let saves = 0;
    await context.route('**/api/**', async route => {
      const url = new URL(route.request().url());
      let result = {};
      if (url.pathname.endsWith('/auth/verify')) result = user;
      else if (url.pathname.endsWith('/sales-orders/candidates')) result = { candidates: [{
        task_id: task.id, customer_name: task.customer, project_name: task.project, product_name: '不锈钢镀铜门',
        door_type: task.door_type, width: 2300, height: 2750, opening_direction: '右内开', color: '紫铜',
        drawing_status: '已通过', approved_at: '2026-10-17', quote_status: '已报价', technical_details: {},
        quotes: [2, 3].map((count, index) => ({ quote_id: 147 + index, group_index: 0, group_name: '第1组门',
          door_quantity: count, quote_date: '2026-10-17', amount: 11615, items: sample.items })),
      }], total: 1, page: 1, page_size: 50 };
      else if (url.pathname.endsWith('/sales-orders/suggestions')) result = { customer_name: [], project_name: [], delivery_address: [], customer_phone: [], product_category: [] };
      else if (url.pathname.endsWith('/sales-orders')) result = { orders: [], total: 0 };
      else if (url.pathname.endsWith('/tasks')) result = { tasks: [task], total: 1 };
      else if (url.pathname.endsWith('/accessories')) result = { accessories: [] };
      else if (url.pathname.endsWith('/accessories/remember-quote')) result = { remembered: 0 };
      else if (url.pathname.endsWith('/quotes/147')) {
        if (route.request().method() === 'PUT') { saved = { ...route.request().postDataJSON(), id: 147 }; saves++; }
        result = { quote: saved };
      } else if (url.pathname.endsWith('/quotes')) result = { quotes: [saved], total: 1, offset: 0, limit: 50 };
      await route.fulfill({ json: result, headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${baseURL}/quote`);
    async function load() {
      await page.getByRole('button', { name: '报价历史', exact: true }).click();
      await page.getByRole('dialog', { name: '报价历史' }).getByRole('button').filter({ hasText: '#147' }).click();
      await page.getByRole('dialog', { name: '报价历史' }).waitFor({ state: 'hidden' });
      await page.waitForFunction(() => document.querySelector('[aria-label="第1组樘数"]')?.value === '2');
    }
    await load();
    const input = page.getByRole('spinbutton', { name: '第1组樘数', exact: true });
    assert.equal(await input.inputValue(), '2');
    const combo = page.getByRole('combobox').first();
    assert.match(await combo.inputValue(), /2580.*2890.*外围/);
    await combo.focus();
    await page.getByRole('option').filter({ hasText: '外围' }).waitFor();
    await combo.press('Escape');
    await page.getByRole('button', { name: '第1组增加一樘', exact: true }).click();
    await page.getByText('本组合计 ¥34,845', { exact: true }).waitFor();
    assert.match(await page.locator('#quote-preview-area').innerText(), /34845/);
    await input.fill('0');
    await page.getByRole('button', { name: '更新报价', exact: true }).click();
    await page.getByText('无法保存', { exact: true }).waitFor();
    assert.equal(saves, 0);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await input.fill('2');
    await page.getByRole('button', { name: '更新报价', exact: true }).click();
    await page.getByRole('dialog', { name: '请确认宽、高尺寸' }).getByText(/2 樘/).waitFor();
    await page.getByRole('button', { name: '确认保存', exact: true }).click();
    await page.getByText('更新成功', { exact: true }).waitFor();
    assert.equal(saved.doorGroups[0].doorQuantity, 2);
    assert.equal(saved.doorGroups[0].items[1].quantity, 1);
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    await load();
    assert.equal(await input.inputValue(), '2');
    await input.fill('1');
    assert(await page.getByRole('button', { name: '第1组减少一樘', exact: true }).isDisabled());
    await input.fill('2');
    await page.getByText('本组合计 ¥23,230', { exact: true }).waitFor();
    await input.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, `quantity-${width}.png`), fullPage: true });
    await input.locator('xpath=ancestor::section').screenshot({ path: path.join(output, `group-${width}.png`) });
    const bounds = await input.boundingBox();
    assert(bounds.x >= 0 && bounds.x + bounds.width <= width + 1);
    await page.goto(`${baseURL}/orders`);
    await page.getByRole('button', { name: '新建订单', exact: true }).first().click();
    const picker = page.getByRole('dialog', { name: '关联已终审图纸及对应报价单', exact: true });
    await picker.getByRole('checkbox').check();
    await picker.getByRole('button', { name: '加入订单', exact: true }).click();
    const orderQuantity = page.locator('.order-line-editor input[type="number"]');
    assert.equal(await orderQuantity.inputValue(), '2');
    await page.locator('.order-editor__totals .is-total').getByText('¥23,230', { exact: true }).waitFor();
    await orderQuantity.fill('4');
    await page.locator('.order-editor__totals .is-total').getByText('¥46,460', { exact: true }).waitFor();
    await page.locator('.order-line-editor select').selectOption('148:0');
    assert.equal(await orderQuantity.inputValue(), '3');
    await page.locator('.order-editor__totals .is-total').getByText('¥34,845', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${width}px: quantity, preview total, invalid count, save/reload, outer dimensions, order handoff and quote switching`);
  }
} finally { await browser.close(); }

const samplePath = path.join(output, 'quantity-quote.json');
await writeFile(samplePath, JSON.stringify(sample), 'utf8');
await renderQuoteArtifacts({ quotePath: samplePath, outputDir: output });
const html = await readFile(path.join(output, 'quote.html'), 'utf8');
assert.match(html, /23230/);
assert.match(html, /2 樘/);
assert.match(html, /单樘<br>用量/);
assert.match(html, /11615/);
console.log('PASS actual shared HTML, JPG and PDF generation: per-door items, two-door subtotal');
