const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const base = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const artifacts = process.env.AI_CONFIG_TEST_ARTIFACTS;

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [];
  async function scenario(user, perform) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const state = { reads: 0, writes: [], readError: false, saveError: false, delay: 0 };
    await context.addCookies([{ name: 'auth_token', value: 'mock-ai-config', url: base }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'mock-ai-config');
      sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '报价系统');
    }, user);
    await context.route('**/api/**', async route => {
      const request = route.request(), url = new URL(request.url()), method = request.method();
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = (body, status = 200) => route.fulfill({ status, headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (url.pathname === '/api/auth/verify') return json(user);
      if (url.pathname === '/api/tasks') return json({ tasks: [], total: 0 });
      if (url.pathname === '/api/accessories') return json({ accessories: [] });
      if (url.pathname === '/api/ai-config') {
        if (method === 'POST') {
          state.writes.push(request.postDataJSON());
          if (state.saveError) return json({ detail: '权限不足' }, 403);
        } else {
          state.reads++;
          const failed = state.readError, delay = state.delay;
          if (delay) await new Promise(resolve => setTimeout(resolve, delay));
          if (failed) return json({ detail: '权限不足' }, 403);
        }
        return json({ config: { baseUrl: 'https://example.invalid', endpointPath: '/chat/completions',
          model: 'mock-vision', hasApiKey: true, prompt: '', updatedAt: '' } });
      }
      return json({});
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    try { await page.goto(`${base}/quote`); await page.getByText('报价明细', { exact: true }).waitFor(); await perform(page, state); }
    finally { await context.close(); }
  }
  try {
    await scenario({ uid: 'E', role: '录入员', name: '销售小A', permissions: [] }, async (page, state) => {
      assert.equal(await page.getByRole('button', { name: 'AI 模型配置', exact: true }).count(), 0);
      assert.equal(state.reads, 0); assert.equal(state.writes.length, 0);
    });
    await scenario({ uid: 'A', role: '录入员', name: '销售小A', permissions: [] }, async (page, state) => {
      state.readError = true;
      await page.getByRole('button', { name: 'AI 模型配置', exact: true }).click();
      await page.getByRole('alert').filter({ hasText: '权限不足' }).waitFor();
      assert.equal(await page.getByRole('alert').filter({ hasText: '权限不足' }).evaluate(el => getComputedStyle(el).color), 'rgb(201, 53, 49)');
      assert.equal(await page.getByRole('button', { name: '保存 AI 配置', exact: true }).isEnabled(), false);
      state.readError = false;
      await page.getByRole('button', { name: '重新读取', exact: true }).click();
      const url = page.getByLabel('Base URL', { exact: true });
      await url.waitFor();
      await page.waitForFunction(() => document.querySelector('input[placeholder="https://api.moonshot.cn/v1"]')?.value === 'https://example.invalid');
      assert.equal(await page.getByLabel('API Key', { exact: true }).inputValue(), '');
      await url.fill('https://api.deepseek.com');
      await page.getByLabel('模型名', { exact: true }).fill('deepseek-flash');
      state.saveError = true;
      await page.getByRole('button', { name: '保存 AI 配置', exact: true }).click();
      await page.getByRole('alert').filter({ hasText: '权限不足' }).waitFor();
      assert.equal(await page.getByRole('alert').filter({ hasText: '权限不足' }).evaluate(el => getComputedStyle(el).color), 'rgb(201, 53, 49)');
      assert.equal(await url.inputValue(), 'https://api.deepseek.com');
      if (artifacts) { fs.mkdirSync(artifacts, { recursive: true }); await page.screenshot({ path: path.join(artifacts, 'save-error-desktop.png') }); }
      await page.setViewportSize({ width: 390, height: 900 });
      await page.waitForTimeout(350);
      assert.equal(await page.locator('.ui-dialog').evaluate(el => el.scrollWidth > el.clientWidth + 1), false);
      if (artifacts) await page.screenshot({ path: path.join(artifacts, 'save-error-mobile.png') });
      state.saveError = false;
      assert.equal(state.writes[0].apiKey, '');
      await page.getByLabel('API Key', { exact: true }).fill('mock-not-real-key');
      await page.getByRole('button', { name: '保存 AI 配置', exact: true }).click();
      await page.getByRole('status').filter({ hasText: 'AI 配置已保存' }).waitFor();
      assert.equal(await page.getByRole('button', { name: '保存 AI 配置', exact: true }).isEnabled(), false);
      assert.equal(await page.getByLabel('API Key', { exact: true }).inputValue(), '');
      assert.equal(state.writes[1].apiKey, 'mock-not-real-key');
      assert.equal(state.writes[1].model, 'deepseek-flash');
      await page.getByRole('heading', { name: 'AI 模型配置', exact: true }).waitFor({ state: 'hidden' });
      state.delay = 600;
      await page.getByRole('button', { name: 'AI 模型配置', exact: true }).click();
      await page.getByRole('button', { name: '关闭', exact: true }).click();
      state.delay = 0;
      await page.getByRole('button', { name: 'AI 模型配置', exact: true }).click();
      await page.getByLabel('模型名', { exact: true }).fill('manual-edit');
      await page.waitForTimeout(900);
      assert.equal(await page.getByLabel('模型名', { exact: true }).inputValue(), 'manual-edit');
    });
    await scenario({ uid: 'root', role: '超级管理员', name: '管理员', permissions: [] }, async page => {
      await page.getByRole('button', { name: 'AI 模型配置', exact: true }).click();
      await page.getByLabel('模型名', { exact: true }).waitFor();
      await page.getByRole('button', { name: '保存 AI 配置', exact: true }).waitFor({ state: 'visible' });
    });
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ ordinaryHidden: true, accountA: true, superAdmin: true, readRetry: true, redErrors: true, staleReadSafe: true, mobileOverflow: false, inferenceCalls: 0, errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
