const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, request } = require('playwright');
const base = process.env.PATTERN_TEST_URL || 'http://127.0.0.1:3164';
const apiBase = process.env.PATTERN_API_URL || 'http://127.0.0.1:8164/api/';
const out = process.env.PATTERN_TEST_ARTIFACTS || 'F:/codex/reference-pattern-browser';
const image = fs.readFileSync(process.env.PATTERN_TEST_IMAGE || 'C:/Users/Administrator/AppData/Local/Temp/codex-clipboard-08095f9e-f9a2-4ee9-8eda-2dcc0a206744.png');
const rect = (x1,y1,x2,y2) => ({ points:[[x1,y1],[x2,y1],[x2,y2],[x1,y2]], closed:true });
const definition = { version:1, name:'测试回纹', stretch_x:[.35,.65], stretch_y:[.15,.85], warnings:['测试：请核对两侧各两条短线'],
  paths:[rect(0,0,1,1),rect(.16,.06,.84,.94),rect(0,0,.32,.12),rect(.68,0,1,.12),rect(0,.88,.32,1),rect(.68,.88,1,1),
    {points:[[0,.37],[.12,.37]],closed:false},{points:[[0,.64],[.12,.64]],closed:false},
    {points:[[.88,.37],[1,.37]],closed:false},{points:[[.88,.64],[1,.64]],closed:false}] };

(async () => {
  const api = await request.newContext({ baseURL: apiBase });
  const login = await (await api.post('login',{data:{uid:'admin',pwd:'local-options-2026'}})).json();
  assert.equal(login.success,true,JSON.stringify(login));
  const headers = {Authorization:`Bearer ${login.token}`};
  const customer = `参考图验收-${Date.now()}`;
  const params = {dhdw:customer,product_name:'不锈钢镀铜门',material:'0.8mm',ys:'2号色',mshd:80,dw:1930,dh:3060,door_type:'对开门',sel_kx:'右开',sel_nk:'内开',st_val:'连体锁',zmls:'无',fmls:'无',fingerprint_lock:'无',sel_hys:'暗合页',trim_style_outer:'平包套',door_panel_style:'H型布局',panel_b2_glass_style:'无线条',panel_middle_offset_z:100,back_panel_same_as_front:true,sel_qc:'玻璃',qc_shape:'矩形气窗',qc_height:550,qc_glass_style:'无线条'};
  Object.assign(params,{zmks:'平板',fmks:'平板',sl:'1 樘'});
  const created = await api.post('tasks',{headers,data:{params,ref_text:'',ref_images:[]}});
  assert.equal(created.status(),200,await created.text());
  const task = await created.json();
  const browser = await chromium.launch({headless:true,channel:'chrome'});
  let posts=0,complete=false,templateSaves=0,failPreview=false;
  const templates=[], errors=[];
  try {
    const context = await browser.newContext({viewport:{width:1600,height:1100}});
    await context.addCookies([{name:'auth_token',value:login.token,url:base}]);
    await context.addInitScript(({token,user})=>{if(!sessionStorage.getItem('door_token')){sessionStorage.setItem('door_token',token);sessionStorage.setItem('door_user',JSON.stringify(user));sessionStorage.setItem('door_module','图纸绘制');}},login);
    await context.route('**/api/reference-patterns/**',async route=>{
      const req=route.request(),p=new URL(req.url()).pathname;
      const cors={'access-control-allow-origin':'*','access-control-allow-headers':'*','access-control-allow-methods':'*'};
      const json=(body,status=200)=>route.fulfill({status,headers:cors,contentType:'application/json',body:JSON.stringify(body)});
      if(req.method()==='OPTIONS')return route.fulfill({status:204,headers:cors});
      if(p.endsWith('/connection'))return json({configured:true,model:'mock-vision-no-paid-call'});
      if(p.endsWith('/templates')){
        if(req.method()==='POST'){templateSaves++; const data=req.postDataJSON();templates.push({id:'template-1',...data});return json({template:templates.at(-1)},201);}
        return json({templates});
      }
      if(p.endsWith('/jobs')&&req.method()==='POST'){posts++;return json({job:{id:(posts===1?'a':'b').repeat(32),status:'queued',model:'mock-vision',definition:null,error:''}},202);}
      if(p.endsWith('/source'))return route.fulfill({headers:cors,contentType:'image/png',body:image});
      if(/\/jobs\/[ab]{32}$/.test(p))return json({job:{id:p.split('/').at(-1),status:complete?'completed':'running',model:'mock-vision',definition:complete?definition:null,error:''}});
      if(p.endsWith('/preview')){if(failPreview)return json({detail:'测试目标区域过小'},400);return route.continue();}
      throw Error(`Unexpected pattern route ${p}`);
    });
    const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
    page.on('dialog',dialog=>dialog.accept());
    await page.goto(`${base}/dashboard`,{timeout:120000});
    const openTask=async()=>{await page.locator('.task-list-row__main').filter({hasText:customer}).click();await page.locator('.door-form').waitFor();};
    await openTask();
    const panel=page.locator('[data-door-section="门板设置"]');
    await panel.getByRole('button',{name:'参考图识别',exact:true}).first().click();
    const modal=page.getByRole('dialog',{name:'正面门板B2 · 参考图识别',exact:true});
    await modal.getByLabel('选择参考图',{exact:true}).setInputFiles({name:'motif.png',mimeType:'image/png',buffer:image});
    await modal.locator('img').evaluate(img=>img.decode());
    const bounds=await modal.locator('img').boundingBox();
    await page.mouse.move(bounds.x+2,bounds.y+2);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width-2,bounds.y+bounds.height-2);await page.mouse.up();
    await modal.getByRole('button',{name:'识别线稿',exact:true}).click();
    await modal.getByText('正在识别，可关闭后从本栏查看结果',{exact:true}).waitFor();
    await modal.getByRole('button',{name:'关闭弹窗',exact:true}).click();
    const save=async()=>{const response=page.waitForResponse(res=>res.request().method()==='PUT'&&res.url().endsWith(`/api/tasks/${task.id}`));await page.getByRole('button',{name:'保存表单',exact:true}).click();assert.equal((await response).status(),200);await page.getByRole('dialog',{name:'保存成功',exact:true}).getByRole('button',{name:'知道了',exact:true}).click();};
    await save();
    let stored=await(await api.get(`tasks/${task.id}`,{headers})).json();
    assert.equal(stored.params.reference_pattern_jobs.panel_b2,'a'.repeat(32));
    complete=true;
    await page.reload();await openTask();
    await panel.getByRole('button',{name:'查看参考图识别',exact:true}).click();
    await modal.getByLabel('识别线稿预览',{exact:true}).waitFor();
    assert.equal(posts,1,'navigation must not resubmit AI');
    await modal.getByLabel('线宽(mm)',{exact:true}).fill('15');
    await modal.getByLabel('识别线稿预览',{exact:true}).waitFor();
    await modal.getByText('线条校正（10组）',{exact:true}).click();
    await modal.getByRole('button',{name:'添加横线',exact:true}).click();
    await modal.getByText('线条校正（11组）',{exact:true}).waitFor();
    await modal.getByLabel('识别线稿预览',{exact:true}).waitFor();
    await modal.locator('.viewport-dialog__body').evaluate(el=>{el.scrollTop=0;});
    if(out){fs.mkdirSync(out,{recursive:true});await page.screenshot({path:path.join(out,'desktop-b2.png')});}
    await page.setViewportSize({width:390,height:900});await page.waitForTimeout(100);
    assert.equal(await modal.evaluate(el=>el.scrollWidth>el.clientWidth+1),false);
    if(out)await page.screenshot({path:path.join(out,'mobile-b2.png')});
    await page.setViewportSize({width:1600,height:1100});
    await modal.getByLabel('我已核对线条和连接关系',{exact:true}).check();
    await modal.getByRole('button',{name:'仅应用到本樘门',exact:true}).click();
    await modal.waitFor({state:'detached'});assert.equal(templateSaves,0);
    await save();stored=await(await api.get(`tasks/${task.id}`,{headers})).json();
    assert.equal(stored.params.reference_patterns.panel_b2.band_width,15);
    assert.equal(stored.params.reference_patterns.panel_b2.definition.paths.length,11);
    assert.equal(stored.params.panel_b2_glass_style,'参考图线稿');
    await panel.getByRole('button',{name:'参考图识别',exact:true}).first().click();
    await modal.getByText('线条校正（11组）',{exact:true}).waitFor();
    assert.equal(posts,1,'reopening applied geometry must not call AI');
    await modal.getByRole('button',{name:'关闭弹窗',exact:true}).click();
    const structure=page.locator('[data-door-section="结构与开向"]');
    await structure.getByRole('button',{name:'参考图识别',exact:true}).click();
    const transom=page.getByRole('dialog',{name:'矩形气窗 · 参考图识别',exact:true});
    await transom.getByLabel('B2或气窗参考图上传区',{exact:true}).evaluate((el,bytes)=>{const dt=new DataTransfer();dt.items.add(new File([new Uint8Array(bytes)],'pasted.png',{type:'image/png'}));el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true}));},Array.from(image));
    await transom.locator('img').evaluate(img=>img.decode());
    await transom.getByRole('button',{name:'识别线稿',exact:true}).click();
    await transom.getByLabel('识别线稿预览',{exact:true}).waitFor();
    failPreview=true;await transom.getByLabel('试配高(mm)',{exact:true}).fill('80');
    await transom.getByRole('alert').filter({hasText:'测试目标区域过小'}).first().waitFor();
    assert.equal(await transom.getByRole('button',{name:'仅应用到本樘门'}).isDisabled(),true);
    failPreview=false;await transom.getByLabel('试配高(mm)',{exact:true}).fill('400');
    await transom.getByLabel('识别线稿预览',{exact:true}).waitFor();
    await transom.getByLabel('我已核对线条和连接关系',{exact:true}).check();
    await transom.getByLabel('模板名称（另存时填写）',{exact:true}).fill('气窗回纹测试');
    await transom.getByRole('button',{name:'应用并保存模板',exact:true}).click();
    await transom.waitFor({state:'detached'});assert.equal(templateSaves,1);assert.equal(posts,2);
    await save();stored=await(await api.get(`tasks/${task.id}`,{headers})).json();
    assert.equal(stored.params.qc_glass_style,'参考图线稿');assert.equal(stored.params.reference_patterns.transom.reviewed,true);
    const generated=await api.post('generate_cad',{headers,data:stored.params,timeout:120000});
    assert.equal(generated.status(),200,await generated.text());
    fs.writeFileSync(path.join(out,'reference-b2-and-transom.dxf'),await generated.body());
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({taskId:task.id,AIRequests:posts,templateSaves,optionalSaving:true,paste:true,crop:true,recovery:true,actualDxf:true,mobileOverflow:false,errors}));
    await context.close();
  } finally {await browser.close();await api.dispose();}
})().catch(error=>{console.error(error);process.exitCode=1;});
