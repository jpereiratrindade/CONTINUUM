// Optional dev dependency: playwright. Uses its own temporary sources and SQLite.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const {spawn,spawnSync} = require('node:child_process');
const {createInterface} = require('node:readline');
const path = require('node:path');
const fs = require('node:fs');
let preview,browser;
const python=`
from tempfile import TemporaryDirectory
from pathlib import Path
from http.server import ThreadingHTTPServer
import json, threading
from lab.core import Lab
from lab.api import execute
from lab.server import create_handler
with TemporaryDirectory(prefix="continuum-browser-") as folder:
    lab=Lab(Path(folder)/"test.sqlite")
    for name in ("a","b"):
        source=Path(folder)/name;source.mkdir()
        (source/"creative.md").write_text("# Processo criativo " + name + "\\n\\nMemória e convergência no processo criativo contínuo entre ferramentas. Referências para continuar. <script>window.sourceExecuted=true</script>",encoding="utf-8")
        lab.register_source(str(source),"Pesquisa " + name)
    handler=create_handler(lab);handler.log_message=lambda *args:None
    server=ThreadingHTTPServer(("127.0.0.1",0),handler)
    def observe():
        while True:
            execute(lab,"scan",{},allow_writes=True)
            threading.Event().wait(.3)
    threading.Thread(target=observe,daemon=True).start()
    print(json.dumps({"url":"http://127.0.0.1:"+str(server.server_port),"file":str(Path(folder)/"a/creative.md"),"db":str(Path(folder)/"test.sqlite")}),flush=True)
    server.serve_forever()
`;
const waitSaved=page=>page.waitForFunction(()=>document.querySelector('#note-status')?.textContent==='Preservado');
(async()=>{
 preview=spawn(process.env.PYTHON||'python3',['-u','-c',python],{cwd:path.resolve(__dirname,'..'),stdio:['ignore','pipe','inherit']});
 const fixture=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('Preview startup timed out')),10000);
  createInterface({input:preview.stdout}).once('line',line=>{clearTimeout(timer);resolve(JSON.parse(line));});
  preview.once('error',reject);preview.once('exit',code=>{clearTimeout(timer);reject(Error(`Preview exited ${code}`));});
 });
 browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',dialog=>dialog.accept());
 const url=fixture.url;
 const post=async(route,data)=>{
  const response=await page.request.post(url+route,{data,headers:{'X-Lab-Intent':'user'}});
  assert.equal(response.status(),200,await response.text());return response.json();
 };
 await page.goto(url);await page.locator('#health').filter({hasText:'Memória local'}).waitFor();
 assert.equal(await page.locator('.mast-brand .project-mark path').count()>0,true);
 for(const asset of ['/favicon.svg','/assets/continuum-symbol.svg','/assets/continuum-icons.svg'])assert.equal((await page.request.get(url+asset)).status(),200);
 const intention='Como sustentar o processo criativo contínuo entre ferramentas com memória e convergência?';
 await page.locator('#query').fill(intention);await page.reload();
 assert.equal(await page.locator('#query').inputValue(),intention);
 await page.locator('#search-form button').click();
 await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator('#reference-title').innerText(),intention);
 const id=page.url().split('/').pop();
 let ref=await (await page.request.get(url+'/api/reference?id='+id)).json();
 assert.equal(ref.stale,false);assert.equal(ref.package.contributions.length,2);
 const firstVersion=ref.package.evidence.find(d=>d.path===fixture.file).version_event_id;
 const text='Quero aproximar conversa e escrita sem preencher formulários.\n\nPróximo movimento\nConfrontar esta ideia com uma referência e escrever um pequeno experimento.';
 await page.locator('#working-text').fill(text);await waitSaved(page);
 await page.reload();await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator('#working-text').inputValue(),text);
 assert.equal(await page.locator('#search-form').isVisible(),false);
 // Dismissal is remembered across reload, rather than repeatedly interrupting creation.
 const contribution=page.locator('.contribution').first();await contribution.locator('summary').click();
 const dismissed=await contribution.locator('[data-dismiss]').getAttribute('data-dismiss');
 await contribution.locator('[data-dismiss]').click();
 await page.waitForFunction(id=>!document.querySelector(`[data-dismiss="${id}"]`),dismissed);
 await page.reload();await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator(`[data-dismiss="${dismissed}"]`).count(),0);
 // Change an authorized source outside the app. Observer prepares a new reference package automatically.
 fs.writeFileSync(fixture.file,'# Processo criativo a\n\nMemória e convergência entre ferramentas. Contraponto novo: conexões excessivas podem interromper o processo criativo.');
 await page.waitForFunction(async({url,id,version})=>{
  const r=await fetch(url+'/api/reference?id='+id).then(r=>r.json());
  return r.package.evidence.some(d=>d.version_event_id!==version&&d.path.endsWith('/a/creative.md'));
 },{url,id,version:firstVersion});
 await page.waitForFunction(()=>document.querySelector('#reference-contributions')?.textContent.includes('Contraponto novo'),{},{timeout:20000});
 const old=await (await page.request.get(url+'/api/document-version?id='+firstVersion)).json();
 assert.equal(old.body.includes('Contraponto novo'),false);
 assert.equal(await page.locator('#working-text').inputValue(),text);
 const updated=page.locator('.contribution').filter({hasText:'Contraponto novo'});
 await updated.locator('summary').click();await updated.locator('[data-incorporate]').click();
 await waitSaved(page);
 assert.equal((await page.locator('#working-text').inputValue()).includes('snapshot '),true);
 assert.equal(await page.evaluate(()=>window.sourceExecuted),undefined);
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export-work').click()]);
 const downloaded=fs.readFileSync(await download.path(),'utf8');
 assert.equal(downloaded.includes('snapshot'),true);assert.equal(downloaded.includes(intention),true);
 // Simulate another tool editing the same reference; stale browser writes cannot silently overwrite it.
 ref=await (await page.request.get(url+'/api/reference?id='+id)).json();
 await post('/api/reference/note',{id,text:'Contribuição externa preservada.',revision:ref.note.revision});
 await page.locator('#working-text').fill('Meu texto concorrente precisa ser conciliado.');
 await page.locator('#note-conflict:not(.hidden)').waitFor();
 await page.reload();await page.locator('#note-conflict:not(.hidden)').waitFor();
 assert.equal(await page.locator('#working-text').inputValue(),'Meu texto concorrente precisa ser conciliado.');
 assert.equal(await page.locator('#remote-note').textContent(),'Contribuição externa preservada.');
 await page.locator('#resolve-note').click();await waitSaved(page);
 // Offline autosave keeps a local recovery copy even after reopening.
 await page.route('**/api/reference/note',route=>route.abort('failed'));
 const offline='Esboço durante falha de rede: preservar para continuar depois.';
 await page.locator('#working-text').fill(offline);
 await page.locator('#note-status').filter({hasText:'Pendente'}).waitFor();
 await page.reload();await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator('#working-text').inputValue(),offline);
 await page.unroute('**/api/reference/note');
 await page.locator('#working-text').fill(offline+' Recuperado.');await waitSaved(page);
 // A lost creation response can be retried without duplicating the intention.
 await page.locator('#new-idea').click();
 const retry='Uma associação criativa que não deve desaparecer com a resposta.';
 await page.locator('#query').fill(retry);
 await page.route('**/api/investigations',async route=>{await route.fetch();await route.abort('failed');});
 await page.locator('#search-form button').click();
 await page.locator('#question-status').filter({hasText:'tente novamente'}).waitFor();
 await page.reload();await page.locator('#search-form:not(.hidden)').waitFor();
 assert.equal(await page.locator('#query').inputValue(),retry);
 await page.unroute('**/api/investigations');
 await page.locator('#search-form button').click();
 await page.locator('#reference-title').filter({hasText:retry}).waitFor();
 const nodes=(await (await page.request.get(url+'/api/nodes')).json()).nodes;
 assert.equal(nodes.filter(n=>n.title===retry).length,1);
 await page.locator(`button[data-open-node="${id}"]`).first().click();
 await page.locator('#reference-title').filter({hasText:intention}).waitFor();
 // An assistant proposes through a real MCP subprocess; text stays intact until review.
 ref=await (await page.request.get(url+'/api/reference?id='+id)).json();
 const beforeProposal=ref.note.text;
 const proposalText='Uma proposta do Codex: experimentar uma conexão. <script>window.proposalExecuted=true</script>';
 const proposalId=require('node:crypto').randomUUID();
 const dismissedProposalId=require('node:crypto').randomUUID();
 const mcpMessages=[
  {jsonrpc:'2.0',id:1,method:'initialize',params:{protocolVersion:'2025-11-25',capabilities:{},clientInfo:{name:'codex-browser-test'}}},
  {jsonrpc:'2.0',method:'notifications/initialized'},
  ...[[proposalId,proposalText],[dismissedProposalId,'Outra possibilidade, que vou dispensar.']].map(([request_id,text],i)=>({jsonrpc:'2.0',id:i+2,method:'tools/call',params:{name:'propose_note',arguments:{id,text,revision:ref.note.revision,request_id}}}))
 ];
 const mcp=spawnSync(process.env.PYTHON||'python3',['-m','lab','--db',fixture.db,'mcp','--allow-writes'],{cwd:path.resolve(__dirname,'..'),input:mcpMessages.map(m=>JSON.stringify(m)+'\n').join(''),encoding:'utf8',timeout:10000});
 assert.equal(mcp.status,0,mcp.stderr);
 for(const line of mcp.stdout.trim().split('\n'))assert.equal(JSON.parse(line).result.isError||false,false);
 await page.reload();await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator('#working-text').inputValue(),beforeProposal);
 assert.equal((await page.locator('#note-origin').textContent()).includes('Navegador / API'),true);
 assert.equal((await page.locator('#context-state').textContent()).includes('Referências aproximadas'),true);
 const proposal=page.locator('.text-proposal').filter({hasText:'Uma proposta do Codex'});
 await proposal.locator('summary').click();
 assert.equal((await proposal.locator('.proposal-text').textContent()),proposalText);
 // The server commits incorporation but its response is lost: no duplicated addition.
 await page.route('**/api/reference/proposal/review',async route=>{await route.fetch();await route.abort('failed');});
 await proposal.locator('[data-accept-proposal]').click();
 await page.waitForFunction(text=>document.querySelector('#working-text').value.endsWith(text),proposalText);
 await page.unroute('**/api/reference/proposal/review');
 ref=await (await page.request.get(url+'/api/reference?id='+id)).json();
 assert.equal(ref.note.text,beforeProposal+'\n\n'+proposalText);
 assert.equal(ref.authorship.proposal.source_ref,'mcp:codex-browser-test');
 assert.equal((await page.locator('#note-origin').textContent()).includes('proposta de Codex'),true);
 const dismissedProposal=page.locator('.text-proposal').filter({hasText:'Outra possibilidade'});
 await dismissedProposal.locator('summary').click();await dismissedProposal.locator('[data-dismiss-proposal]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.text-proposal').length===0);
 await page.reload();await page.locator('#reference-workspace:not(.hidden)').waitFor();
 assert.equal(await page.locator('.text-proposal').count(),0);
 assert.equal(await page.evaluate(()=>window.proposalExecuted),undefined);
 await page.locator('#show-changes').click();
 await page.locator('#reference-history h4').first().waitFor({state:'attached'});
 const edit=page.locator('.history-event').filter({hasText:'Edição do texto'}).last();
 await edit.locator('summary').first().click();await edit.locator('h4').first().waitFor();
 assert.equal((await page.locator('#reference-history').textContent()).includes('Antes'),true);
 assert.equal((await page.locator('#reference-history').textContent()).includes('codex-browser-test'),true);
 await page.locator('.workspace-history > summary').click();
 const output=process.env.CONTINUUM_SCREENSHOTS;if(output)fs.mkdirSync(output,{recursive:true});
 if(output)await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
 for(const width of [1440,1024,768,390,320]){
  await page.setViewportSize({width,height:900});
  for(const view of ['explorar','trajetorias','fontes','laboratorio']){
   await page.locator(`.nav[data-view=${view}]`).click();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}/${view} overflows`);
  }
 }
 await page.locator('.nav[data-view=explorar]').click();await page.setViewportSize({width:390,height:844});
 if(output)await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: MCP proposals stay separate; preview, incorporation with lost response, dismissal, visible origins and before/after; source observation -> reference space -> autosave -> reload; automatic source updates; versioned evidence; dismissed contributions; concurrent edits; offline recovery; lost-response retry; five widths; no JS errors.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(preview)preview.kill('SIGTERM');});
