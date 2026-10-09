import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';

const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const baseURL = process.env.QUOTE_UI_URL || 'http://127.0.0.1:3122';
const output = process.env.QUOTE_UI_OUTPUT || path.join(tmpdir(), 'door-erp-quote-history');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH });
try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport });
    await context.addCookies([{ name: 'auth_token', value: 'ui-test-only', url: baseURL }]);
    const user = { uid: 'ui-test', name: 'UI test', role: '\u7ba1\u7406\u5458', permissions: [], default_module: '\u62a5\u4ef7\u7cfb\u7edf' };
    await context.addInitScript((user) => {
      sessionStorage.setItem('door_token', 'ui-test-only');
      sessionStorage.setItem('door_user', JSON.stringify(user));
    }, user);
    let fail = false;
    let requests = [];
    let records = Array.from({ length: 121 }, (_, index) => ({
      id: 121 - index, customerName: index === 120 ? 'oldest' : `Customer ${121 - index}`,
      projectName: 'Project', quoteDate: '2026-10-09', doorSummary: 'Double door',
      doorWidth: 1394, doorHeight: 2470, doorCount: 2,
    }));
    await context.route('**/api/**', async (route) => {
      const url = new URL(route.request().url());
      const pathname = url.pathname;
      let result = {};
      let status = 200;
      if (pathname.endsWith('/auth/verify')) result = user;
      else if (pathname.endsWith('/tasks')) result = { tasks: [], total: 0 };
      else if (pathname.endsWith('/accessories')) result = { accessories: [] };
      else if (/\/quotes\/\d+$/.test(pathname) && route.request().method() === 'DELETE') {
        const id = Number(pathname.split('/').at(-1));
        records = records.filter((quote) => quote.id !== id);
      } else if (pathname.endsWith('/quotes')) {
        requests.push(Object.fromEntries(url.searchParams));
        if (fail) { status = 500; result = { detail: 'History load failed' }; }
        else {
          const offset = Number(url.searchParams.get('offset') || 0);
          const q = url.searchParams.get('q') || '';
          const matches = records.filter((quote) => `${quote.id} ${quote.customerName}`.includes(q));
          result = { quotes: matches.slice(offset, offset + 50), total: matches.length, offset, limit: 50 };
        }
      }
      await route.fulfill({ status, json: result, headers: { 'Access-Control-Allow-Origin': '*' } });
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${baseURL}/quote`);
    await page.getByRole('button', { name: '\u62a5\u4ef7\u5386\u53f2', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '\u62a5\u4ef7\u5386\u53f2' });
    await dialog.getByText('\u5171 121 \u6761\u8bb0\u5f55', { exact: false }).waitFor();
    await dialog.getByRole('checkbox', { name: '\u9009\u62e9\u62a5\u4ef7\u5355 #121', exact: true }).check();
    await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).click();
    await dialog.getByText('#71', { exact: true }).waitFor();
    assert.equal(await dialog.getByRole('checkbox', { checked: true }).count(), 0);
    assert.equal(requests.at(-1).offset, '50');
    await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).click();
    await dialog.getByText('#21', { exact: true }).waitFor();
    assert.equal(requests.at(-1).offset, '100');
    assert.equal(await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).isDisabled(), true);
    const search = dialog.getByRole('textbox', { name: '\u641c\u7d22\u62a5\u4ef7\u5386\u53f2' });
    await search.fill('oldest');
    await dialog.getByText('#1', { exact: true }).waitFor();
    assert.equal(requests.at(-1).q, 'oldest');
    assert.equal(requests.at(-1).offset, '0');
    await dialog.getByRole('button', { name: '\u6e05\u9664\u7b5b\u9009', exact: true }).click();
    await dialog.getByText('#121', { exact: true }).waitFor();
    // Clearing an already empty filter must still finish loading.
    await dialog.getByRole('button', { name: '\u6e05\u9664\u7b5b\u9009', exact: true }).click();
    await dialog.getByText('#121', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, `history-${viewport.width}.png`) });
    const bounds = await dialog.boundingBox();
    assert(bounds.x >= 0 && bounds.x + bounds.width <= viewport.width + 1);
    const next = await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).boundingBox();
    assert(next.y + next.height <= viewport.height + 1);
    fail = true;
    await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).click();
    await dialog.getByRole('alert').waitFor();
    assert.equal(await dialog.getByText('\u6682\u65e0\u62a5\u4ef7\u8bb0\u5f55').count(), 0);
    fail = false;
    await dialog.getByRole('button', { name: '\u91cd\u8bd5', exact: true }).click();
    await dialog.getByText('#71', { exact: true }).waitFor();
    // Delete the entire last page and verify a return to the previous page.
    await dialog.getByRole('button', { name: '\u4e0b\u4e00\u9875', exact: true }).click();
    await dialog.getByText('#21', { exact: true }).waitFor();
    await dialog.locator('label input[type=checkbox]').check();
    page.once('dialog', (confirm) => confirm.accept());
    await dialog.getByRole('button', { name: '\u6279\u91cf\u5220\u9664', exact: true }).click();
    await dialog.getByText('#71', { exact: true }).waitFor();
    await dialog.getByText('\u5171 100 \u6761\u8bb0\u5f55', { exact: false }).waitFor();
    assert.equal(requests.at(-1).offset, '50');
    assert.deepEqual(errors, []);
    console.log(`PASS quote history ${viewport.width}px: pagination, full search, selection, retry, deletion`);
    await context.close();
  }
} finally {
  await browser.close();
}
