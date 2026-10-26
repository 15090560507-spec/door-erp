const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { chromium } = require('playwright');

const baseUrl = process.env.RENDER_TEST_URL || 'http://127.0.0.1:3164';
const artifacts = process.env.QUOTE_TEST_ARTIFACTS;
const source = ts.createSourceFile('types.ts', fs.readFileSync(path.join(__dirname, '../src/lib/types.ts'), 'utf8'), ts.ScriptTarget.Latest, true);
let defaults;
source.forEachChild(node => {
  if (ts.isVariableStatement(node)) for (const declaration of node.declarationList.declarations) {
    if (declaration.name.getText(source) === 'DEFAULT_FORM_DATA') {
      defaults = new Function('localDateYmd', `return (${declaration.initializer.getText(source)})`)(() => '2026-10-26');
    }
  }
});
assert.ok(defaults);
const user = { uid: 'quote-browser', role: '管理员', name: 'Quote Browser', default_module: '图纸绘制', permissions: [] };
const baseParams = { ...defaults, dw: 1000, dh: 2000, dhdw: 'Outer Customer', gdmc: 'Exact Project',
  material: '0.8mm', zmks: '平板', fmks: '平板', ys: '测试色', mshd: '80', zmls: '标配拉手', fmls: '标配拉手',
  st_val: '连体锁', fingerprint_lock: '无', sel_hys: '可拆卸合页', sel_kx: '右开', sel_nk: '内开',
  has_outer: true, has_inner: true, trim_front_in: 150, trim_back_in: 100,
  trim_style_outer: '平包套', trim_style_inner: '平包套',
  overlap_front_lr: 0, overlap_front_top: 0, overlap_back_lr: 0, overlap_back_top: 0 };
const makeTask = (id, params) => ({ id, params, customer: params.dhdw, project: params.gdmc,
  status: '待绘制', door_type: '单门', size: `${params.dw} x ${params.dh}`, created_at: '2026-10-26', ref_text: '', ref_images: [], history: [] });
const tasks = new Map([
  ['outer-task', makeTask('outer-task', baseParams)],
  ['inner-task', makeTask('inner-task', { ...baseParams, dhdw: 'Inner Customer', trim_back_in: 300 })],
]);
const saved = new Map();
const metrics = params => {
  const side = (name, width) => {
    const w = params.dw + width * 2, h = params.dh + width;
    return { side: name, valid: true, error: '', outerBounds: { left: 0, bottom: 0, right: w, top: h, width: w, height: h },
      innerBounds: { left: 0, bottom: 0, right: params.dw, top: params.dh, width: params.dw, height: params.dh },
      outerArea: w * h / 1e6, innerArea: params.dw * params.dh / 1e6, baseArea: w * h / 1e6 - params.dw * params.dh / 1e6,
      quoteArea: w * h / 1e6 - params.dw * params.dh / 1e6, includedLintelArea: 0, lintelArea: 0 };
  };
  return { source: 'cad-trim-contour-v1', lintelTarget: 'none', outer: side('outer', params.trim_front_in), inner: side('inner', params.trim_back_in) };
};

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const errors = [], unexpected = [];
  let savedPayload, trimRequests = 0, newTasks = 0, paramSaves = 0, failNextSave = false, renderRequests = 0, previewRequests = 0;
  let previewDelay = 0, failPreview = false;
  const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII=';
  const previewSvg = process.env.CAD_PREVIEW_FIXTURE ? fs.readFileSync(process.env.CAD_PREVIEW_FIXTURE, 'utf8')
    : '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 5000 4000"><g data-cad-view="front"><rect x="100" y="100" width="900" height="2100" fill="none" stroke="blue"/><text x="100" y="2250">900</text></g><g data-cad-view="back"><rect x="2100" y="100" width="900" height="2100" fill="none" stroke="orange"/><text x="2100" y="2250">900</text></g></svg>';
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1100 } });
    await context.addCookies([{ name: 'auth_token', value: 'mock-quote-only', url: baseUrl }]);
    await context.addInitScript(user => {
      sessionStorage.setItem('door_token', 'mock-quote-only');
      sessionStorage.setItem('door_user', JSON.stringify(user));
      sessionStorage.setItem('door_module', '图纸绘制');
    }, user);
    await context.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url()), method = req.method();
      const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': '*' };
      const json = body => route.fulfill({ status: 200, headers, contentType: 'application/json', body: JSON.stringify(body) });
      if (method === 'OPTIONS') return route.fulfill({ status: 204, headers });
      if (url.pathname === '/api/auth/verify') return json(user);
      if (url.pathname === '/api/accessories') return json({ accessories: [{ id: 1, category: '制作材料', name: '0.8mm', unitPrice: 1480, unit: 'm2' }] });
      if (url.pathname === '/api/admin/dropdown-options') return json({});
      if (url.pathname === '/api/generate_cad_preview') {
        previewRequests++;
        assert.equal(url.searchParams.get('doors_only'), 'true');
        const body = req.postDataJSON(), failing = failPreview;
        if (previewDelay) await new Promise(resolve => setTimeout(resolve, previewDelay));
        if (failing) return route.fulfill({ status: 500, headers, contentType: 'application/json', body: JSON.stringify({ detail: 'Mock preview failed' }) });
        return route.fulfill({ status: 200, headers, contentType: 'image/svg+xml', body: previewSvg.replace('<svg ', `<svg data-request-width="${body.dw}" `) });
      }
      if (url.pathname === '/api/tasks/overview') return json({ total: tasks.size, customers: [], door_types: [], status_counts: {} });
      if (url.pathname === '/api/render/model-configs') return json({ configs: [{ id: 'mock-model', enabled: true, hasApiKey: true }] });
      if (url.pathname.startsWith('/api/render/line-art/tasks/')) {
        assert.ok(tasks.has(url.pathname.split('/').pop()));
        return json({ extraction: { front: { url: '/api/mock-line-art' } } });
      }
      if (url.pathname === '/api/mock-line-art') return route.fulfill({ status: 200, headers, contentType: 'image/png', body: Buffer.from(png, 'base64') });
      if (url.pathname === '/api/render/tasks' && method === 'POST') {
        renderRequests++;
        assert.match(req.postData(), /name="sourceTaskId"\r\n\r\nnew-1/);
        return json({ task: { id: 'mock-render', status: 'completed', images: [{ src: `data:image/png;base64,${png}` }] } });
      }
      if (url.pathname === '/api/render/tasks') return json({ tasks: [] });
      if (url.pathname === '/api/tasks' && method === 'GET') return json({ tasks: [...tasks.values()], total: tasks.size });
      if (url.pathname === '/api/tasks' && method === 'POST') {
        const body = req.postDataJSON();
        const task = makeTask(`new-${++newTasks}`, body.params);
        Object.assign(task, { ref_text: body.ref_text, ref_images: body.ref_images });
        tasks.set(task.id, task); return json(task);
      }
      if (url.pathname.startsWith('/api/tasks/')) {
        const id = decodeURIComponent(url.pathname.slice('/api/tasks/'.length));
        const task = tasks.get(id); assert.ok(task, id);
        if (method === 'PUT') {
          if (failNextSave) {
            failNextSave = false;
            return route.fulfill({ status: 500, headers, contentType: 'application/json', body: JSON.stringify({ detail: 'Mock save failed' }) });
          }
          const body = req.postDataJSON();
          if (body.params) paramSaves++;
          Object.assign(task, body);
        }
        return json(task);
      }
      if (url.pathname === '/api/quotes/trim-metrics') { trimRequests++; return json(metrics(req.postDataJSON())); }
      if (url.pathname.startsWith('/api/quotes/by-task/')) return json({ quote: saved.get(decodeURIComponent(url.pathname.slice('/api/quotes/by-task/'.length))) || null });
      if (url.pathname === '/api/quotes' && method === 'POST') {
        savedPayload = req.postDataJSON();
        const quote = { ...savedPayload, id: 41, items: savedPayload.doorGroups.flatMap(g => g.items) };
        saved.set(savedPayload.doorGroups[0].taskId, quote); return json({ quote });
      }
      if (url.pathname === '/api/accessories/remember-quote') return json({ remembered: 0 });
      unexpected.push(`${method} ${url.pathname}`); return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    const rows = () => page.locator('table').first().locator('tbody tr').filter({ has: page.locator('textarea') });
    const namedRow = async name => {
      const names = await rows().locator('textarea').evaluateAll(elements => elements.map(el => el.value));
      const index = names.findIndex(value => value.includes(name)); assert.ok(index >= 0, names.join('|'));
      return rows().nth(index);
    };
    const input = (row, column) => row.locator('td').nth(column).locator('input');
    const screenshot = async name => {
      if (!artifacts) return;
      fs.mkdirSync(artifacts, { recursive: true });
      await page.screenshot({ path: path.join(artifacts, name), fullPage: true });
    };
    await page.goto(`${baseUrl}/quote?taskId=outer-task`, { timeout: 120000 });
    await page.locator('textarea').filter({ hasText: '内门套（另计）' }).waitFor();
    assert.ok(await page.getByRole('heading', { name: '图纸识别', exact: true }).evaluate(el => Boolean(document.querySelector('#quote-preview-area').compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)));
    let main = await namedRow('单门'), extra = await namedRow('内门套');
    assert.equal(await input(main, 1).inputValue(), '1300');
    assert.equal(await input(main, 2).inputValue(), '2150');
    assert.equal(await input(extra, 5).inputValue(), '0.52');
    assert.equal(await input(extra, 6).inputValue(), '1036');
    await page.getByLabel('第1组另一侧门套系数', { exact: true }).fill('0.8');
    assert.equal(await input(extra, 6).inputValue(), '1184');
    await input(main, 6).fill('2000');
    assert.equal(await input(extra, 6).inputValue(), '1600');
    await page.getByRole('button', { name: '上移第 2 行', exact: true }).click();
    main = await namedRow('单门'); extra = await namedRow('内门套');
    await input(main, 6).fill('2500');
    assert.equal(await input(extra, 6).inputValue(), '2000');
    await input(extra, 6).fill('1875');
    assert.equal(await page.getByLabel('第1组另一侧门套系数', { exact: true }).inputValue(), '0.75');
    for (const quantity of ['3.7920', '123456.7890']) {
      await input(main, 5).fill(quantity);
      const cell = page.locator('[data-quote-quantity]').filter({ hasText: quantity }).first();
      await cell.waitFor();
      const fit = await cell.evaluate(el => {
        const span = el.querySelector('span'), style = getComputedStyle(el), box = span.getBoundingClientRect();
        return { whiteSpace: getComputedStyle(span).whiteSpace, width: box.width,
          available: el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
          oneLine: box.height <= parseFloat(getComputedStyle(span).fontSize) * 1.4 };
      });
      assert.equal(fit.whiteSpace, 'nowrap'); assert.ok(fit.width <= fit.available + 1, JSON.stringify(fit)); assert.ok(fit.oneLine);
    }
    await input(main, 5).fill('3.7920');
    await screenshot('outer-desktop.png');
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await page.getByRole('button', { name: '确认保存', exact: true }).click();
    await page.getByRole('heading', { name: '保存成功', exact: true }).waitFor();
    assert.equal(savedPayload.doorGroups[0].extraTrimFactor, .75);
    assert.equal(savedPayload.doorGroups[0].items[0].pricingRole, 'extraTrim');
    const beforeReload = trimRequests;
    await page.reload();
    await page.getByRole('button', { name: '更新报价', exact: true }).waitFor();
    assert.equal(trimRequests, beforeReload, 'history must not be silently repriced');
    assert.equal(await input(await namedRow('内门套'), 6).inputValue(), '1875');
    await page.goto(`${baseUrl}/quote?taskId=inner-task`);
    await page.locator('textarea').filter({ hasText: '外门套（另计）' }).waitFor();
    main = await namedRow('单门'); extra = await namedRow('外门套');
    assert.equal(await input(main, 1).inputValue(), '1600'); assert.equal(await input(main, 2).inputValue(), '2300');
    assert.equal(await input(extra, 5).inputValue(), '0.795');
    await screenshot('inner-desktop.png');
    await page.getByRole('button', { name: '门框面积 × 单价 + 门套面积 × 单价', exact: true }).click();
    await page.getByLabel('门套单价', { exact: true }).fill('500');
    await page.waitForFunction(() => [...document.querySelectorAll('textarea')].some(el => el.value === '外包套'));
    main = await namedRow('单门');
    assert.equal(await input(main, 1).inputValue(), '1000'); assert.equal(await input(main, 2).inputValue(), '2000');
    await page.waitForFunction(() => [...document.querySelectorAll('table')][0].querySelectorAll('tbody tr')[1]?.querySelectorAll('td')[6]?.querySelector('input')?.value === '500');
    assert.equal(await input(await namedRow('外包套'), 6).inputValue(), '500');
    assert.equal(await input(await namedRow('内包套'), 6).inputValue(), '500');
    assert.equal(await page.getByLabel('第1组另一侧门套系数', { exact: true }).count(), 0);
    await page.goto(`${baseUrl}/dashboard`);
    const outerTaskRow = page.locator('.task-list-row').filter({ hasText: 'Outer Customer' }).first();
    await outerTaskRow.getByRole('button', { name: '项目报价', exact: true }).waitFor();
    assert.deepEqual(await outerTaskRow.locator('.task-list-row__actions button').evaluateAll(els => els.map(el => el.getAttribute('aria-label'))), ['项目报价', '复制表单', '删除表单']);
    await outerTaskRow.getByRole('button', { name: '项目报价', exact: true }).click();
    await page.waitForURL('**/quote?taskId=outer-task');
    await page.getByRole('button', { name: '更新报价', exact: true }).waitFor();
    assert.equal(newTasks, 0);
    await page.goto(`${baseUrl}/dashboard`);
    await page.locator('.task-list-row__main').filter({ hasText: 'Outer Customer' }).first().click();
    await page.locator('.door-form').waitFor();
    const field = label => page.locator('.door-form label').filter({ hasText: new RegExp(`^\\s*\\*?${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*$`) }).first().locator('..').locator('input,select').first();
    const actions = () => page.locator('[data-drawing-actions]');
    const editActions = await actions().getByRole('button').allTextContents();
    const editFields = await page.locator('.door-form label').allTextContents();
    const buttonsStyle = await actions().getByRole('button').evaluateAll(els => els.map(el => ({ bg: getComputedStyle(el).backgroundColor, color: getComputedStyle(el).color, border: getComputedStyle(el).borderColor })));
    assert.ok(buttonsStyle.slice(0, 4).every(style => JSON.stringify(style) === JSON.stringify(buttonsStyle[0])));
    assert.notDeepEqual(buttonsStyle[4], buttonsStyle[0]);
    assert.equal(await page.locator('[data-cad-preview-panel]').count(), 0);
    await page.getByRole('button', { name: '预览 DXF', exact: true }).click();
    const panel = page.locator('[data-cad-preview-panel]');
    await panel.locator('[data-cad-preview-canvas] svg').waitFor();
    assert.equal(await panel.getByRole('button', { name: '生成预览', exact: true }).count(), 0);
    const checkFit = async (container, expectedSides) => {
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const fit = await container.locator('[data-cad-preview-canvas] svg').evaluate(svg => {
        const view = svg.viewBox.baseVal, scale = svg.getScreenCTM();
        const groups = [...svg.querySelectorAll('g[data-cad-view]')].filter(g => getComputedStyle(g).display !== 'none');
        const boxes = groups.map(g => g.getBBox());
        return { sides: groups.map(g => g.dataset.cadView), uniform: Math.abs(Math.abs(scale.a) - Math.abs(scale.d)) < .0001,
          fits: boxes.every(b => b.x >= view.x && b.y >= view.y && b.x + b.width <= view.x + view.width && b.y + b.height <= view.y + view.height),
          fill: Math.max((Math.max(...boxes.map(b => b.x + b.width)) - Math.min(...boxes.map(b => b.x))) / view.width,
            (Math.max(...boxes.map(b => b.y + b.height)) - Math.min(...boxes.map(b => b.y))) / view.height) };
      });
      assert.deepEqual(fit.sides, expectedSides); assert.ok(fit.uniform && fit.fits && fit.fill > .94, JSON.stringify(fit));
    };
    await checkFit(panel, ['front', 'back']);
    await panel.scrollIntoViewIfNeeded();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'cad-both-desktop.png') });
    await panel.getByRole('button', { name: '正面', exact: true }).click();
    await checkFit(panel, ['front']);
    await panel.getByRole('button', { name: '反面', exact: true }).click();
    await checkFit(panel, ['back']);
    assert.equal(previewRequests, 1, 'side switching must not regenerate CAD');
    await panel.getByRole('button', { name: '放大查看', exact: true }).click();
    const previewDialog = page.getByRole('dialog', { name: 'CAD 图纸预览', exact: true });
    await checkFit(previewDialog, ['back']);
    await previewDialog.getByRole('button', { name: '正面和反面', exact: true }).click();
    await checkFit(previewDialog, ['front', 'back']);
    await previewDialog.getByRole('button', { name: '关闭', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 1000 });
    await panel.scrollIntoViewIfNeeded();
    await checkFit(panel, ['front', 'back']);
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'cad-both-mobile.png') });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    await page.setViewportSize({ width: 1600, height: 1100 });
    await panel.getByRole('button', { name: '反面', exact: true }).click();
    await page.getByRole('button', { name: '预览 DXF', exact: true }).click();
    await panel.locator('[data-cad-preview-canvas] svg').waitFor();
    await checkFit(panel, ['front', 'back']);
    assert.equal(previewRequests, 2, 'a new preview defaults to both sides');
    await field('颜色').fill('Changed color');
    await page.getByRole('button', { name: '去报价', exact: true }).click();
    await page.getByRole('button', { name: '继续编辑', exact: true }).click();
    assert.ok(page.url().endsWith('/dashboard'));
    await page.getByRole('button', { name: '去报价', exact: true }).click();
    await page.getByRole('button', { name: '保存并报价', exact: true }).click();
    await page.waitForURL('**/quote?taskId=outer-task');
    await page.getByRole('button', { name: '更新报价', exact: true }).waitFor();
    assert.equal(tasks.get('outer-task').params.ys, 'Changed color'); assert.equal(paramSaves, 1);
    await page.goto(`${baseUrl}/dashboard`);
    await page.getByRole('button', { name: /新建任务/ }).click();
    await page.locator('.door-form').waitFor();
    for (const [label, value] of Object.entries({ '订货单位': 'New Customer', '颜色': '测试色', '门扇厚度(mm)': '80',
      '正面款式': '平板', '反面款式': '平板', '正面拉手': '标配拉手', '反面拉手': '标配拉手',
      '锁体类型': '连体锁', '指纹锁': '无', '开启机构': '可拆卸合页', '外包套款式': '平包套' })) await field(label).fill(value);
    await page.locator('.door-form').getByLabel('右开', { exact: true }).check();
    await page.locator('.door-form').getByLabel('内开', { exact: true }).check();
    assert.deepEqual(await actions().getByRole('button').allTextContents(), editActions);
    const entryFields = await page.locator('.door-form label').allTextContents();
    assert.deepEqual(entryFields, editFields.filter((label, i) => {
      const innerStart = editFields.indexOf('内包套');
      return i <= innerStart || i > innerStart + 4;
    }));
    assert.deepEqual(editActions, ['预览 DXF', '生成 DXF', '生成效果图', '去报价', '保存表单']);
    assert.equal(await page.locator('[data-cad-preview-panel]').count(), 0);
    await page.getByRole('button', { name: '去报价', exact: true }).click();
    await page.getByRole('heading', { name: '请先保存表单', exact: true }).waitFor();
    assert.equal(newTasks, 0);
    await page.getByRole('button', { name: '继续编辑', exact: true }).click();
    const note = page.getByPlaceholder('在此打字或粘贴沟通要求');
    await note.fill('Reference and customer notes stay after saving');
    await page.getByLabel('上传图片', { exact: true }).setInputFiles({ name: 'reference.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
    await page.getByText('已上传 1 张图片，点击/粘贴/拖拽追加', { exact: true }).waitFor();
    await page.getByRole('button', { name: '返回图纸绘制列表' }).click();
    await page.getByRole('button', { name: '继续编辑', exact: true }).click();
    await page.getByRole('button', { name: '保存表单', exact: true }).click();
    await page.getByRole('heading', { name: '保存成功', exact: true }).waitFor();
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    assert.ok(page.url().endsWith('/dashboard'));
    assert.equal(await field('订货单位').inputValue(), 'New Customer');
    assert.equal(await note.inputValue(), 'Reference and customer notes stay after saving');
    assert.deepEqual(tasks.get('new-1').ref_images, [png]);
    assert.equal(newTasks, 1);
    await field('颜色').fill('Updated entry color');
    failNextSave = true;
    await page.getByRole('button', { name: '保存表单', exact: true }).click();
    await page.getByText('Mock save failed', { exact: true }).waitFor();
    assert.equal(newTasks, 1);
    assert.notEqual(tasks.get('new-1').params.ys, 'Updated entry color');
    await page.getByRole('button', { name: '保存表单', exact: true }).click();
    await page.getByRole('heading', { name: '保存成功', exact: true }).waitFor();
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    assert.equal(tasks.get('new-1').params.ys, 'Updated entry color');
    assert.equal(tasks.get('new-1').ref_text, 'Reference and customer notes stay after saving');
    assert.equal(newTasks, 1, 'repeat saves must update the entry task');
    await page.getByRole('button', { name: '生成效果图', exact: true }).click();
    await page.getByAltText('快速生成效果图', { exact: true }).waitFor();
    assert.equal(renderRequests, 1);
    assert.equal(newTasks, 1, 'rendering must reuse the saved entry task');
    await page.setViewportSize({ width: 1600, height: 1100 });
    await actions().scrollIntoViewIfNeeded();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'entry-actions-desktop.png') });
    await page.setViewportSize({ width: 390, height: 1000 });
    await actions().scrollIntoViewIfNeeded();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'entry-actions-mobile.png') });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    const actionBoxes = await actions().getByRole('button').evaluateAll(elements => elements.map(el => {
      const rect = el.getBoundingClientRect(); return { top: rect.top, bottom: rect.bottom, fits: el.scrollWidth <= el.clientWidth };
    }));
    assert.ok(actionBoxes.every((box, i) => box.fits && (!i || box.top >= actionBoxes[i - 1].bottom)));
    await field('颜色').fill('Quote-confirmed entry');
    await page.getByRole('button', { name: '去报价', exact: true }).click();
    await page.getByRole('heading', { name: '请先保存表单', exact: true }).waitFor();
    assert.equal(tasks.get('new-1').params.ys, 'Updated entry color');
    await page.getByRole('button', { name: '保存并报价', exact: true }).click();
    await page.waitForURL('**/quote?taskId=new-1');
    await page.waitForFunction(() => document.querySelector('textarea')?.value.includes('单门'));
    assert.equal(newTasks, 1);
    assert.equal(tasks.get('new-1').params.ys, 'Quote-confirmed entry');
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.waitForTimeout(200);
    await screenshot('mobile.png');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    await page.setViewportSize({ width: 1600, height: 1100 });
    await page.goto(`${baseUrl}/dashboard`);
    await page.getByRole('button', { name: /新建任务/ }).click();
    for (const [label, value] of Object.entries({ '订货单位': 'Second Customer', '颜色': '测试色', '门扇厚度(mm)': '80',
      '正面款式': '平板', '反面款式': '平板', '正面拉手': '标配拉手', '反面拉手': '标配拉手',
      '锁体类型': '连体锁', '指纹锁': '无', '开启机构': '可拆卸合页', '外包套款式': '平包套' })) await field(label).fill(value);
    await page.locator('.door-form').getByLabel('右开', { exact: true }).check();
    await page.locator('.door-form').getByLabel('内开', { exact: true }).check();
    await page.getByRole('button', { name: '保存表单', exact: true }).click();
    await page.getByRole('heading', { name: '保存成功', exact: true }).waitFor();
    await page.getByRole('button', { name: '知道了', exact: true }).click();
    assert.equal(newTasks, 2);
    await page.getByRole('button', { name: '清空表单', exact: true }).click();
    assert.equal(await field('订货单位').inputValue(), '');
    assert.equal(tasks.get('new-2').params.dhdw, 'Second Customer');
    await page.getByRole('button', { name: '返回图纸绘制列表' }).click();
    await page.getByRole('button', { name: /新建任务/ }).waitFor();
    await page.setViewportSize({ width: 1920, height: 1100 });
    await page.locator('.task-list-row__main').filter({ hasText: 'Outer Customer' }).first().click();
    await page.locator('.door-form').waitFor();
    const dock = page.locator('[data-live-cad-preview]');
    await dock.getByRole('button', { name: '移动图纸小窗', exact: true }).waitFor();
    assert.equal(await dock.getByRole('switch', { name: '自动预览', exact: true }).isChecked(), false);
    assert.equal(await page.locator('[data-door-section="门板设置"]').evaluate(el => Boolean(el.closest('details'))), false);
    const columns = await page.locator('.door-form > div').evaluateAll(cols => cols.slice(0, 3).map(col => [...col.querySelectorAll(':scope > [data-door-section]')].map(el => el.dataset.doorSection)));
    assert.ok(columns[0].includes('五金锁具')); assert.ok(columns[2].includes('门板设置'));
    const placement = await page.locator('.drawing-form-workspace').evaluate(el => {
      const form = el.querySelector('.door-form').getBoundingClientRect(), workspace = el.getBoundingClientRect();
      const dock = document.querySelector('[data-live-cad-preview]');
      return { formWidth: form.width, workspaceWidth: workspace.width, position: getComputedStyle(dock).position, portaled: dock.parentElement === document.body };
    });
    assert.ok(Math.abs(placement.formWidth - placement.workspaceWidth) <= 1 && placement.position === 'fixed' && placement.portaled, JSON.stringify(placement));
    const drag = async (dx, dy) => {
      const handle = await dock.getByRole('button', { name: '移动图纸小窗', exact: true }).boundingBox();
      const x = handle.x + handle.width / 2, y = handle.y + handle.height / 2;
      await page.mouse.move(x, y); await page.mouse.down();
      await page.mouse.move(x + dx, y + dy, { steps: 8 }); await page.mouse.up();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    };
    const initialDock = await dock.boundingBox();
    await drag(-430, 150);
    const movedDock = await dock.boundingBox();
    assert.ok(Math.abs(movedDock.x - (initialDock.x - 430)) < 2 && Math.abs(movedDock.y - (initialDock.y + 150)) < 2);
    await drag(-3000, -2000);
    assert.ok((await dock.boundingBox()).x >= 8 && (await dock.boundingBox()).y >= 8);
    await dock.getByRole('button', { name: '移动图纸小窗', exact: true }).press('Shift+ArrowRight');
    assert.ok((await dock.boundingBox()).x >= 58);
    let bounds = await dock.boundingBox();
    await drag(1920 - bounds.width - 16 - bounds.x, 96 - bounds.y);
    const fixedBeforeScroll = await dock.boundingBox();
    await page.evaluate(() => window.scrollBy(0, 400));
    assert.ok(Math.abs((await dock.boundingBox()).y - fixedBeforeScroll.y) < 1);
    await dock.getByRole('button', { name: '收起小窗', exact: true }).click();
    assert.ok((await dock.boundingBox()).height < 100);
    await dock.getByRole('button', { name: '展开小窗', exact: true }).click();
    const beforeLive = previewRequests, beforeSaves = paramSaves;
    await page.waitForTimeout(1600); assert.equal(previewRequests, beforeLive);
    await dock.getByRole('switch', { name: '自动预览', exact: true }).check();
    const width = field('总宽(W)');
    await width.fill('1100'); await width.fill('1200'); await width.fill('1300');
    await page.waitForTimeout(600); assert.equal(previewRequests, beforeLive);
    await dock.locator('[data-cad-preview-canvas] svg').waitFor();
    assert.equal(previewRequests, beforeLive + 1);
    await field('订货单位').fill('Live preview only');
    await page.waitForTimeout(1700); assert.equal(previewRequests, beforeLive + 1);
    await dock.getByRole('switch', { name: '自动预览', exact: true }).uncheck();
    await width.fill('1350'); await page.waitForTimeout(1700); assert.equal(previewRequests, beforeLive + 1);
    await dock.getByRole('switch', { name: '自动预览', exact: true }).check();
    await page.waitForTimeout(1800); assert.equal(previewRequests, beforeLive + 2);
    const beforeMinimize = previewRequests;
    await dock.getByRole('button', { name: '收起小窗', exact: true }).click();
    await width.fill('1349'); await page.waitForTimeout(1700);
    assert.equal(previewRequests, beforeMinimize, 'minimized preview must not schedule automatic generation');
    await width.fill('1350');
    await dock.getByRole('button', { name: '展开小窗', exact: true }).click();
    await page.waitForTimeout(1700);
    assert.equal(previewRequests, beforeMinimize, 'restored known geometry reuses the cache');
    previewDelay = 1800;
    await width.fill('1360'); await page.waitForTimeout(1700);
    await width.fill('1370'); await page.waitForTimeout(1800);
    assert.equal(await dock.locator('[data-cad-preview-canvas] svg').getAttribute('data-request-width'), '1350', 'stale response must not replace the last successful preview');
    await page.waitForTimeout(2000);
    assert.equal(await dock.locator('[data-cad-preview-canvas] svg').getAttribute('data-request-width'), '1370');
    previewDelay = 0; failPreview = true;
    await width.fill('1380'); await dock.getByRole('alert').waitFor();
    assert.equal(await dock.locator('[data-cad-preview-canvas] svg').getAttribute('data-request-width'), '1370');
    failPreview = false;
    await dock.getByRole('button', { name: '刷新小窗', exact: true }).click();
    await page.waitForTimeout(150);
    assert.equal(await dock.locator('[data-cad-preview-canvas] svg').getAttribute('data-request-width'), '1380');
    assert.equal(paramSaves, beforeSaves, 'automatic preview must never save a form');
    await dock.getByRole('switch', { name: '自动预览', exact: true }).uncheck();
    await dock.getByRole('button', { name: '收起小窗', exact: true }).click();
    await field('正面门板样式').selectOption('四边对角线条');
    await dock.getByRole('button', { name: '展开小窗', exact: true }).click();
    await page.locator('.door-form').scrollIntoViewIfNeeded();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'three-column-desktop.png') });
    await drag(-180, 120);
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'floating-dragged-desktop.png') });
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.waitForTimeout(100);
    bounds = await dock.boundingBox();
    assert.ok(bounds.x >= 8 && bounds.y >= 8 && bounds.x + bounds.width <= 383 && bounds.y + bounds.height <= 993);
    const cdp = await context.newCDPSession(page);
    await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 1 });
    const touchHandle = await dock.getByRole('button', { name: '移动图纸小窗', exact: true }).boundingBox();
    const tx = touchHandle.x + 35, ty = touchHandle.y + touchHandle.height / 2;
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: tx, y: ty, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: tx - 20, y: ty + 100, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await page.waitForTimeout(100);
    assert.ok((await dock.boundingBox()).y > bounds.y + 70, 'touch must drag the floating window');
    await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: false });
    await cdp.detach();
    await dock.scrollIntoViewIfNeeded();
    if (artifacts) await page.screenshot({ path: path.join(artifacts, 'live-preview-mobile.png') });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth) <= 1);
    await page.setViewportSize({ width: 1920, height: 1100 });
    await page.getByRole('button', { name: /返回列表/ }).click();
    await page.getByRole('button', { name: '不保存离开', exact: true }).click();
    await page.locator('.task-list-row__main').filter({ hasText: 'Inner Customer' }).first().click();
    await page.locator('.door-form').waitFor();
    assert.equal(await dock.getByRole('switch', { name: '自动预览', exact: true }).isChecked(), false);
    assert.equal(await dock.locator('[data-cad-preview-canvas]').count(), 0);
    assert.deepEqual(errors, []); assert.deepEqual(unexpected, []);
    console.log(JSON.stringify({ largerSidePricing: true, factorEditing: true, reorderedLink: true, previewNoWrap: true,
      savedHistoryPreserved: true, splitModeUnchanged: true, unsavedCancelAndSave: true, matchingFormActions: true,
      entrySaveStays: true, repeatSaveUpdates: true, failedSaveRetry: true, entryRenderLinked: true,
      referencePreserved: true, clearStartsNewEntry: true, requestedPreviewOnly: true, sideSwitchWithoutRequests: true,
      previewFitWithoutDistortion: true, rowQuoteNavigation: true, explicitQuoteSave: true, recognitionAfterPreview: true,
      threeColumnBalanced: true, panelExpanded: true, floatingPreviewNoSpace: true, mouseAndTouchDrag: true,
      boundedOnResize: true, previewCollapse: true, livePreviewOptIn: true, debouncedLatestOnly: true,
      livePreviewFailureRetention: true, noAutoSave: true, newTaskSaved: newTasks, errors, unexpected }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
