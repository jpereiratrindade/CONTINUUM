"use strict";
// Every dynamic string enters the DOM through escapeHtml. No remote dependencies.
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const maybe = (value, empty="Não informado") => escapeHtml(value || empty);
let lastResult = null;
let dashboard = null;
let llmEnabled = false;
const QUESTION_KEY = "continuum.question.v1";
let questionState = {draft: "", submitted: null};
let asking = false;

function saveQuestion() {
  try {
    localStorage.setItem(QUESTION_KEY, JSON.stringify(questionState));
    return true;
  } catch {
    $("#question-status").textContent = "O navegador não permitiu salvar o rascunho. Mantenha esta página aberta até a pergunta ser registrada em Trajetórias.";
    return false;
  }
}
function restoreQuestion() {
  try {
    const state = JSON.parse(localStorage.getItem(QUESTION_KEY));
    if (state && typeof state.draft === "string") {
      questionState.draft = state.draft.slice(0,4000);
      if (state.submitted && typeof state.submitted.query === "string" && typeof state.submitted.request_id === "string") {
        questionState.submitted = state.submitted;
      }
      $("#query").value = questionState.draft;
      if (questionState.draft) $("#question-status").textContent = "Pergunta restaurada deste navegador. Investigue para recuperar o contexto; reenvios da mesma submissão não duplicam a trajetória.";
    }
  } catch { /* Storage may be unavailable; the form remains usable. */ }
}


async function request(path, body) {
  const config = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json","X-Lab-Intent":"user"},body:JSON.stringify(body)};
  const response = await fetch(path, config);
  let data;
  try { data = await response.json(); }
  catch { throw new Error(`Resposta inválida (HTTP ${response.status})`); }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function notify(message, error=false) {
  const box = $("#toast"); box.textContent=message; box.classList.toggle("error",error); box.classList.remove("hidden");
  clearTimeout(notify._timer); notify._timer=setTimeout(()=>box.classList.add("hidden"),5000);
}
function show(view) {
  $$(".view").forEach(el=>el.classList.toggle("hidden",el.id!==`view-${view}`));
  $$(".nav").forEach(el=>el.classList.toggle("active",el.dataset.view===view));
  const activeNav = $$(".nav").find(el=>el.dataset.view===view);
  $("#current-view").textContent = activeNav ? activeNav.textContent.trim() : "Explorar questões";
  $$(".nav").forEach(el=>{
    if (el.dataset.view===view) el.setAttribute("aria-current","page");
    else el.removeAttribute("aria-current");
  });
  if (view==="trajetorias") renderNodes();
  if (view==="fontes") renderSources();
  if (view==="laboratorio") renderLaboratory();
  if (location.hash!==`#${view}`) history.replaceState(null,"",`#${view}`);
}
function nodeCard(n, buttonText="Abrir trajetória") {
  return `<div class="card"><div class="meta">${escapeHtml(n.kind)} <span class="chip">${escapeHtml(n.status)}</span></div>
    <div class="card-title">${escapeHtml(n.title)}</div><p>${escapeHtml((n.body||"").slice(0,180) || "Sem contexto inicial")}</p>
    <button class="linklike" data-open-node="${escapeHtml(n.id)}">${buttonText} →</button></div>`;
}
async function refresh() {
  dashboard = await request("/api/dashboard");
  const health = await request("/api/health");
  llmEnabled = health.llm_enabled;
  $("#health").textContent = `${dashboard.totals.documents} documentos · ${dashboard.totals.events} acontecimentos`;
  $("#resume").innerHTML = `<h2>Retomadas possíveis</h2>` + (dashboard.questions.length ?
    `<div class="cards">${dashboard.questions.slice(0,6).map(n=>nodeCard(n)).join("")}</div>` :
    `<div class="notice">Nenhuma trajetória registrada ainda. Autorize uma fonte ou inicie uma questão; o laboratório não inventará um histórico.</div>`);
  $("#llm").disabled = asking || !lastResult || !llmEnabled;
  renderNodes();renderSources();renderLaboratory();
}
async function ask(event) {
  if (event) event.preventDefault();
  if (asking) return;
  const q = $("#query").value.trim();
  if (!q) return notify("Informe uma questão para investigar",true);
  questionState.draft = $("#query").value;
  if (!questionState.submitted || questionState.submitted.query !== q) {
    questionState.submitted = {query: q, request_id: crypto.randomUUID()};
  }
  saveQuestion(); // Preserve text and retry key before any network request.
  asking = true;
  const submit = $("#search-form button[type=submit]");
  submit.disabled = true;
  $("#results").setAttribute("aria-busy", "true");
  $("#download").disabled = true;
  $("#draft").disabled = true;
  $("#llm").disabled = true;
  lastResult = null;
  ["#document-results", "#node-results", "#connection-results", "#next-step", "#llm-output"].forEach(id=>$(id).replaceChildren());
  $("#results").classList.remove("hidden");
  $("#summary").textContent="Recuperando fontes observadas…";
  try {
    const result = await request("/api/investigations", {
      query: q, request_id: questionState.submitted.request_id
    });
    $("#question-status").textContent = "Pergunta preservada em Trajetórias. O texto continua disponível neste campo.";
    lastResult=result;
    $("#summary").textContent=result.summary;
    $("#document-results").innerHTML = `<h3 class="section-mini">Documentos recuperados (${result.documents.length})</h3>` +
      (result.documents.length ? result.documents.map(d=>`<article class="hit"><div class="hit-title">${escapeHtml(d.title)}</div>
      <div class="meta">Correspondência lexical · observado ${escapeHtml(d.observed_at)}</div>
      <p>${escapeHtml(d.snippet)}</p><div class="path">${escapeHtml(d.path)}</div></article>`).join("") : `<p class="muted">Nenhuma correspondência no corpus observado.</p>`);
    $("#node-results").innerHTML = `<h3 class="section-mini">Trajetórias relacionadas (${result.nodes.length})</h3>` +
      (result.nodes.length ? result.nodes.map(n=>nodeCard(n,"Inspecionar histórico")).join("") : `<p class="muted">Nenhuma questão ou hipótese registrada foi recuperada.</p>`);
    $("#connection-results").innerHTML = `<h3 class="section-mini">Conexões para investigar (${result.connections.length})</h3>` +
      (result.connections.length ? `<div class="connections">${result.connections.map(c=>`<div class="candidate"><span class="chip warn">Apenas candidata</span>
       <p><strong>${escapeHtml(c.from_title)}</strong> ↔ <strong>${escapeHtml(c.to_title)}</strong></p>
       <small>Termos comuns: ${escapeHtml(c.terms.join(", "))}. Pontuação lexical: ${escapeHtml(c.score)}.</small></div>`).join("")}</div>` :
       `<p class="muted">Não foram detectadas aproximações interfontes que superassem o limiar lexical. Isso não exclui relações conceituais.</p>`);
    $("#next-step").innerHTML=`<h3 class="section-mini">Próximos movimentos possíveis</h3><ul>${result.proposed_steps.map(t=>`<li>${escapeHtml(t)}</li>`).join("")}</ul><details><summary>Limites deste resultado</summary><ul>${result.limitations.map(t=>`<li>${escapeHtml(t)}</li>`).join("")}</ul></details>`;
    $("#llm-output").innerHTML="";
    refresh().catch(()=>{});
  } catch (ex) {
    notify(ex.message,true);
    $("#summary").textContent = "Não foi possível concluir a investigação. Sua pergunta continua no campo; tente novamente.";
    $("#question-status").textContent = "A confirmação do registro não chegou. Tente novamente: o mesmo envio não criará outra trajetória.";
  } finally {
    asking = false;
    submit.disabled = false;
    $("#results").removeAttribute("aria-busy");
    $("#download").disabled = !lastResult;
    $("#draft").disabled = !lastResult;
    $("#llm").disabled = !lastResult || !llmEnabled;
  }
}
async function openNode(id) {
  show("trajetorias");
  try {
    const t=await request(`/api/trajectory?id=${encodeURIComponent(id)}`);
    const n=t.node;
    const detail=$("#trajectory-detail");detail.classList.remove("hidden");
    detail.innerHTML=`<div class="eyebrow">LINHAGEM DOCUMENTADA</div><h2>${escapeHtml(n.title)}</h2>
      <div class="meta">${escapeHtml(n.kind)} · ${escapeHtml(n.status)} · identificador ${escapeHtml(n.id)}</div>
      <p>${escapeHtml(n.body || "Sem descrição")}</p>
      <h3>Revisar sem apagar o passado</h3><form id="revision-form" class="stack">
      <label for="revision-status">Situação atual</label><select id="revision-status">${["open","active","suspended","resolved"].map(s=>`<option value="${s}" ${s===n.status?"selected":""}>${s}</option>`).join("")}</select>
      <label for="revision-body">Compreensão atual</label><textarea id="revision-body" rows="4" maxlength="20000">${escapeHtml(n.body)}</textarea>
      <label for="revision-reason">Por que estamos revisando?</label><input id="revision-reason" required maxlength="2000" placeholder="Nova evidência, mudança de interpretação, contraponto…">
      <button class="subtle" type="submit">Registrar nova interpretação</button></form>
      <h3 class="history-heading">Acontecimentos preservados (${t.events.length})</h3>
      <div class="timeline">${t.events.map(e=>`<div class="time-entry"><h3>${escapeHtml(e.kind)}</h3><div class="meta">Ocorrência ${escapeHtml(e.occurred_at)} · registro ${escapeHtml(e.recorded_at)} · ${escapeHtml(e.evidence_state)}</div><pre>${escapeHtml(JSON.stringify(e.payload,null,2))}</pre></div>`).join("")}</div>
      <h3>Relações declaradas (${t.links.length})</h3><p>${t.links.length?t.links.map(l=>`<span class="chip">${escapeHtml(l.relation)} · ${escapeHtml(l.state)}</span> ${escapeHtml(l.reason)}`).join("<br>"):"Nenhuma relação declarada."}</p>`;
    $("#revision-form").addEventListener("submit",async (event)=>{
      event.preventDefault();try{await request("/api/nodes/revise",{id:n.id,status:$("#revision-status").value,body:$("#revision-body").value,reason:$("#revision-reason").value});notify("Revisão preservada como novo acontecimento");await refresh();await openNode(id);}catch(ex){notify(ex.message,true);}
    });
    detail.scrollIntoView({behavior:"smooth",block:"start"});
  } catch(ex) { notify(ex.message,true); }
}
function renderNodes() {
  if (!dashboard) return;
  const nodes=dashboard.questions;
  $("#node-list").innerHTML = nodes.length ? nodes.map(n=>nodeCard(n)).join("") : `<p class="muted">Ainda não há trajetórias declaradas.</p>`;
  const opts=`<option value="">Escolher…</option>`+nodes.map(n=>`<option value="${escapeHtml(n.id)}">${escapeHtml(n.title)}</option>`).join("");
  $("#link-source").innerHTML=opts; $("#link-target").innerHTML=opts;
}
function renderSources() {
  if (!dashboard) return;
  $("#source-list").innerHTML = dashboard.sources.length ? dashboard.sources.map(s=>`<div class="card"><div class="card-title">${escapeHtml(s.label)} <span class="chip ${s.active?"":"warn"}">${s.active?"Ativa":"Pausada"}</span></div><div class="path">${escapeHtml(s.path)}</div><p>Última observação: ${escapeHtml(s.last_scan_at||"Não observada")}</p><button class="linklike" data-toggle-source="${escapeHtml(s.id)}" data-source-active="${s.active?"false":"true"}">${s.active?"Pausar observação":"Reativar observação"}</button></div>`).join("") : `<div class="notice">Nenhuma pasta autorizada. O laboratório não observa o computador inteiro.</div>`;
}
function renderLaboratory() {
  if (!dashboard) return;
  $("#lab-stats").innerHTML=Object.entries({"Documentos":dashboard.totals.documents,"Trajetórias":dashboard.totals.nodes,"Acontecimentos":dashboard.totals.events,"Fontes":dashboard.totals.sources}).map(([label,value])=>`<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
  const integrity=dashboard.integrity;
  $("#recent-events").innerHTML=`<h2>Trilha temporal</h2><p class="muted">Integridade relativa ao banco: ${integrity.ok?"cadeia coerente":"falha detectada"} · ${integrity.checked} eventos verificados. Âncoras externas exigem operação CLI.</p>`+
    `<ul>${dashboard.recent_events.map(e=>`<li><strong>${escapeHtml(e.kind)}</strong> — ${escapeHtml(e.recorded_at)} <span class="chip">${escapeHtml(e.evidence_state)}</span></li>`).join("")}</ul>`;
}
function onForm(selector, callback) {$(selector).addEventListener("submit",async e=>{e.preventDefault();try{await callback();}catch(ex){notify(ex.message,true);}});}
function init() {
  restoreQuestion();
  $("#query").addEventListener("input",()=>{
    questionState.draft = $("#query").value;
    if (saveQuestion()) $("#question-status").textContent = "Rascunho salvo neste navegador. Ao investigar, a pergunta será preservada em Trajetórias.";
  });
  $$(".nav").forEach(btn=>btn.addEventListener("click",()=>show(btn.dataset.view)));
  $("#brand").addEventListener("click",()=>show("explorar"));
  document.body.addEventListener("click",async e=>{
    const nodeButton=e.target.closest("[data-open-node]");if(nodeButton)openNode(nodeButton.dataset.openNode);
    const sourceButton=e.target.closest("[data-toggle-source]");
    if(sourceButton){try{const active=sourceButton.dataset.sourceActive==="true";await request("/api/sources/active",{id:sourceButton.dataset.toggleSource,active});notify(active?"Observação reativada":"Observação pausada; histórico permanece preservado");await refresh();}catch(ex){notify(ex.message,true);}}
  });
  $("#search-form").addEventListener("submit",ask);
  $("#download").addEventListener("click",()=>{if(lastResult)location.href=`/api/export?q=${encodeURIComponent(lastResult.query)}`;});
  $("#draft").addEventListener("click",async()=>{if(!lastResult)return;try{const r=await request("/api/draft",{query:lastResult.query});notify(`Roteiro criado: ${r.path}`);await refresh();}catch(ex){notify(ex.message,true);}});
  $("#llm").addEventListener("click",async()=>{if(!lastResult)return;$("#llm-output").textContent="Consultando o modelo local…";try{const r=await request("/api/explore",{query:lastResult.query});$("#llm-output").innerHTML=`<p class="chip warn">Interpretação automática não verificada · ${escapeHtml(r.model)}</p><div class="llm-text">${escapeHtml(r.text)}</div>`;}catch(ex){$("#llm-output").textContent=ex.message;notify(ex.message,true);}});
  onForm("#node-form",async()=>{const n=await request("/api/nodes",{kind:$("#node-kind").value,title:$("#node-title").value,body:$("#node-body").value});$("#node-form").reset();notify("Trajetória criada com registro histórico");await refresh();await openNode(n.id);});
  onForm("#source-form",async()=>{await request("/api/sources",{label:$("#source-label").value,path:$("#source-path").value});const result=await request("/api/scan",{});notify(`Fonte autorizada; ${result.added} documento(s) observado(s)`);await refresh();});
  $("#scan").addEventListener("click",async()=>{try{const r=await request("/api/scan",{});notify(`Observação: ${r.added} novos, ${r.changed} alterados, ${r.unchanged} inalterados.`);await refresh();}catch(ex){notify(ex.message,true);}});
  onForm("#link-form",async()=>{await request("/api/links",{source_id:$("#link-source").value,target_id:$("#link-target").value,relation:$("#link-relation").value,state:$("#link-state").value,reason:$("#link-reason").value});notify("Relação declarada, sem atribuir validade científica");$("#link-form").reset();await refresh();});
  const initial=location.hash.replace("#","");show(["explorar","trajetorias","fontes","laboratorio"].includes(initial)?initial:"explorar");
  refresh().catch(ex=>notify(`Não foi possível carregar o laboratório: ${ex.message}`,true));
}
document.addEventListener("DOMContentLoaded",init);
