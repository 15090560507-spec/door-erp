const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

// All API requests are mocked, including task creation. No provider is contacted.
const baseUrl = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const artifactDir = process.env.RENDER_TEST_ARTIFACTS;
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
const user = { uid: 'render-test', name: 'Render Test', role: '管理员', default_module: '效果渲染', permissions: [] };
const config = {
  id: 'mock-model', name: 'Mock Model', provider: 'image2_proxy', model: 'mock-model',
  baseUrl: 'https://provider.invalid', endpoint: '/images/edits', apiType: 'openai_images_edits',
  defaultSize: 'original', timeoutSeconds: 180, enabled: true, hasApiKey: true,
};
const legacy = {
  id: 'legacy-precise', status: 'completed', modelConfigId: config.id, prompt: 'Legacy reference',
  size: '4k', count: 1, selectedAssetIds: [], renderMode: 'precise', sourceType: 'image', sourceSide: 'front',
  files: [{ role: 'line_art', url: '/api/mock/line.png', originalName: 'legacy-line.png', mimeType: 'image/png' }],
  referenceBindings: { panel: { assetIds: [], files: [{ url: '/api/mock/panel.png', originalName: 'legacy-panel.png', mimeType: 'image/png' }] } },
  segmentation: { id: 'legacy-regions', source: { url: '/api/mock/line.png' }, masks: {} },
  psdFile: { url: '/api/mock/legacy.psd', originalName: 'legacy.psd' }, psdStatus: 'completed',
  images: [{ id: 'legacy-image', src: '/api/mock/result.png' }],
  createdAt: '2026-10-21T01:00:00Z', finishedAt: '2026-10-21T01:01:00Z',
};

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const unexpected = [], submissions = [], errors = [];
  let tasks = [legacy];
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1100 } });
    await context.addCookies([{ name: 'auth_token', value: 'mock-only', url: baseUrl }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'mock-only');
      sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '效果渲染');
    }, user);
    await context.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url()), method = req.method();
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = body => route.fulfill({ status: 200, headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (url.pathname === '/api/auth/verify') return json(user);
      if (url.pathname === '/api/render/model-configs' && method === 'GET') return json({ configs: [config] });
      if (url.pathname === '/api/render/model-configs/mock-model' && method === 'PUT') return json({ config });
      if (url.pathname === '/api/tasks' && method === 'GET') return json({ tasks: [], total: 0 });
      if (url.pathname === '/api/render/tasks' && method === 'GET') return json({ tasks });
      if (url.pathname === '/api/render/tasks' && method === 'POST') {
        const body = req.postDataBuffer().toString('latin1');
        const field = name => body.match(new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)`))?.[1];
        assert.equal(field('renderMode'), 'quick');
        assert.equal(field('segmentationId'), '');
        assert.equal(field('count'), '1');
        assert.match(body, /name="lineArt"; filename=/);
        assert.match(body, /name="panelReferences"; filename=/);
        submissions.push({ mode: field('renderMode'), size: field('size') });
        const task = { ...legacy, id: `quick-${submissions.length}`, renderMode: 'quick', size: field('size'),
          segmentation: undefined, psdFile: null, psdStatus: 'not_requested', files: [], referenceBindings: {} };
        tasks = [task, legacy];
        return json({ task });
      }
      if (url.pathname.startsWith('/api/mock/') && url.pathname.endsWith('.png')) {
        return route.fulfill({ status: 200, headers, contentType: 'image/png', body: png });
      }
      if (url.pathname === '/api/mock/legacy.psd') {
        return route.fulfill({ status: 200, headers, contentType: 'application/octet-stream', body: 'mock-existing-psd' });
      }
      unexpected.push(`${method} ${url.pathname}`);
      return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${baseUrl}/render`, { timeout: 120000 });
    const generate = page.getByRole('button', { name: /^一键生成效果图/ });
    await generate.waitFor({ timeout: 120000 });
    assert.equal(await generate.count(), 1);
    const removed = /精准分区生成|精细分区生成|转为精准生成|重生成门|生成并下载 PSD|检查区域/;
    assert.equal(await page.getByRole('button', { name: removed }).count(), 0);
    await generate.click();
    await page.getByText('请先生成正面和反面线稿', { exact: true }).waitFor();
    await page.getByRole('button', { name: '直接上传线稿', exact: true }).click();
    await page.locator('input[type=file]').filter({ hasNot: page.locator('[multiple]') }).first().setInputFiles({ name: 'line.png', mimeType: 'image/png', buffer: png });
    await generate.click();
    await page.getByText('请为门扇款式选择或上传至少一张参考图', { exact: true }).waitFor();
    await page.locator('input[type=file][multiple]').first().setInputFiles({ name: 'reference.png', mimeType: 'image/png', buffer: png });
    const submit = async expectedSize => {
      const response = page.waitForResponse(r => r.url().includes('/api/render/tasks') && r.request().method() === 'POST');
      await generate.click();
      assert.equal((await response).status(), 200);
      await page.getByRole('heading', { name: '正在提交渲染任务' }).waitFor({ state: 'hidden' });
      assert.equal(submissions.at(-1).size, expectedSize);
      assert.equal(await page.getByRole('button', { name: removed }).count(), 0);
    };
    await submit('2k');
    assert.equal(await page.getByRole('button', { name: '下载分层 PSD', exact: true }).count(), 0);
    await page.getByLabel('输出清晰度').selectOption('4k');
    await submit('4k');
    const history = page.locator('div.rounded-lg').filter({ has: page.getByRole('button', { name: /completed.*历史分区/ }) }).last();
    await history.getByRole('button', { name: '查看', exact: true }).click();
    await page.getByText('legacy-line.png', { exact: true }).waitFor();
    await page.getByText('legacy-panel.png', { exact: true }).waitFor();
    const downloaded = page.waitForEvent('download');
    await page.getByRole('button', { name: '下载分层 PSD', exact: true }).click();
    assert.equal((await downloaded).suggestedFilename(), 'legacy.psd');
    await submit('4k');
    const saveScreenshot = async name => {
      if (!artifactDir) return;
      fs.mkdirSync(artifactDir, { recursive: true });
      const section = generate.locator('xpath=ancestor::section[1]');
      await section.screenshot({ path: path.join(artifactDir, name) });
    };
    await saveScreenshot('desktop.png');
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.waitForTimeout(200);
    await saveScreenshot('mobile.png');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    assert.deepEqual(errors, []);
    assert.deepEqual(unexpected, []);
    assert.deepEqual(submissions, [{ mode: 'quick', size: '2k' }, { mode: 'quick', size: '4k' }, { mode: 'quick', size: '4k' }]);
    console.log(JSON.stringify({ submissions, legacyRestored: true, existingPsdDownloaded: true, errors, unexpected }));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
