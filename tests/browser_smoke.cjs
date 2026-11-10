const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const path = require('node:path');
const fs = require('node:fs');
let preview;
let browser;
// Optional dev dependency: playwright. No application database is used.
const python = `
from tempfile import TemporaryDirectory
from pathlib import Path
from http.server import ThreadingHTTPServer
from lab.core import Lab
from lab.server import create_handler
with TemporaryDirectory(prefix="continuum-browser-") as folder:
    lab = Lab(Path(folder) / "test.sqlite")
    handler = create_handler(lab)
    handler.log_message = lambda *args: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    print("http://127.0.0.1:" + str(server.server_port), flush=True)
    server.serve_forever()
`;
(async()=>{
  preview=spawn(process.env.PYTHON || 'python3',['-u','-c',python],{cwd:path.resolve(__dirname,'..'),stdio:['ignore','pipe','inherit']});
  const baseURL=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error('Preview startup timed out')),10000);
    createInterface({input:preview.stdout}).once('line',line=>{clearTimeout(timer);resolve(line)});
    preview.once('error',reject);
    preview.once('exit',code=>{clearTimeout(timer);reject(new Error(`Preview exited: ${code}`))});
  });
  browser=await chromium.launch({headless:true});
  const output=process.env.CONTINUUM_SCREENSHOTS;
  if(output) fs.mkdirSync(output,{recursive:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(baseURL);
  await page.locator('#health').filter({hasText:'documentos'}).waitFor();
  assert.equal(await page.locator('.mast-brand .project-mark path').count()>0,true);
  for (const asset of ['/favicon.svg','/assets/continuum-symbol.svg','/assets/continuum-icons.svg']) {
    assert.equal((await page.request.get(baseURL+asset)).status(),200);
  }
  assert.equal(await page.locator('.nav .icon use').count(),4);
  // Main symbols are inline: hiding external image requests must not erase them.
  await page.route('**/assets/**',route=>route.abort());
  assert.equal(await page.locator('.mast-brand .project-mark').isVisible(),true);
  if(output) await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
  const query='Como preservar uma pergunta e sua evidência entre ambientes?';
  await page.locator('#query').fill(query);
  await page.reload();
  assert.equal(await page.locator('#query').inputValue(),query);
  await page.locator('#search-form button').click();
  await page.locator('#question-status').filter({hasText:'Pergunta preservada'}).waitFor();
  assert.equal(await page.locator('#query').inputValue(),query);
  await page.locator('.nav[data-view=trajetorias]').click();
  assert.equal(await page.locator('#current-view').innerText(),'Trajetórias');
  await page.locator('#node-list').filter({hasText:query}).waitFor();
  await page.locator('#node-list button').first().click();
  await page.locator('#trajectory-detail').filter({hasText:query}).waitFor();
  await page.locator('#brand').click();
  assert.equal(await page.locator('#query').inputValue(),query);
  await page.reload();
  await page.locator('#health').filter({hasText:'documentos'}).waitFor();
  await page.locator('#search-form button').click();
  await page.locator('#question-status').filter({hasText:'Pergunta preservada'}).waitFor();
  assert.equal((await (await page.request.get(baseURL+'/api/nodes')).json()).nodes.length,1);
  const failedQuery='Como retomar uma pergunta após falha de rede?';
  await page.route('**/api/investigations',route=>route.abort('failed'));
  await page.locator('#query').fill(failedQuery);
  await page.locator('#search-form button').click();
  await page.locator('#summary').filter({hasText:'tente novamente'}).waitFor();
  assert.equal(await page.locator('#query').inputValue(),failedQuery);
  assert.equal(await page.locator('#download').isDisabled(),true);
  await page.reload();
  assert.equal(await page.locator('#query').inputValue(),failedQuery);
  await page.unroute('**/api/investigations');
  await page.locator('#search-form button').click();
  await page.locator('#question-status').filter({hasText:'Pergunta preservada'}).waitFor();
  // Lost response: persist on server, drop reply, reload and retry with same UUID.
  const retryQuery='Como evitar duplicações quando a confirmação se perde?';
  await page.route('**/api/investigations',async route=>{
    await route.fetch();
    await route.abort('failed');
  });
  await page.locator('#query').fill(retryQuery);
  await page.locator('#search-form button').click();
  await page.locator('#summary').filter({hasText:'tente novamente'}).waitFor();
  await page.reload();
  await page.unroute('**/api/investigations');
  await page.locator('#search-form button').click();
  await page.locator('#question-status').filter({hasText:'Pergunta preservada'}).waitFor();
  const nodes=(await (await page.request.get(baseURL+'/api/nodes')).json()).nodes;
  assert.equal(nodes.filter(n=>n.body===retryQuery).length,1);
  for(const width of [1440,1024,768,390,320]){
    await page.setViewportSize({width,height:900});
    for(const view of ['explorar','trajetorias','fontes','laboratorio']){
      await page.locator(`.nav[data-view=${view}]`).click();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}/${view}: horizontal overflow`);
    }
  }
  await page.locator('.nav[data-view=explorar]').click();
  await page.setViewportSize({width:390,height:844});
  if(output) await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: branding assets, navigation, draft reload, submitted trajectory, network failure, lost response retry, no duplicates, five viewport widths, no JS errors');
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{
  if(browser) await browser.close();
  if(preview) preview.kill('SIGTERM');
});
