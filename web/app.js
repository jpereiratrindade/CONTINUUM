"use strict";
const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const QUESTION_KEY = "continuum.question.v1";
const KIND_LABEL = {question:"Questão",idea:"Ideia",hypothesis:"Hipótese",decision:"Decisão",experiment:"Experimento",opportunity:"Oportunidade"};
const STATUS_LABEL = {open:"Aberto",active:"Em andamento",suspended:"Suspenso",resolved:"Resolvido"};
const RELATION_LABEL = {evolves_into:"Evolui para",supports:"Pode sustentar",contradicts:"Contradiz / tensiona",depends_on:"Depende de",relates_to:"Relaciona-se a"};
const STATE_LABEL = {candidate:"Candidata",endorsed:"Declarada",rectified:"Retificada"};
const MOVE_RELATION_LABEL = {objects_to:"Contesta",challenges:"Tensiona",reformulates:"Reformula",constrains:"Condiciona",supports:"Sustenta",resolves:"Encaminha"};
const DISPOSE_LABEL = {useful:"Útil",not_relevant:"Não pertinente",incorrect_interpretation:"Interpretação incorreta",revisit_later:"Revisitar depois"};
function clipText(value, limit=95) {
  const s = String(value ?? "").trim();
  if (s.length <= limit) return s;
  const cut = s.slice(0, limit);
  const sp = cut.lastIndexOf(" ");
  return (sp >= Math.floor(limit * 0.6) ? cut.slice(0, sp) : cut).replace(/[,;:\s]+$/, "") + "…";
}
let questionState = {draft: "", submitted: null};
let allNodes = [], nextOffset = null, active = null, opening = 0, asking = false;
function uuid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") crypto.getRandomValues(b);
  else for (let i = 0; i < 16; i++) b[i] = Math.floor(Math.random() * 256);
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, x => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
}

async function request(path, body) {
  const config = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json","X-Lab-Intent":"user"},body:JSON.stringify(body)};
  const response = await fetch(path, config);
  let data;
  try { data = await response.json(); } catch { throw new Error(`Resposta inválida (HTTP ${response.status})`); }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function store(key,value) { try { localStorage.setItem(key,JSON.stringify(value)); return true; } catch { return false; } }
function read(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } }
function remove(key) { try { localStorage.removeItem(key); } catch { /* Storage may be unavailable. */ } }
function notify(message,error=false) {
  const toast=$("#toast");toast.textContent=message;toast.classList.toggle("error",error);toast.classList.remove("hidden");
  clearTimeout(notify.timer);notify.timer=setTimeout(()=>toast.classList.add("hidden"),5500);
}
function show(view) {
  $$(".view").forEach(el=>el.classList.toggle("hidden",el.id!==`view-${view}`));
  $$(".nav").forEach(el=>{el.classList.toggle("active",el.dataset.view===view);if(el.dataset.view===view)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  $("#current-view").textContent=$$(".nav").find(el=>el.dataset.view===view)?.textContent.trim() || "Continuar";
  history.replaceState(null,"",`#${view}${view==="explorar"&&active?"/"+active.id:""}`);
  if(view==="fontes")renderSources().catch(ex=>notify(ex.message,true));
  if(view==="laboratorio")renderLaboratory().catch(ex=>notify(ex.message,true));
}
function nodeCard(node) {
  return `<article class="card"><div class="card-title">${escapeHtml(node.title)}</div><div class="meta">${escapeHtml(KIND_LABEL[node.kind]||node.kind)} · ${escapeHtml(STATUS_LABEL[node.status]||node.status)}</div><button class="linklike" data-open-node="${escapeHtml(node.id)}">Continuar →</button></article>`;
}
async function loadNodes(append=false) {
  const result=await request(`/api/nodes?limit=100&offset=${append?(nextOffset||0):0}`);
  allNodes=append?allNodes.concat(result.nodes):result.nodes;nextOffset=result.next_offset;
  $("#node-list").innerHTML=allNodes.map(nodeCard).join("") || '<p class="muted">Seu próximo percurso pode começar com um fragmento.</p>';
  if(nextOffset!==null)$("#node-list").insertAdjacentHTML("beforeend",'<button id="more-nodes" class="subtle">Mais percursos</button>');
  const ongoing=allNodes.filter(n=>["open","active"].includes(n.status)&&n.id!==active?.id).slice(0,3);
  $("#resume").innerHTML=ongoing.length?`<h2>Outros percursos</h2><div class="cards">${ongoing.map(nodeCard).join("")}</div>`:"";
  const options='<option value="">Escolher…</option>'+allNodes.map(n=>`<option value="${escapeHtml(n.id)}">${escapeHtml(n.title)}</option>`).join("");
  $("#link-source").innerHTML=options;$("#link-target").innerHTML=options;
}
function updateStatus(session,text) { if(active===session)$("#note-status").textContent=text; }
function rememberNote(session) {
  const saved=store(`continuum.note.${session.id}`,{text:session.text,base_revision:session.revision});
  updateStatus(session,saved?"Rascunho local":"Sem cópia local · mantenha esta página aberta");
}
function queueSave(session) {
  clearTimeout(session.timer);
  session.timer=setTimeout(()=>saveNote(session),900);
}
function editing() {
  if(!active)return;
  active.text=$("#working-text").value;active.dirty=true;rememberNote(active);
  if(!active.conflict)queueSave(active);
}
function conflictUI(session) {
  if(active!==session)return;
  $("#note-conflict").classList.toggle("hidden",!session.conflict);
  $("#remote-note").textContent=session.remote?.text || "(sem texto)";
}
async function saveNote(session) {
  clearTimeout(session.timer);
  if(!session.dirty||session.inflight||session.conflict)return;
  session.inflight=true;updateStatus(session,"Preservando…");
  const sent=session.text;
  try {
    const result=await request("/api/reference/note",{id:session.id,text:sent,revision:session.revision});
    session.revision=result.revision;session.dirty=session.text!==sent;
    if(session.dirty){rememberNote(session);queueSave(session);}else{remove(`continuum.note.${session.id}`);updateStatus(session,"Preservado");}
    if(active===session)await pollReference();
  } catch(ex) {
    if(ex.message.includes("mudou em outro ambiente")){
      try {const latest=await request(`/api/reference?id=${encodeURIComponent(session.id)}`);session.remote=latest.note;session.conflict=true;conflictUI(session);}catch{/* Local draft remains. */}
      updateStatus(session,"Conciliação necessária");
    } else {updateStatus(session,"Pendente · texto mantido localmente");}
  } finally { session.inflight=false; }
}
async function openNode(id) {
  const token=++opening;
  if(active)await saveNote(active);
  const data=await request(`/api/reference?id=${encodeURIComponent(id)}`);
  if(token!==opening)return;
  const draft=read(`continuum.note.${id}`);
  const session={id,text:data.note.text,revision:data.note.revision,dirty:false,inflight:false,conflict:false,remote:data.note,packageId:null};
  if(draft&&typeof draft.text==="string"&&Number.isInteger(draft.base_revision)){
    if(draft.text===data.note.text)remove(`continuum.note.${id}`);
    else {session.text=draft.text;session.dirty=true;session.conflict=draft.base_revision!==data.note.revision;}
  }
  active=session;store("continuum.active",id);
  $("#reference-title").textContent=data.node.title;
  $("#working-text").value=session.text;
  $("#reference-workspace").classList.remove("hidden");
  $("#search-form").classList.add("hidden");
  $("#reference-history").replaceChildren();
  $(".workspace-history").open=false;
  $("#reference-git").replaceChildren();
  $(".workspace-git").open=false;
  $("#git-status").textContent="";
  updateStatus(session,session.conflict?"Rascunho local · conciliação necessária":session.dirty?"Rascunho restaurado":"Preservado");
  conflictUI(session);renderReference(data);show("explorar");
  if(session.dirty&&!session.conflict)queueSave(session);
  await loadNodes();
}
function originLabel(origin) {
  if(!origin)return "Origem não informada";
  if(origin.source_type==="mcp_client"){
    const client=origin.source_ref.replace(/^mcp:/,"");
    return /codex/i.test(client)?"Codex, via MCP":`${client}, via MCP`;
  }
  if(origin.source_ref==="browser-or-http-client")return "Navegador / API";
  return origin.source_ref || "Origem não informada";
}
function renderProposals(data) {
  const proposals=data.proposals || [];
  const key=JSON.stringify(proposals)+data.note.revision;
  if(active.proposalKey===key)return;
  active.proposalKey=key;
  const pending=proposals.filter(p=>p.state==="pending");
  $("#show-proposals").classList.toggle("hidden",!pending.length);
  $("#show-proposals").textContent=pending.length===1?"Uma proposta para examinar":`${pending.length} propostas para examinar`;
  const reviewed=proposals.filter(p=>p.state!=="pending");
  $("#note-proposals").innerHTML=(pending.length?`<h3>${pending.length===1?"Uma proposta para examinar":pending.length+" propostas para examinar"}</h3>`:"")+pending.map(p=>`<details class="text-proposal"><summary title="${escapeHtml(p.source_ref)}">Proposta de ${escapeHtml(originLabel(p))}<small>Ainda não incorporada · ${escapeHtml(new Date(p.recorded_at).toLocaleString("pt-BR"))}</small></summary><p class="small muted">Se incorporar, este trecho será acrescentado ao final do texto preservado.</p><pre class="proposal-text">${escapeHtml(p.text)}</pre><div class="toolbar"><button class="subtle" data-accept-proposal="${escapeHtml(p.id)}" data-revision="${data.note.revision}">Incorporar ao final</button><button class="subtle" data-dismiss-proposal="${escapeHtml(p.id)}">Dispensar</button></div></details>`).join("")+(reviewed.length?`<details class="reviewed-proposals"><summary>Propostas examinadas (${reviewed.length})</summary>${reviewed.map(p=>`<details><summary>${p.state==="incorporated"?"Incorporada":"Dispensada"} · ${escapeHtml(originLabel(p))}</summary><pre class="proposal-text">${escapeHtml(p.text)}</pre></details>`).join("")}</details>`:"");
}
function spanLabel(refs, brief=false) {
  if(!refs||!refs.length)return "sem trecho ancorado";
  const r=refs[0];
  if(brief)return `turno ${r.turn_id}`;
  return `turno ${r.turn_id}[${r.span_start}:${r.span_end}] · hash ${(r.source_version_hash||"").slice(0,10)}`;
}
function renderChainCard(ch, idx) {
  const relLabel = MOVE_RELATION_LABEL[ch.what_was_objected.relation] || "Objeção";
  return `<div class="critical-chain">
    <div class="chain-header">
      <strong>Transformação #${idx+1}</strong>
      <span class="chip" title="Escopo: ${escapeHtml(ch.scope)}">Reconstrução candidata</span>
    </div>
    <div class="chain-row">
      <span class="chain-step-label">1. Proposta questionada</span>
      <div>${escapeHtml(ch.questioned_proposal.content)}</div>
    </div>
    <div class="chain-row objection">
      <span class="chain-step-label">2. Objeção (${escapeHtml(relLabel)})</span>
      <div>${escapeHtml(ch.what_was_objected.content)}</div>
    </div>
    ${ch.what_changed_after?`<div class="chain-row reformulation">
      <span class="chain-step-label">3. Reformulação subsequente</span>
      <div>${escapeHtml(ch.what_changed_after.content)}</div>
    </div>`:`<div class="chain-row"><span class="chain-step-label">3. Reformulação subsequente</span><div class="muted">Ainda sem nova formulação vinculada.</div></div>`}
    <div class="chain-row doubt">
      <span class="chain-step-label">4. Questão em aberto</span>
      <div>${escapeHtml(ch.remaining_doubt)}</div>
    </div>
    <details class="chain-drawer">
      <summary>Lastro nos turnos, leitura alternativa e avaliação</summary>
      <div class="chain-drawer-body">
        <div><strong>Âncora da proposta:</strong> ${escapeHtml(spanLabel(ch.questioned_proposal.evidence_refs))}</div>
        <div><strong>Âncora da objeção:</strong> ${escapeHtml(spanLabel(ch.what_was_objected.evidence_refs))}</div>
        ${ch.what_changed_after?`<div><strong>Âncora da reformulação:</strong> ${escapeHtml(spanLabel(ch.what_changed_after.evidence_refs))}</div>`:""}
        <div><em>Leitura alternativa:</em> ${escapeHtml(ch.what_was_objected.alternative_reading)}</div>
        <div class="disposition-bar">
          <span class="small muted">Avaliar esta objeção no escopo atual:</span>
          <button class="subtle" type="button" data-dispose-target="${escapeHtml(ch.what_was_objected.id)}" data-dispose="useful">Útil</button>
          <button class="subtle" type="button" data-dispose-target="${escapeHtml(ch.what_was_objected.id)}" data-dispose="not_relevant">Não pertinente</button>
          <button class="subtle" type="button" data-dispose-target="${escapeHtml(ch.what_was_objected.id)}" data-dispose="incorrect_interpretation">Interpretação incorreta</button>
          <button class="subtle" type="button" data-dispose-target="${escapeHtml(ch.what_was_objected.id)}" data-dispose="revisit_later">Revisitar depois</button>
        </div>
      </div>
    </details>
  </div>`;
}
function renderCriticalTrajectory(data) {
  const crit=data.critical_trajectory;
  if(!crit)return;
  if($("#focus-switcher")&&allNodes.length){
    $("#focus-switcher").innerHTML=allNodes.slice(0,8).map(n=>`<button type="button" class="focus-switch-btn${n.id===data.node.id?" active":""}" data-open-node="${escapeHtml(n.id)}"><span class="chip">${escapeHtml(KIND_LABEL[n.kind]||n.kind)}</span> <span>${escapeHtml(clipText(n.title, 78))}</span></button>`).join("");
  }
  const key=JSON.stringify(crit)+allNodes.length;
  if(active.critKey===key)return;
  active.critKey=key;
  const counts=crit.context_counts||{};
  if($("#reference-context-counts")){
    $("#reference-context-counts").innerHTML=`<div class="ctx-pill"><strong>${counts.documents||0}</strong><span>Documentos</span></div><div class="ctx-pill"><strong>${counts.dialogues||0}</strong><span>Discussões</span></div><div class="ctx-pill"><strong>${counts.commits||0}</strong><span>Versões Git</span></div><div class="ctx-pill" title="${counts.moves||0} movimentos reconstruídos"><strong>${counts.transformations||0}</strong><span>Transformações</span></div>`;
  }
  const ribbon=crit.transformation_ribbon||[];
  if($("#reference-ribbon")){
    $("#reference-ribbon").innerHTML=ribbon.length?ribbon.map((step,idx)=>`<div class="ribbon-step" data-kind="${escapeHtml(step.kind)}" title="${escapeHtml(spanLabel(step.evidence_refs))}"><strong>${idx+1}. ${escapeHtml(step.stage_label)}</strong><div>${escapeHtml(step.summary)}</div><div class="small muted">${escapeHtml(spanLabel(step.evidence_refs, true))}</div></div>`).join('<div class="ribbon-arrow" aria-hidden="true">→</div>'):'<p class="small muted">Importe um diálogo autorizado para reconstruir a cadeia de transformações (proposta → objeção → reformulação).</p>';
  }
  const chains=crit.chains||[];
  if($("#reference-critical-chains")){
    if(!chains.length){
      $("#reference-critical-chains").innerHTML="";
    } else if(chains.length===1){
      $("#reference-critical-chains").innerHTML=renderChainCard(chains[0], 0);
    } else {
      const latestIdx = chains.length - 1;
      const olderCount = chains.length - 1;
      const olderHtml = chains.slice(0, latestIdx).map((ch, idx) => renderChainCard(ch, idx)).join("");
      $("#reference-critical-chains").innerHTML = renderChainCard(chains[latestIdx], latestIdx) + `<details class="older-chains"><summary>Ver ${olderCount === 1 ? "1 transformação anterior" : olderCount + " transformações anteriores"} deste percurso</summary><div class="older-chains-body">${olderHtml}</div></details>`;
    }
  }
  const contrib=crit.continuum_contributions||{};
  const slots=[contrib.candidate_convergence,contrib.recurring_objection,contrib.tension_contradiction,contrib.next_movement].filter(Boolean);
  if($("#reference-continuum-cards")){
    $("#reference-continuum-cards").innerHTML=slots.length?slots.map(s=>`<div class="epistemic-card" data-slot="${escapeHtml(s.kind)}"><div class="epistemic-card-head"><h4>${escapeHtml(s.label)}</h4><span class="chip">${escapeHtml(STATE_LABEL[s.state]||s.state)}</span></div><div class="epistemic-card-body">${escapeHtml(s.summary)}</div>${(s.alternative_reading||(s.evidence_refs&&s.evidence_refs.length))?`<details class="card-drawer"><summary>Fonte e leitura alternativa</summary><div class="card-drawer-body">${s.evidence_refs?.length?`<div><strong>Fonte:</strong> ${escapeHtml(spanLabel(s.evidence_refs))}</div>`:""}${s.alternative_reading?`<div><em>Leitura alternativa:</em> ${escapeHtml(s.alternative_reading)}</div>`:""}</div></details>`:""}</div>`).join(""):"";
  }
  if($("#docs-approx-details")&&slots.length===0){
    $("#docs-approx-details").open=true;
  }
}
function renderTransformations(data) {
  const items=data.transformations || [];
  const key=JSON.stringify(items)+data.node.status+data.node.kind;
  if(active.transformKey===key)return;
  active.transformKey=key;
  $("#reference-badge").textContent=`${KIND_LABEL[data.node.kind]||data.node.kind} · ${STATUS_LABEL[data.node.status]||data.node.status}`;
  if($("#revise-status"))$("#revise-status").value=data.node.status;
  $("#reference-transformations").innerHTML=items.length?items.map(t=>{
    const arrow=t.direction==="outgoing"?"→":"←";
    const rel=RELATION_LABEL[t.relation]||t.relation;
    const n=t.node;
    return `<div class="transformation-item"><div class="transformation-meta"><span class="chip">${escapeHtml(KIND_LABEL[n.kind]||n.kind)} · ${escapeHtml(STATUS_LABEL[n.status]||n.status)}</span> <span class="small muted">${arrow} ${escapeHtml(rel)}</span><strong>${escapeHtml(n.title)}</strong><div class="small muted">${escapeHtml(t.reason)}</div></div><button class="subtle" type="button" data-open-node="${escapeHtml(n.id)}">Abrir →</button></div>`;
  }).join(""):'<p class="small muted">Nenhuma transformação ou vínculo registrado ainda. Desdobre uma hipótese, ideia, decisão ou experimento abaixo para avançar o percurso.</p>';
}
async function renderGitHistory(id) {
  const g=await request(`/api/reference/git?id=${encodeURIComponent(id)}`);
  if(!g.versioned){$("#reference-git").innerHTML='<p class="small muted">Ainda não há commit Git para este percurso. Clique em "Versionar no Git" para registrar um marco.</p>';return;}
  $("#git-status").textContent=`Git HEAD: ${g.commits[0]?.hash || ""}`;
  $("#reference-git").innerHTML=`<p class="small muted">Arquivo: <code>${escapeHtml(g.path)}</code></p>`+g.commits.map(c=>`<div class="small"><code>${escapeHtml(c.hash)}</code> · ${escapeHtml(new Date(c.date).toLocaleString("pt-BR"))} — <strong>${escapeHtml(c.subject)}</strong></div>`).join("")+(g.diff?`<h4>Último diff (HEAD)</h4><pre>${escapeHtml(g.diff)}</pre>`:"");
}
function renderReference(data) {
  if(!active||data.node.id!==active.id)return;
  const author=data.authorship;
  const last=author?.last_edit;
  $("#note-origin").title=last?.source_ref || "";
  $("#note-origin").textContent=last?`${last.kind==="working_note_saved"?"Última edição preservada":"Registro inicial"}: ${originLabel(last)} · ${new Date(last.recorded_at).toLocaleString("pt-BR")} · ${author.edits} ${author.edits===1?"edição registrada":"edições registradas"}${author.proposal?" · proposta de "+originLabel(author.proposal)+" incorporada":""}`:"Origem não informada";
  renderProposals(data);
  renderCriticalTrajectory(data);
  renderTransformations(data);
  const p=data.package;
  $("#context-state").textContent=data.stale?"Atualização das referências pendente":"Referências aproximadas automaticamente";
  if(!p){$("#reference-contributions").innerHTML='<p class="muted small">O contexto será preparado na próxima observação das fontes.</p>';return;}
  const available=p.contributions.filter(c=>!data.feedback[c.id]||data.feedback[c.id]==="available");
  const renderKey=data.package_event_id+JSON.stringify(data.feedback);
  if(active.packageId===renderKey)return;
  active.packageId=renderKey;active.package=p;
  $("#reference-next").innerHTML=p.next_movement?`<details class="context-details"><summary>Próximo movimento registrado</summary><p>${escapeHtml(p.next_movement)}</p></details>`:"";
  $("#reference-contributions").innerHTML=available.length?available.map(c=>`<details class="contribution"><summary><span>${escapeHtml(c.title)}</span><small>${escapeHtml(c.source)}${p.changed_evidence?.includes(c.document_id)?" · nova referência ou versão":""}</small></summary><p class="muted small">Aproximação lexical · candidata</p>${c.context_notice?`<p class="notice small">${escapeHtml(c.context_notice)}</p>`:""}<blockquote>${escapeHtml(c.text)}</blockquote><div class="toolbar"><button class="subtle" data-incorporate="${escapeHtml(c.id)}">Trazer para o texto</button><button class="subtle" data-dismiss="${escapeHtml(c.id)}">Dispensar</button><button class="linklike" data-version="${escapeHtml(c.version_event_id)}">Ler fonte completa</button></div><div class="source-preview"></div></details>`).join(""):'<p class="muted small">Nenhuma contribuição nova por enquanto.</p>';
  if(Object.values(data.feedback).some(s=>s!=="available"))$("#reference-contributions").insertAdjacentHTML("beforeend",'<button id="restore-contributions" class="linklike">Rever contribuições dispensadas ou incorporadas</button>');
  active.feedback=data.feedback;
  $("#reference-related").innerHTML=p.related.map(n=>`<button class="related-idea" data-open-node="${escapeHtml(n.id)}">${escapeHtml(n.title)} →</button>`).join("") || '<p class="muted small">Nenhum outro percurso aproximado.</p>';
  $("#reference-connections").innerHTML=p.connections.map(c=>`<p class="small muted">Possível conexão entre referências: ${escapeHtml(c.terms.join(", "))}. Conferir os contextos.</p>`).join("");
  $("#reference-provenance").textContent=`Pacote ${data.package_event_id}. Preparado em ${new Date(p.generated_at).toLocaleString("pt-BR")}. Última contribuição: ${p.last_change?.source_ref||"não informada"}.`;
}
async function pollReference() {
  const session=active;if(!session)return;
  const data=await request(`/api/reference?id=${encodeURIComponent(session.id)}`);
  if(active!==session)return;
  if(!session.dirty&&!session.inflight){
    session.revision=data.note.revision;session.text=data.note.text;
    if($("#working-text").value!==session.text)$("#working-text").value=session.text;
  }
  $("#reference-title").textContent=data.node.title;
  renderReference(data);
}
async function ask(event) {
  event.preventDefault();if(asking)return;
  const query=$("#query").value.trim();if(!query)return;
  if(!questionState.submitted||questionState.submitted.query!==query)questionState.submitted={query,request_id:uuid()};
  questionState.draft=$("#query").value;store(QUESTION_KEY,questionState);
  asking=true;$("#search-form button[type=submit]").disabled=true;
  try {
    const result=await request("/api/investigations",{query:questionState.submitted.query,request_id:questionState.submitted.request_id});
    questionState.submitted.node_id=result.question_node.id;store(QUESTION_KEY,questionState);
    store("continuum.active",result.question_node.id);
    $("#question-status").textContent="Ideia preservada em seu percurso.";
    await openNode(result.question_node.id);
    $("#working-text").focus();
  }catch(ex){$("#question-status").textContent="Não foi possível concluir. Seu texto continua aqui; tente novamente.";notify(ex.message,true);}
  finally{asking=false;$("#search-form button[type=submit]").disabled=false;}
}
async function renderSources(){
  const data=await request("/api/sources");
  $("#source-list").innerHTML=data.sources.map(s=>`<div class="card"><div class="card-title">${escapeHtml(s.label)}</div><span class="chip">${s.active?"Observando":"Pausada"}</span><div class="path">${escapeHtml(s.path)}</div><button class="linklike" data-toggle-source="${escapeHtml(s.id)}" data-active="${s.active?"false":"true"}">${s.active?"Pausar":"Reativar"}</button></div>`).join("")||'<p class="muted">Autorize uma pasta para aproximar seu trabalho das referências existentes.</p>';
}
async function renderLaboratory(){
  const d=await request("/api/dashboard");
  $("#lab-stats").innerHTML=Object.entries({Documentos:d.totals.documents,Percursos:d.totals.nodes,Acontecimentos:d.totals.events,Fontes:d.totals.sources}).map(([label,value])=>`<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
  $("#recent-events").innerHTML=`<h2>Trilha temporal</h2><p>${d.integrity.ok?"Cadeia coerente":"Falha detectada"} · ${d.integrity.checked} eventos</p>`;
}
function onForm(selector,callback){$(selector).addEventListener("submit",async event=>{event.preventDefault();try{await callback();}catch(ex){notify(ex.message,true);}});}
async function actions(event){
 const target=event.target.closest("button");if(!target)return;
 if(target.dataset.openNode)return openNode(target.dataset.openNode);
 if(target.id==="export-work"&&active){await saveNote(active);if(active.dirty||active.conflict)throw Error("Conclua o salvamento para exportar o texto compartilhado.");location.href=`/api/reference/export?id=${encodeURIComponent(active.id)}`;return;}
 if(target.id==="git-checkpoint"&&active){
  target.disabled=true;
  try{
    await saveNote(active);
    if(active.dirty||active.conflict)throw Error("Conclua o salvamento antes de versionar no Git.");
    const res=await request("/api/reference/git",{id:active.id});
    $("#git-status").textContent=res.head?`Git HEAD: ${res.head}${res.committed?" (novo commit)":" (sem alterações)"}`:"";
    $(".workspace-git").open=true;
    await renderGitHistory(active.id);
    notify(res.committed?`Marco versionado no Git (${res.head}).`:"O arquivo Git já está atualizado com esta revisão.");
  }finally{target.disabled=false;}
  return;
 }
 if(target.id==="show-changes"){$(".workspace-history").open=true;$(".workspace-history").scrollIntoView({behavior:"smooth",block:"nearest"});return;}
 if(target.id==="show-proposals"){$("#note-proposals").scrollIntoView({behavior:"smooth",block:"start"});return;}
 if(target.id==="more-nodes")return loadNodes(true);
 if(target.dataset.toggleSource){await request("/api/sources/active",{id:target.dataset.toggleSource,active:target.dataset.active==="true"});return renderSources();}
 if(target.dataset.version){const doc=await request(`/api/document-version?id=${encodeURIComponent(target.dataset.version)}`);const host=target.closest("details").querySelector(".source-preview");host.replaceChildren();const pre=document.createElement("pre");pre.textContent=doc.body;host.append(pre);return;}
 if(!active)return;
 const session=active;
 if(target.dataset.disposeTarget&&target.dataset.dispose){
  target.disabled=true;
  try{
    await request("/api/reference/move/dispose",{id:session.id,target_id:target.dataset.disposeTarget,disposition:target.dataset.dispose,target_kind:"move"});
    notify(`Avaliação "${DISPOSE_LABEL[target.dataset.dispose]||target.dataset.dispose}" registrada para este escopo.`);
    await pollReference();
  }finally{target.disabled=false;}
  return;
 }
 if(target.dataset.acceptProposal||target.dataset.dismissProposal){
  if(target.dataset.acceptProposal&&(session.dirty||session.inflight||session.conflict)){
    await saveNote(session);
    throw Error("Confira o texto preservado e a proposta antes de incorporar.");
  }
  target.disabled=true;
  try {
    await request("/api/reference/proposal/review",{id:session.id,proposal_id:target.dataset.acceptProposal||target.dataset.dismissProposal,state:target.dataset.acceptProposal?"incorporated":"dismissed",revision:Number(target.dataset.revision || session.revision)});
    await pollReference();
  } catch(ex) {await pollReference();throw ex;} finally {target.disabled=false;}
  return;
 }
 if(target.dataset.dismiss||target.dataset.incorporate){
  target.disabled=true;
  try {
  const ident=target.dataset.dismiss||target.dataset.incorporate;
  if(target.dataset.incorporate){
    const c=session.package.contributions.find(c=>c.id===ident);
    const text=session.text+`\n\n> ${c.text.replace(/\n/g,"\n> ")}\n\nReferência: ${c.title} · snapshot ${c.version_event_id} · SHA-256 ${c.content_hash}\n`;
    if(text.length>20000)throw Error("O trecho excede o limite do texto de trabalho.");
    session.text=text;session.dirty=true;$("#working-text").value=text;rememberNote(session);await saveNote(session);
    if(session.dirty||session.conflict)throw Error("Contribuição no rascunho local. Concilie ou conclua o salvamento antes de marcá-la como incorporada.");
  }
  await request("/api/reference/review",{id:session.id,suggestion_id:ident,state:target.dataset.dismiss?"dismissed":"incorporated"});return await pollReference();
  } finally {target.disabled=false;}
 }
 if(target.id==="restore-contributions"){
  for(const [suggestion_id,state] of Object.entries(session.feedback))if(state!=="available"&&session.package.contributions.some(c=>c.id===suggestion_id))await request("/api/reference/review",{id:session.id,suggestion_id,state:"available"});
  return pollReference();
 }
}
async function init(){
 const saved=read(QUESTION_KEY);if(saved&&typeof saved.draft==="string"){questionState=saved;$("#query").value=saved.draft.slice(0,4000);}
 $("#query").addEventListener("input",()=>{questionState.draft=$("#query").value;$("#question-status").textContent=store(QUESTION_KEY,questionState)?"Rascunho salvo neste navegador.":"Sem cópia local · mantenha a página aberta.";});
 $("#search-form").addEventListener("submit",ask);
 $("#working-text").addEventListener("input",editing);
 $("#working-text").addEventListener("blur",()=>{if(active)saveNote(active);});
 $("#new-idea").addEventListener("click",()=>{if(questionState.submitted?.node_id){questionState={draft:"",submitted:null};$("#query").value="";store(QUESTION_KEY,questionState);}$("#search-form").classList.remove("hidden");$("#query").focus();});
 $("#resolve-note").addEventListener("click",async()=>{if(!active?.remote)return;active.revision=active.remote.revision;active.conflict=false;conflictUI(active);await saveNote(active);});
 $("#use-remote-note").addEventListener("click",()=>{if(!active?.remote)return;active.text=active.remote.text;active.revision=active.remote.revision;active.dirty=false;active.conflict=false;$("#working-text").value=active.text;remove(`continuum.note.${active.id}`);conflictUI(active);updateStatus(active,"Versão compartilhada");});
 $(".workspace-git").addEventListener("toggle",async event=>{if(event.target.open&&active){try{await renderGitHistory(active.id);}catch(ex){notify(ex.message,true);}}});
 $(".workspace-history").addEventListener("toggle",async event=>{if(event.target.open&&active){try{const data=await request(`/api/trajectory?id=${encodeURIComponent(active.id)}`);$("#reference-history").innerHTML=data.events.map(e=>`<details class="history-event"><summary>${escapeHtml(e.kind==="working_note_saved"?"Edição do texto":e.kind==="note_proposed"?"Proposta recebida":e.kind==="note_proposal_reviewed"?"Proposta examinada":e.kind==="git_checkpoint_recorded"?"Versionado no Git":e.kind)} · ${escapeHtml(new Date(e.recorded_at).toLocaleString("pt-BR"))} · ${escapeHtml(originLabel(e))}</summary>${e.kind==="working_note_saved"?`${e.payload.proposal?`<p class="small">Proposta de ${escapeHtml(originLabel(e.payload.proposal))} incorporada.</p>`:""}<p class="small muted">Cliente registrado: ${escapeHtml(e.source_ref)}${e.payload.proposal?" · proposta: "+escapeHtml(e.payload.proposal.source_ref):""}</p><h4>Antes</h4><pre>${escapeHtml(e.payload.before.text)}</pre><h4>Depois</h4><pre>${escapeHtml(e.payload.after.text)}</pre>`:`<pre>${escapeHtml(JSON.stringify(e.payload,null,2))}</pre>`}</details>`).join("");}catch(ex){notify(ex.message,true);}}});
 $$(".nav").forEach(btn=>btn.addEventListener("click",()=>show(btn.dataset.view)));
 $("#brand").addEventListener("click",event=>{event.preventDefault();show("explorar");});
 document.body.addEventListener("click",event=>actions(event).catch(ex=>notify(ex.message,true)));
 onForm("#dialogue-form",async()=>{if(!active)return;await saveNote(active);const res=await request("/api/reference/dialogue",{id:active.id,conversation_id:$("#dialogue-conv-id").value,scope:$("#dialogue-scope").value,title:$("#dialogue-title").value,dialogue_text:$("#dialogue-text").value});$("#dialogue-text").value="";await pollReference();notify(res.idempotent_reuse?"Diálogo idêntico já importado (idempotente).":`Diálogo importado: ${res.moves.length} movimentos e ${res.transformations.length} transformações reconstruídas.`);});
 onForm("#revise-form",async()=>{if(!active)return;await saveNote(active);await request("/api/nodes/revise",{id:active.id,status:$("#revise-status").value,reason:$("#revise-reason").value});$("#revise-reason").value="";$(".revise-status-box").open=false;await pollReference();await loadNodes();notify("Estado do percurso revisado e preservado no histórico.");});
 onForm("#transform-form",async()=>{if(!active)return;await saveNote(active);const res=await request("/api/reference/transform",{source_id:active.id,kind:$("#transform-kind").value,relation:$("#transform-relation").value,title:$("#transform-title").value,body:$("#transform-body").value,reason:$("#transform-reason").value});$("#transform-form").reset();$(".transform-action-box").open=false;const warnCount=res.prior_objections?.warnings?.length||0;notify(warnCount?`Transformação registrada com ${warnCount} alerta(s) de objeção prévia neste escopo.`:"Transformação registrada e vinculada.");await loadNodes();await openNode(res.node.id);});
 onForm("#node-form",async()=>{const n=await request("/api/nodes",{kind:$("#node-kind").value,title:$("#node-title").value,body:$("#node-body").value});$("#node-form").reset();await loadNodes();await openNode(n.id);});
 onForm("#source-form",async()=>{await request("/api/sources",{label:$("#source-label").value,path:$("#source-path").value});await request("/api/scan",{});await renderSources();await pollReference();notify("Fonte observada. Contextos preparados.");});
 onForm("#link-form",async()=>{await request("/api/links",{source_id:$("#link-source").value,target_id:$("#link-target").value,relation:$("#link-relation").value,state:$("#link-state").value,reason:$("#link-reason").value});$("#link-form").reset();notify("Relação preservada.");});
 $("#scan").addEventListener("click",async()=>{try{await request("/api/scan",{});await renderSources();await pollReference();notify("Fontes observadas. Contextos atualizados.");}catch(ex){notify(ex.message,true);}});
 document.addEventListener("visibilitychange",()=>{if(document.hidden&&active)saveNote(active);});
 window.addEventListener("beforeunload",event=>{if(active?.dirty){rememberNote(active);event.preventDefault();event.returnValue="";}});
 const [view,routeId]=location.hash.slice(1).split("/");
 await request("/api/health");$("#health").textContent="Memória local";
 await loadNodes();
 const selected=routeId||read("continuum.active")||allNodes.find(n=>["open","active"].includes(n.status)&&n.kind!=="experiment")?.id;
 if(selected){try{await openNode(selected);}catch(ex){notify(ex.message,true);}}
 if(questionState.draft.trim()&&(!questionState.submitted?.node_id||questionState.draft.trim()!==questionState.submitted.query))$("#search-form").classList.remove("hidden");
 if(["trajetorias","fontes","laboratorio"].includes(view))show(view);else show("explorar");
 setInterval(()=>{if(!document.hidden){if(active?.dirty&&!active.inflight&&!active.conflict)saveNote(active);pollReference().catch(()=>{});}},12000);
}
document.addEventListener("DOMContentLoaded",()=>init().catch(ex=>notify(ex.message,true)));
