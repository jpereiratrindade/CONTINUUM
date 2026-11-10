"""Auditable lexical retrieval. Lexical similarity is never semantic proof."""
from __future__ import annotations

import math
from collections import Counter
from itertools import combinations

from .core import Lab, words

STOP = set(words("""a as o os um uma uns umas do da dos das de em no na nos nas por para com sem
que quem qual quais como onde quando porque sobre entre sendo foi sao ser ter haver esse essa
este esta esses essas pelo pela seus suas nossa nosso ainda mais menos muito todos cada desde
nao sim ou e and the of to for in from with without an what how why this that those about
seu sua seus suas enquanto agora depois antes nosso estamos trabalhar trabalho projetos projeto
sistema sistemas ideia ideias documento documentos questao questoes vamos fazer sera"""))


def tokens(t: str) -> set[str]:
    return {w for w in words(t) if w not in STOP and len(w) >= 4}


def overlap(a: str, b: str) -> tuple[float, list[str]]:
    x, y = tokens(a), tokens(b)
    shared = sorted(x & y)
    if not x or not y:
        return 0.0, []
    # Conservative, explainable relevance: raw common terms and cosine on token sets.
    return round(len(shared) / math.sqrt(len(x) * len(y)), 3), shared


def _matched_docs(lab: Lab, query: str, limit: int) -> list[dict]:
    ts = [t for t in dict.fromkeys(words(query)) if t not in STOP and len(t) >= 3][:24]
    if not ts:
        return []
    # Entirely constructed from word tokens; FTS syntax injection is not possible.
    expression = " OR ".join('"' + t.replace('"', '') + '"' for t in ts)
    with lab.lock:
        rows = lab.db.execute("""SELECT d.id, d.path, d.title, d.observed_at, d.source_id,
            c.body AS snippet, bm25(chunks_fts,3.0,1.0) AS rank
            FROM chunks_fts JOIN chunks c ON c.id=chunks_fts.rowid
            JOIN documents d ON d.id=c.document_id
            WHERE chunks_fts MATCH ? AND d.present=1 ORDER BY rank LIMIT ?""",
            (expression,limit * 5)).fetchall()
    by_id = {}
    for r in rows:
        if r["id"] not in by_id:
            by_id[r["id"]] = {"id":r["id"],"path":r["path"],"title":r["title"],
                "snippet":r["snippet"][:900],"observed_at":r["observed_at"],
                "source_id":r["source_id"],"match_type":"lexical_fts", "score":round(-r["rank"],3)}
    return list(by_id.values())[:limit]


def _matched_nodes(lab: Lab, query: str, limit: int) -> list[dict]:
    q = tokens(query)
    if not q:
        return []
    with lab.lock:
        rows = lab.db.execute("SELECT n.*,COALESCE(w.text,'') AS working_text FROM nodes n LEFT JOIN working_notes w ON w.node_id=n.id ORDER BY n.updated_at DESC,n.id LIMIT 2000").fetchall()
    matches = []
    for row in rows:
        item = dict(row)
        score = len(q & tokens(item["title"] + " " + item["body"] + " " + item["working_text"])) / len(q)
        if score:
            item["match_type"]="lexical_overlap"
            item["score"] = round(score,3)
            matches.append(item)
    matches.sort(key=lambda x:(-x["score"],x["title"]))
    return matches[:limit]


def discover(lab: Lab, query: str, limit: int = 8) -> dict:
    if not query.strip() or len(query) > 4000:
        raise ValueError("Informe uma questão de até 4000 caracteres")
    docs = _matched_docs(lab,query,limit)
    nodes = _matched_nodes(lab,query,limit)
    # Cross-source tentative connections. This is not an inference of causation.
    possibilities = []
    for a,b in combinations(docs[:8],2):
        if a["source_id"] == b["source_id"]:
            continue
        strength,shared = overlap(a["title"] + " " + a["snippet"],
                                  b["title"] + " " + b["snippet"])
        if len(shared) < 2 or strength < .12:
            continue
        possibilities.append({"from_id":a["id"],"from_title":a["title"],
            "to_id":b["id"],"to_title":b["title"],"score":strength,
            "terms":shared[:10],"state":"candidate","basis":"lexical_overlap",
            "warning":"Correspondência de termos; não representa causalidade nem validação científica."})
    possibilities.sort(key=lambda x:-x["score"])
    absent = not docs and not nodes
    if absent:
        summary = "Não foram recuperados registros correspondentes. Isso não demonstra inexistência de trabalho anterior: o corpus observado pode estar incompleto."
    else:
        summary = f"Foram recuperados {len(docs)} documento(s) e {len(nodes)} elemento(s) de trajetória por correspondência lexical. Os resultados exigem leitura contextual."
    return {"query":query,"summary":summary,"documents":docs,"nodes":nodes,
        "connections":possibilities[:8],"limitations":[
            "Busca lexical: não compreende sozinha o significado dos documentos.",
            "Somente fontes previamente autorizadas e observadas entram no resultado.",
            "A proximidade entre textos não comprova relação causal nem oportunidade realizada."],
        "proposed_steps":["Ler as fontes recuperadas e verificar seus contextos.",
            "Registrar uma questão ou hipótese de investigação, se pertinente.",
            "Produzir um roteiro de continuidade com lacunas e próximas verificações."]}


def markdown_pack(result: dict) -> str:
    query = result["query"].replace("\n", " ")
    lines = ["# Roteiro de continuidade", "",f"**Questão:** {query}", "",
             "**Natureza:** síntese operacional de recuperação; não é uma conclusão científica.","",
             "## Estado da recuperação", "", result["summary"], "", "## Fontes recuperadas", ""]
    if not result["documents"]:
        lines.append("Nenhuma fonte correspondente foi encontrada no corpus observado.")
    for d in result["documents"]:
        lines.extend([f"### {d['title']}","",f"- Documento: `{d['path']}`",
            f"- ID: `{d['id']}`", f"- Observado: {d['observed_at']}",
            "- Base da recuperação: busca lexical indexada (FTS5).", "",
            "> " + d["snippet"].replace("\n", "\n> "), ""])
    lines.extend(["## Questões, hipóteses e decisões relacionadas", ""])
    if not result["nodes"]:
        lines.append("Nenhum elemento estruturado recuperado.")
    for n in result["nodes"]:
        lines.extend([f"- **{n['title']}** ({n['kind']}; {n['status']}; ID `{n['id']}`): {n['body'][:300]}"])
    lines.extend(["", "## Conexões candidatas", ""])
    if not result["connections"]:
        lines.append("Nenhuma conexão interfontes ultrapassou o limiar lexical conservador.")
    for c in result["connections"]:
        lines.append(f"- {c['from_title']} ↔ {c['to_title']} | termos: {', '.join(c['terms'])}. **Apenas candidata.**")
    lines.extend(["", "## Próximos experimentos", ""])
    lines.extend(f"- [ ] {p}" for p in result["proposed_steps"])
    lines.extend(["", "## Incertezas e limites", ""])
    lines.extend(f"- {s}" for s in result["limitations"])
    return "\n".join(lines) + "\n"
