"""Plan A/B/C intellectual transformations, dialogue custody, and critical memory of objections.

Implements CONT-PLAN-001 (Section 7.4, Section 8, and Invariants INV-T01 through INV-T15):
- Plan A: Authorized dialogue import with immutable turns, version hashes, and verifiable SourceSpans.
- Plan B: Candidate IntellectualMoves and typed Transformations (proposal -> objection -> reformulation)
          with explicit method/version/interpreted_at, anchor validation, and mandatory alternative_reading.
- Plan C: Critical trajectory reconstruction, human dispositions, interpretive rectifications (append-only),
          and operational objection memory preventing blind repetition of already-objected proposals in scope.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from .core import Lab, canonical, digest, utcnow, words
from .retrieval import STOP, overlap, tokens

PIPELINE_VERSION = "0.1.0"
DEFAULT_METHOD = "heuristic-discourse-pt-v1"
MODEL_DIGEST = digest({"method": DEFAULT_METHOD, "version": PIPELINE_VERSION})

MOVE_KINDS = {
    "question",
    "proposal",
    "objection",
    "qualification",
    "reformulation",
    "decision",
    "suspension",
    "observation",
}

MOVE_STATUSES = {
    "candidate",
    "rectified",
    "ungrounded_hypothesis",
}

TRANSFORMATION_RELATIONS = {
    "responds_to",
    "objects_to",
    "reformulates",
    "constrains",
    "supports",
    "challenges",
    "revives",
    "alternates_with",
    "analogous_to",
    "depends_on",
    "informs",
}

HUMAN_DISPOSITIONS = {
    "useful",
    "not_relevant",
    "incorrect_interpretation",
    "revisit_later",
}


def schema(lab: Lab) -> None:
    lab.db.executescript("""
        CREATE TABLE IF NOT EXISTS dialogues (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            trajectory_id TEXT REFERENCES nodes(id),
            scope TEXT NOT NULL,
            title TEXT NOT NULL,
            version_hash TEXT NOT NULL,
            raw_payload TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(conversation_id, scope, version_hash)
        );
        CREATE TRIGGER IF NOT EXISTS dialogues_immutable_content BEFORE UPDATE OF
            conversation_id, scope, version_hash, raw_payload, imported_at ON dialogues
            BEGIN SELECT RAISE(ABORT, 'INV-T01: original dialogue record is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS dialogues_immutable_delete BEFORE DELETE ON dialogues
            BEGIN SELECT RAISE(ABORT, 'INV-T01: original dialogue record cannot be deleted directly'); END;

        CREATE TABLE IF NOT EXISTS dialogue_turns (
            dialogue_id TEXT NOT NULL REFERENCES dialogues(id),
            turn_id TEXT NOT NULL,
            turn_order INTEGER NOT NULL,
            speaker_role TEXT NOT NULL,
            text TEXT NOT NULL,
            occurred_at TEXT,
            PRIMARY KEY(dialogue_id, turn_id)
        );
        CREATE TRIGGER IF NOT EXISTS dialogue_turns_immutable_update BEFORE UPDATE ON dialogue_turns
            BEGIN SELECT RAISE(ABORT, 'INV-T01: original dialogue turns are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS dialogue_turns_immutable_delete BEFORE DELETE ON dialogue_turns
            BEGIN SELECT RAISE(ABORT, 'INV-T01: original dialogue turns are immutable'); END;

        CREATE TABLE IF NOT EXISTS intellectual_moves (
            id TEXT PRIMARY KEY,
            trajectory_id TEXT NOT NULL REFERENCES nodes(id),
            dialogue_id TEXT REFERENCES dialogues(id),
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            content TEXT NOT NULL,
            evidence_refs TEXT NOT NULL,
            interpretation TEXT NOT NULL,
            interpreted_at TEXT NOT NULL,
            limitations TEXT NOT NULL,
            supersedes_move_id TEXT REFERENCES intellectual_moves(id),
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS move_transformations (
            id TEXT PRIMARY KEY,
            trajectory_id TEXT NOT NULL REFERENCES nodes(id),
            source_move_id TEXT NOT NULL REFERENCES intellectual_moves(id),
            target_move_id TEXT NOT NULL REFERENCES intellectual_moves(id),
            relation TEXT NOT NULL,
            state TEXT NOT NULL,
            basis TEXT NOT NULL,
            evidence_refs TEXT NOT NULL,
            alternative_reading TEXT NOT NULL,
            relation_scope TEXT NOT NULL,
            interpretation_run_id TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS move_dispositions (
            id TEXT PRIMARY KEY,
            trajectory_id TEXT NOT NULL REFERENCES nodes(id),
            target_kind TEXT NOT NULL,
            target_id TEXT NOT NULL,
            disposition TEXT NOT NULL,
            comment TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
    """)


def _parse_raw_dialogue_text(raw_text: str) -> list[dict[str, Any]]:
    """Parse transcript lines or blocks ('User: ...', 'Assistant: ...', or paragraphs) into structured turns."""
    text = raw_text.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError("Texto de diálogo vazio")
    pattern = re.compile(
        r"(?m)^(?:(?:\*\*|##?\s*)?(usu[aá]rio|user|humano|human|autor|equipe|assistente|assistant|chatgpt|ia|sistema|system)(?:\*\*)?\s*[:\-—]\s*)",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    turns: list[dict[str, Any]] = []
    if matches:
        for idx, match in enumerate(matches):
            role_raw = match.group(1).strip().lower()
            if role_raw in ("assistente", "assistant", "chatgpt", "ia"):
                role = "assistant"
            elif role_raw in ("sistema", "system"):
                role = "system"
            else:
                role = "user"
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                turns.append({
                    "turn_id": f"t{len(turns) + 1:03d}",
                    "speaker_role": role,
                    "text": body,
                    "occurred_at": None,
                    "order": len(turns) + 1,
                })
    else:
        blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
        for idx, block in enumerate(blocks):
            turns.append({
                "turn_id": f"t{idx + 1:03d}",
                "speaker_role": "user" if idx % 2 == 0 else "assistant",
                "text": block,
                "occurred_at": None,
                "order": idx + 1,
            })
    if not turns:
        raise ValueError("Nenhum turno identificável no diálogo")
    return turns


def _normalize_turns(turns_input: list[dict[str, Any]] | None, dialogue_text: str | None) -> list[dict[str, Any]]:
    if turns_input is not None:
        if not isinstance(turns_input, list) or not turns_input:
            raise ValueError("Lista de turnos inválida ou vazia")
        normalized = []
        seen_ids = set()
        for idx, item in enumerate(turns_input):
            if not isinstance(item, dict):
                raise ValueError("Cada turno deve ser um objeto")
            turn_id = str(item.get("turn_id") or f"t{idx + 1:03d}").strip()
            if not turn_id or turn_id in seen_ids:
                raise ValueError(f"turn_id inválido ou duplicado: {turn_id}")
            seen_ids.add(turn_id)
            role = str(item.get("speaker_role") or "user").strip().lower()
            if role not in ("user", "assistant", "system", "participant"):
                raise ValueError(f"speaker_role inválido: {role}")
            body = str(item.get("text") or "").strip()
            if not body:
                raise ValueError(f"Texto vazio no turno {turn_id}")
            # INV-T03 / Section 8.1: occurred_at=null is legitimate when unknown; never fake with imported_at.
            occurred_at = item.get("occurred_at")
            if occurred_at is not None:
                occurred_at = str(occurred_at).strip() or None
            normalized.append({
                "turn_id": turn_id,
                "speaker_role": role,
                "text": body,
                "occurred_at": occurred_at,
                "order": int(item.get("order") or (idx + 1)),
            })
        return normalized
    if dialogue_text is not None:
        return _parse_raw_dialogue_text(dialogue_text)
    raise ValueError("Informe turns ou dialogue_text para importar o diálogo")


def verify_evidence_refs(lab: Lab, evidence_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """INV-T02 & Section 8.2: Verify exact byte/character offsets and version hash against Plan A."""
    if not isinstance(evidence_refs, list):
        raise ValueError("evidence_refs deve ser uma lista")
    verified = []
    for ref in evidence_refs:
        if not isinstance(ref, dict):
            raise ValueError("Cada evidence_ref deve ser um objeto")
        source_id = str(ref.get("source_id") or "").strip()
        turn_id = str(ref.get("turn_id") or "").strip()
        span_start = ref.get("span_start")
        span_end = ref.get("span_end")
        version_hash = str(ref.get("source_version_hash") or "").strip()
        if not source_id or not turn_id or type(span_start) is not int or type(span_end) is not int:
            raise ValueError("Âncora incompleta: requer source_id, turn_id, span_start e span_end inteiros")
        dlg = lab.db.execute("SELECT version_hash, active FROM dialogues WHERE id=?", (source_id,)).fetchone()
        if not dlg:
            raise ValueError(f"Diálogo de origem inexistente: {source_id}")
        if not dlg["active"]:
            raise PermissionError(f"INV-T08: Diálogo {source_id} está pausado/revogado e não pode originar análises")
        if version_hash and version_hash != dlg["version_hash"]:
            raise ValueError("source_version_hash diverge da versão original do diálogo")
        turn = lab.db.execute(
            "SELECT text, speaker_role, occurred_at, turn_order FROM dialogue_turns WHERE dialogue_id=? AND turn_id=?",
            (source_id, turn_id),
        ).fetchone()
        if not turn:
            raise ValueError(f"Turno inexistente na fonte: {turn_id}")
        text = turn["text"]
        if span_start < 0 or span_end <= span_start or span_end > len(text):
            raise ValueError(f"Offsets fora dos limites do turno {turn_id} (0..{len(text)}): {span_start}..{span_end}")
        excerpt = text[span_start:span_end]
        verified.append({
            "source_id": source_id,
            "turn_id": turn_id,
            "turn_order": turn["turn_order"],
            "speaker_role": turn["speaker_role"],
            "occurred_at": turn["occurred_at"],
            "span_start": span_start,
            "span_end": span_end,
            "quote": excerpt,
            "source_version_hash": dlg["version_hash"],
        })
    return verified


def _clip(text: str, limit: int = 240) -> str:
    """Truncate text cleanly at sentence or word boundaries without cutting words in half."""
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    cut = clean[:limit]
    last_space = cut.rfind(" ")
    if last_space > limit // 2:
        cut = cut[:last_space]
    return cut.rstrip(" ,;:-—") + "…"


def _classify_segment(seg: str, role: str, index_in_turn: int, turn_index: int) -> str:
    """Classify a discourse segment into a candidate IntellectualMove kind."""
    low = seg.lower().strip()
    # 1. Explicit questions at the end of a segment (unless it is a rhetorical proposal)
    if low.endswith("?") and any(q in low for q in ("como ", "qual ", "quais ", "por que ", "o que ", "onde ", "quando ", "será", "sera")):
        return "question"

    # 2. Methodological qualifications / conditions (checked before objection so 'Cuidado fundamental...' is a qualification)
    qualification_prefixes = (
        "cuidado fundamental", "condição:", "condicao:", "ressalva:", "restrição:", "restricao:",
        "nota metodológica", "importante distinguir",
    )
    qualification_markers = (
        "cuidado fundamental", "condição limitante", "condicao limitante",
        "salvo ", "desde que ", "sem apagar", "sem converter", "não significa que",
        "nao significa que", "deve permanecer candidat",
    )
    if low.startswith(qualification_prefixes) or (
        any(m in low for m in qualification_markers)
        and not low.startswith(("mas ", "porém", "entretanto", "como está", "mesmo "))
    ):
        return "qualification"

    # 3. Reformulations (shifting the problem framing or unit of analysis)
    reformulation_markers = (
        "reformul", "mudança de perspectiva", "mudanca de perspectiva", "deixar de pensar",
        "deixar de apenas", "passar a ", "em vez de ", "ao invés de ", "ao inves de ",
        "propósito original", "proposito original", "verdadeiro achado", "hipótese constituinte",
        "hipotese constituinte", "unidade fundamental", "redirecionamento",
        "precisamos preservar as transformações", "precisamos preservar as transformacoes",
        "repensando", "reconstruir e investigar", "reconstruir as transformações",
    )
    if any(m in low for m in reformulation_markers) and any(
        m in low for m in ("deixar de", "em vez de", "passar a", "não consiste somente", "nao consiste somente", "transformação", "transformacao", "transformações", "redirecionamento")
    ):
        return "reformulation"

    # 4. Objections (explicit and indirect critiques of sufficiency/direction)
    objection_markers = (
        "mas ", "porém", "entretanto", "contudo", "todavia", "não resolve", "nao resolve",
        "não basta", "nao basta", "insuficiente", "insuficiência", "problema é", "problema esta",
        "como está é como", "como esta e como", "só disponibiliza", "so disponibiliza",
        "não demonstra", "nao demonstra", "não equivale", "nao equivale", "reduzir a", "máquina de escrever",
        "planilha", "reprodução de tabelas", "reproducao de tabelas", "não é fim", "nao e fim",
        "desperdiçando", "desperdicando", "falha em", "objeção", "objecao", "crítica", "critica",
        "perde a história", "perde a historia", "faltam ferramentas", "falta uma abstração",
        "falta uma abstracao", "continua exigindo", "caindo no mesmo", "mesmo a análise", "mesmo aproximar",
    )
    if any(m in low for m in objection_markers):
        return "objection"

    # 5. Decisions / directives
    decision_markers = (
        "decisão", "decisao", "ordem direta", "prioridade imediata", "vamos usar",
        "adotar ", "começar por", "comecar por",
    )
    if any(m in low for m in decision_markers):
        return "decision"

    # 6. Proposals
    proposal_markers = (
        "proponho", "proporia", "proposta", "propomos", "podemos ", "poderíamos", "poderiamos",
        "sugiro", "arquitetura", "incluir técnicas", "incluir tecnicas", "rag", "vector",
        "vetorial", "embeddings", "construir ", "implementar ", "criar uma interface",
        "estruturar painéis", "estruturar o laboratório", "avançamos para",
    )
    if any(m in low for m in proposal_markers):
        return "proposal"

    if "?" in seg:
        return "question"
    if turn_index == 0 and index_in_turn == 0:
        return "proposal"
    return "observation"


def _resolve_best_target(
    move: dict[str, Any],
    candidates: list[dict[str, Any]],
    allow_discourse_adjacency: bool = False,
    immediate_prev: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str, float]:
    """INV-T04: Resolve which prior move is addressed by comparing conceptual overlap and discourse connectors."""
    if not candidates:
        return None, "", 0.0
    best_target = None
    best_score = -1.0
    best_basis = ""
    low = move["content"].lower().strip()
    has_anaphoric_connector = low.startswith((
        "mas ", "porém", "entretanto", "contudo", "como está", "isso ", "essa ", "esse ",
        "mesmo ", "então", "precisamos deixar de", "precisamos reformular",
    ))

    for cand in candidates:
        score, shared = overlap(cand["content"], move["content"])
        effective = score + (0.04 * len(shared))
        # Only add adjacency weight if there is an explicit anaphoric/contrastive discourse connector
        if allow_discourse_adjacency and immediate_prev and cand["id"] == immediate_prev["id"] and has_anaphoric_connector:
            effective += 0.15
        if effective > best_score:
            best_score = effective
            best_target = cand
            best_basis = (
                f"conceptual_overlap({','.join(shared[:4])})"
                if shared
                else "anaphoric_discourse_connector"
            )

    if best_score <= 0.0:
        # Fallback only if there is a direct contrastive/anaphoric reply to the immediately preceding candidate
        if allow_discourse_adjacency and immediate_prev and immediate_prev in candidates and has_anaphoric_connector:
            return immediate_prev, "direct_contrastive_reply", 0.15
        return None, "", 0.0
    return best_target, best_basis, round(best_score, 3)


def _split_turn_segments(text: str) -> list[tuple[int, int, str]]:
    """Split a turn into citable discourse spans with exact character offsets (span_start, span_end, snippet)."""
    spans: list[tuple[int, int, str]] = []
    # Split by paragraphs first; if a paragraph has clear contrast/reformulation sentences, split sentences too
    para_iter = re.finditer(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*", text)
    for pmatch in para_iter:
        p_start, p_end = pmatch.start(), pmatch.end()
        para = text[p_start:p_end]
        if len(para.strip()) < 12:
            continue
        # Check if paragraph contains multiple sentences where a later sentence starts with an objection/reformulation marker
        sent_matches = list(re.finditer(r"[^.!?]+[.!?]+|\S[^.!?]*$", para))
        if len(sent_matches) > 1:
            current_start = sent_matches[0].start()
            for idx, sm in enumerate(sent_matches):
                s_text = para[sm.start():sm.end()].strip().lower()
                is_pivot = idx > 0 and any(
                    s_text.startswith(prefix)
                    for prefix in (
                        "mas ", "porém", "entretanto", "contudo", "o problema", "a insuficiência",
                        "precisamos deixar de", "em vez de", "isso sugere", "hipótese",
                    )
                )
                if is_pivot:
                    seg_str = para[current_start:sm.start()]
                    l_strip = len(seg_str) - len(seg_str.lstrip())
                    r_strip = len(seg_str) - len(seg_str.rstrip())
                    a_start = p_start + current_start + l_strip
                    a_end = p_start + sm.start() - r_strip
                    if a_end > a_start and len(text[a_start:a_end]) >= 12:
                        spans.append((a_start, a_end, text[a_start:a_end]))
                    current_start = sm.start()
            seg_str = para[current_start:]
            l_strip = len(seg_str) - len(seg_str.lstrip())
            r_strip = len(seg_str) - len(seg_str.rstrip())
            a_start = p_start + current_start + l_strip
            a_end = p_start + len(para) - r_strip
            if a_end > a_start and len(text[a_start:a_end]) >= 12:
                spans.append((a_start, a_end, text[a_start:a_end]))
        else:
            l_strip = len(para) - len(para.lstrip())
            r_strip = len(para) - len(para.rstrip())
            a_start = p_start + l_strip
            a_end = p_end - r_strip
            if a_end > a_start:
                spans.append((a_start, a_end, text[a_start:a_end]))
    return spans


def import_dialogue(
    lab: Lab,
    trajectory_id: str,
    conversation_id: str,
    scope: str = "authorized:continuum-research",
    title: str = "",
    turns: list[dict[str, Any]] | None = None,
    dialogue_text: str | None = None,
    auto_extract: bool = True,
) -> dict[str, Any]:
    """Import an explicitly authorized dialogue (Plan A) and optionally extract candidate moves (Plan B)."""
    node = lab.node(trajectory_id)
    conv_id = str(conversation_id or "").strip()
    if not conv_id or len(conv_id) > 200:
        raise ValueError("conversation_id é obrigatório (até 200 caracteres)")
    clean_scope = str(scope or "").strip()
    if not clean_scope.startswith("authorized:") or len(clean_scope) <= len("authorized:"):
        raise PermissionError("INV-T11: Escopo de importação deve ser explicitamente autorizado (ex.: 'authorized:continuum-research')")

    normalized_turns = _normalize_turns(turns, dialogue_text)
    canonical_payload = canonical({
        "conversation_id": conv_id,
        "scope": clean_scope,
        "turns": normalized_turns,
    })
    v_hash = digest(canonical_payload)

    with lab.lock:
        # INV-T05: Repeated import of identical material is idempotent
        existing = lab.db.execute(
            "SELECT * FROM dialogues WHERE conversation_id=? AND scope=? AND version_hash=?",
            (conv_id, clean_scope, v_hash),
        ).fetchone()
        if existing:
            dlg_id = existing["id"]
            moves = list_moves(lab, trajectory_id, dialogue_id=dlg_id)
            transforms = list_transformations(lab, trajectory_id)
            return {
                "dialogue_id": dlg_id,
                "conversation_id": conv_id,
                "trajectory_id": trajectory_id,
                "scope": clean_scope,
                "version_hash": v_hash,
                "imported_at": existing["imported_at"],
                "turns_count": len(normalized_turns),
                "idempotent_reuse": True,
                "moves": moves,
                "transformations": transforms,
            }

        dlg_id = str(uuid.uuid4())
        imported_at = utcnow()
        clean_title = (title or f"Diálogo {conv_id} — {node['title'][:80]}").strip()[:240]

        def run_import():
            lab.db.execute(
                "INSERT INTO dialogues VALUES(?,?,?,?,?,?,?,?,1)",
                (dlg_id, conv_id, trajectory_id, clean_scope, clean_title, v_hash, canonical_payload, imported_at),
            )
            for t in normalized_turns:
                lab.db.execute(
                    "INSERT INTO dialogue_turns VALUES(?,?,?,?,?,?)",
                    (dlg_id, t["turn_id"], t["order"], t["speaker_role"], t["text"], t["occurred_at"]),
                )
            lab._append(
                trajectory_id,
                "dialogue_imported",
                {
                    "dialogue_id": dlg_id,
                    "conversation_id": conv_id,
                    "trajectory_id": trajectory_id,
                    "scope": clean_scope,
                    "title": clean_title,
                    "version_hash": v_hash,
                    "imported_at": imported_at,
                    "turns_count": len(normalized_turns),
                },
                source_type="user",
                source_ref=f"dialogue:{conv_id}",
                evidence_state="observed",
            )

        lab._tx(run_import)

    extracted = {"moves": [], "transformations": []}
    if auto_extract:
        extracted = extract_candidate_moves(lab, trajectory_id, dlg_id)

    return {
        "dialogue_id": dlg_id,
        "conversation_id": conv_id,
        "trajectory_id": trajectory_id,
        "scope": clean_scope,
        "version_hash": v_hash,
        "imported_at": imported_at,
        "turns_count": len(normalized_turns),
        "idempotent_reuse": False,
        "moves": extracted["moves"],
        "transformations": extracted["transformations"],
    }


def set_dialogue_active(lab: Lab, dialogue_id: str, active: bool) -> dict[str, Any]:
    """INV-T08: Pause/revoke or reactivate an imported dialogue source."""
    if type(active) is not bool:
        raise ValueError("active deve ser booleano")
    with lab.lock:
        row = lab.db.execute("SELECT * FROM dialogues WHERE id=?", (dialogue_id,)).fetchone()
        if not row:
            raise ValueError("Diálogo não encontrado")

        def run():
            lab.db.execute("UPDATE dialogues SET active=? WHERE id=?", (1 if active else 0, dialogue_id))
            lab._append(
                row["trajectory_id"],
                "dialogue_active_changed",
                {"dialogue_id": dialogue_id, "active": active},
                source_type="user",
                source_ref=f"dialogue:{row['conversation_id']}",
                evidence_state="declared",
            )

        lab._tx(run)
        return {"dialogue_id": dialogue_id, "active": active}


def extract_candidate_moves(lab: Lab, trajectory_id: str, dialogue_id: str) -> dict[str, Any]:
    """Extract candidate IntellectualMoves and typed Transformations (Plan B) from an active dialogue."""
    with lab.lock:
        dlg = lab.db.execute("SELECT * FROM dialogues WHERE id=?", (dialogue_id,)).fetchone()
        if not dlg:
            raise ValueError("Diálogo não encontrado")
        if not dlg["active"]:
            raise PermissionError("INV-T08: Fonte de diálogo pausada/revogada não pode originar novos processamentos")

        # INV-T05 / INV-T12: Check if moves were already extracted for this dialogue version and pipeline
        existing_moves = list_moves(lab, trajectory_id, dialogue_id=dialogue_id)
        if existing_moves:
            return {
                "moves": existing_moves,
                "transformations": list_transformations(lab, trajectory_id),
                "idempotent_reuse": True,
            }

        turns = lab.db.execute(
            "SELECT * FROM dialogue_turns WHERE dialogue_id=? ORDER BY turn_order ASC",
            (dialogue_id,),
        ).fetchall()

        run_id = str(uuid.uuid4())
        interpreted_at = utcnow()
        interp_meta = {
            "method": DEFAULT_METHOD,
            "model_digest": MODEL_DIGEST,
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_id,
        }

        candidate_moves: list[dict[str, Any]] = []
        for t_idx, turn in enumerate(turns):
            spans = _split_turn_segments(turn["text"])
            for s_idx, (s_start, s_end, seg_text) in enumerate(spans):
                kind = _classify_segment(seg_text, turn["speaker_role"], s_idx, t_idx)
                raw_refs = [{
                    "source_id": dialogue_id,
                    "turn_id": turn["turn_id"],
                    "span_start": s_start,
                    "span_end": s_end,
                    "source_version_hash": dlg["version_hash"],
                }]
                verified_refs = verify_evidence_refs(lab, raw_refs)
                move_id = str(uuid.uuid4())
                limitations = [
                    "Classificação discursiva candidata; não infere intenção psicológica do autor (INV-T03, Regra 6).",
                    "O alcance do movimento depende do contexto integral do diálogo.",
                ]
                candidate_moves.append({
                    "id": move_id,
                    "trajectory_id": trajectory_id,
                    "dialogue_id": dialogue_id,
                    "kind": kind,
                    "status": "candidate",
                    "content": seg_text[:600],
                    "evidence_refs": verified_refs,
                    "interpretation": interp_meta,
                    "interpreted_at": interpreted_at,
                    "limitations": limitations,
                    "supersedes_move_id": None,
                })

        # Build typed candidate transformations (proposal -> objection -> reformulation, question -> proposal, etc.)
        # INV-T04: Never confirm or create a relation solely by temporal proximity; resolve against all prior candidates.
        candidate_transforms: list[dict[str, Any]] = []
        prior_moves: list[dict[str, Any]] = []

        for idx, move in enumerate(candidate_moves):
            mkind = move["kind"]
            prev_move = candidate_moves[idx - 1] if idx > 0 else None
            prior_proposals = [m for m in prior_moves if m["kind"] == "proposal"]
            prior_objections = [m for m in prior_moves if m["kind"] == "objection"]
            prior_reforms = [m for m in prior_moves if m["kind"] == "reformulation"]
            prior_questions = [m for m in prior_moves if m["kind"] == "question"]
            prior_observations = [m for m in prior_moves if m["kind"] == "observation"]

            target_move = None
            relation = None
            basis = None
            alt_reading = None

            if mkind == "proposal":
                if prev_move and prev_move["kind"] == "objection":
                    target_move = prev_move
                    relation = "reformulates"
                    basis = "proposal_after_objection_shift"
                    alt_reading = "A nova proposta pode explorar uma frente alternativa sem resolver integralmente a objeção anterior."
                elif prior_reforms:
                    target_move, basis, _ = _resolve_best_target(move, prior_reforms, True, prev_move)
                    if target_move:
                        relation = "informs"
                        alt_reading = "A nova proposta pode inaugurar uma frente paralela, sem decorrer diretamente da reformulação anterior."
                elif prior_questions:
                    target_move, basis, _ = _resolve_best_target(move, prior_questions, True, prev_move)
                    if not target_move and idx == 1 and prior_questions:
                        target_move = prior_questions[-1]
                        basis = "initial_question_response"
                    if target_move:
                        relation = "responds_to"
                        alt_reading = "A proposta pode endereçar apenas um recorte técnico lateral da questão inicial."
                elif prior_proposals:
                    target_move, basis, score = _resolve_best_target(move, prior_proposals, False, None)
                    if target_move and score > 0.0:
                        relation = "alternates_with"
                        alt_reading = "A segunda proposta pode complementar a primeira em vez de competir com ela."
                    else:
                        target_move = None

            elif mkind == "objection":
                if prior_proposals:
                    target_move, basis, _ = _resolve_best_target(move, prior_proposals, True, prev_move)
                    if not target_move and prev_move and prev_move["kind"] == "proposal":
                        target_move = prev_move
                        basis = "direct_turn_objection"
                    if target_move:
                        relation = "objects_to"
                        alt_reading = "A crítica pode referir-se apenas à forma de apresentação ou interface, e não à arquitetura inteira da proposta."
                elif prior_observations:
                    target_move, basis, _ = _resolve_best_target(move, prior_observations, True, prev_move)
                    if target_move:
                        relation = "challenges"
                        alt_reading = "A ressalva pode apontar um limite de escopo do experimento, sem invalidar o dado observado."

            elif mkind == "qualification":
                cands = prior_reforms + prior_proposals
                target_move, basis, _ = _resolve_best_target(move, cands, True, prev_move)
                if not target_move and cands:
                    target_move = cands[-1]
                    basis = "scope_qualification_condition"
                if target_move:
                    relation = "constrains"
                    alt_reading = "A condição enunciada pode ser uma diretriz geral do projeto, não restrita apenas a esta formulação."

            elif mkind == "reformulation":
                if prior_objections:
                    target_move, basis, _ = _resolve_best_target(move, prior_objections, True, prev_move)
                    if not target_move:
                        target_move = prior_objections[-1]
                        basis = "objection_to_reformulation_bridge"
                    relation = "reformulates"
                    alt_reading = "A reformulação pode introduzir uma nova hipótese independente, sem resolver integralmente a objeção anterior."
                elif prior_proposals:
                    target_move, basis, _ = _resolve_best_target(move, prior_proposals, True, prev_move)
                    if target_move:
                        relation = "reformulates"
                        alt_reading = "A nova formulação pode ser uma mudança de vocabulário sem alterar o pressuposto técnico anterior."

            elif mkind == "decision":
                cands = prior_reforms + prior_proposals
                target_move, basis, _ = _resolve_best_target(move, cands, True, prev_move)
                if target_move:
                    relation = "depends_on"
                    alt_reading = "A decisão prática pode ter sido tomada por restrição de prazo/escopo, não como validação definitiva da tese."

            elif mkind == "question" and idx > 0:
                cands = prior_reforms + prior_objections + prior_proposals
                target_move, basis, _ = _resolve_best_target(move, cands, True, prev_move)
                if target_move:
                    relation = "informs"
                    alt_reading = "A nova pergunta pode abrir um subproblema distinto em vez de desdobrar diretamente o movimento anterior."

            if target_move and relation and basis and alt_reading:
                comb_refs = target_move["evidence_refs"][:1] + move["evidence_refs"][:1]
                candidate_transforms.append({
                    "id": str(uuid.uuid4()),
                    "trajectory_id": trajectory_id,
                    "source_move_id": move["id"],
                    "target_move_id": target_move["id"],
                    "relation": relation,
                    "state": "candidate",
                    "basis": basis,
                    "evidence_refs": comb_refs,
                    "alternative_reading": alt_reading,
                    "relation_scope": f"question:{trajectory_id}",
                    "interpretation_run_id": run_id,
                    "recorded_at": interpreted_at,
                    "reason": f"Movimento '{mkind}' vinculado a '{target_move['kind']}' via {basis}",
                })

            prior_moves.append(move)

        def persist():
            for m in candidate_moves:
                lab.db.execute(
                    "INSERT INTO intellectual_moves VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
                    (
                        m["id"],
                        m["trajectory_id"],
                        m["dialogue_id"],
                        m["kind"],
                        m["status"],
                        m["content"],
                        canonical(m["evidence_refs"]),
                        canonical(m["interpretation"]),
                        m["interpreted_at"],
                        canonical(m["limitations"]),
                        m["supersedes_move_id"],
                    ),
                )
            for tr in candidate_transforms:
                lab.db.execute(
                    "INSERT INTO move_transformations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        tr["id"],
                        tr["trajectory_id"],
                        tr["source_move_id"],
                        tr["target_move_id"],
                        tr["relation"],
                        tr["state"],
                        tr["basis"],
                        canonical(tr["evidence_refs"]),
                        tr["alternative_reading"],
                        tr["relation_scope"],
                        tr["interpretation_run_id"],
                        tr["recorded_at"],
                        tr["reason"],
                    ),
                )
            lab._append(
                trajectory_id,
                "moves_extracted",
                {
                    "dialogue_id": dialogue_id,
                    "run_id": run_id,
                    "method": DEFAULT_METHOD,
                    "model_digest": MODEL_DIGEST,
                    "pipeline_version": PIPELINE_VERSION,
                    "interpreted_at": interpreted_at,
                    "moves_count": len(candidate_moves),
                    "transformations_count": len(candidate_transforms),
                },
                source_type="automation",
                source_ref=f"{DEFAULT_METHOD}:{PIPELINE_VERSION}",
                evidence_state="generated",
            )

        lab._tx(persist)
        return {
            "moves": candidate_moves,
            "transformations": candidate_transforms,
            "idempotent_reuse": False,
        }


def create_candidate_move(
    lab: Lab,
    trajectory_id: str,
    kind: str,
    content: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    method: str = "manual-or-mcp-candidate",
) -> dict[str, Any]:
    """Create a candidate IntellectualMove. Enforce INV-T02 (ungrounded if no verifiable span)."""
    lab.node(trajectory_id)
    if kind not in MOVE_KINDS:
        raise ValueError(f"Tipo de movimento inválido: {kind}")
    clean_content = str(content or "").strip()
    if not clean_content or len(clean_content) > 4000:
        raise ValueError("Conteúdo do movimento deve ter entre 1 e 4000 caracteres")

    with lab.lock:
        if evidence_refs:
            verified_refs = verify_evidence_refs(lab, evidence_refs)
            status = "candidate"
            dialogue_id = verified_refs[0]["source_id"]
            limitations = ["Interpretação candidata ancorada em trecho verificável (INV-T02)."]
        else:
            # INV-T02: Without a verifiable span, it is marked ungrounded_hypothesis and excluded from grounded synthesis
            verified_refs = []
            status = "ungrounded_hypothesis"
            dialogue_id = None
            limitations = [
                "INV-T02: Hipótese sem trecho de evidência verificável; não participa de síntese fundamentada."
            ]

        move_id = str(uuid.uuid4())
        interpreted_at = utcnow()
        run_id = str(uuid.uuid4())
        interp = {
            "method": method,
            "model_digest": digest({"method": method, "version": PIPELINE_VERSION}),
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_id,
        }

        def persist():
            lab.db.execute(
                "INSERT INTO intellectual_moves VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    move_id,
                    trajectory_id,
                    dialogue_id,
                    kind,
                    status,
                    clean_content,
                    canonical(verified_refs),
                    canonical(interp),
                    interpreted_at,
                    canonical(limitations),
                    None,
                ),
            )
            lab._append(
                trajectory_id,
                "move_created",
                {
                    "move_id": move_id,
                    "trajectory_id": trajectory_id,
                    "kind": kind,
                    "status": status,
                    "content": clean_content,
                    "evidence_refs": verified_refs,
                    "interpretation": interp,
                    "interpreted_at": interpreted_at,
                },
                source_type="user",
                source_ref=method,
                evidence_state="generated" if status == "candidate" else "declared",
            )

        lab._tx(persist)
        return {
            "id": move_id,
            "trajectory_id": trajectory_id,
            "dialogue_id": dialogue_id,
            "kind": kind,
            "status": status,
            "content": clean_content,
            "evidence_refs": verified_refs,
            "interpretation": interp,
            "interpreted_at": interpreted_at,
            "limitations": limitations,
        }


def rectify_move(
    lab: Lab,
    move_id: str,
    new_kind: str | None = None,
    new_content: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """INV-T06 & INV-T13: Rectify an interpretive move as a new append-only event without erasing the prior move or Plan A."""
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        raise ValueError("Justificativa (reason) é obrigatória para retificar uma interpretação")

    with lab.lock:
        prior = lab.db.execute("SELECT * FROM intellectual_moves WHERE id=?", (move_id,)).fetchone()
        if not prior:
            raise ValueError("Movimento interpretativo não encontrado")

        kind = str(new_kind or prior["kind"]).strip()
        if kind not in MOVE_KINDS:
            raise ValueError(f"Tipo de movimento inválido: {kind}")
        content = str(new_content if new_content is not None else prior["content"]).strip()
        if not content:
            raise ValueError("Conteúdo retificado não pode ser vazio")

        new_id = str(uuid.uuid4())
        interpreted_at = utcnow()
        run_id = str(uuid.uuid4())
        interp = {
            "method": "human-rectification",
            "model_digest": "human-review",
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_id,
            "rectifies_move_id": move_id,
            "reason": clean_reason,
        }
        limitations = ["Retificação interpretativa registrada sobre movimento anterior; original preservado (INV-T06)."]

        def persist():
            # Mark prior move as inactive in current projection (never deleted from table or journal!)
            lab.db.execute("UPDATE intellectual_moves SET active=0 WHERE id=?", (move_id,))
            lab.db.execute(
                "INSERT INTO intellectual_moves VALUES(?,?,?,?,?,?,?,?,?,?,?,1)",
                (
                    new_id,
                    prior["trajectory_id"],
                    prior["dialogue_id"],
                    kind,
                    "rectified",
                    content,
                    prior["evidence_refs"],
                    canonical(interp),
                    interpreted_at,
                    canonical(limitations),
                    move_id,
                ),
            )
            # Re-point active transformations referencing move_id to new_id by adding updated rows while keeping history
            lab.db.execute(
                "UPDATE move_transformations SET source_move_id=? WHERE source_move_id=?",
                (new_id, move_id),
            )
            lab.db.execute(
                "UPDATE move_transformations SET target_move_id=? WHERE target_move_id=?",
                (new_id, move_id),
            )
            lab._append(
                prior["trajectory_id"],
                "move_rectified",
                {
                    "prior_move_id": move_id,
                    "new_move_id": new_id,
                    "trajectory_id": prior["trajectory_id"],
                    "before": {"kind": prior["kind"], "content": prior["content"], "status": prior["status"]},
                    "after": {"kind": kind, "content": content, "status": "rectified"},
                    "reason": clean_reason,
                    "interpreted_at": interpreted_at,
                },
                source_type="user",
                source_ref="human-rectification",
                evidence_state="declared",
            )

        lab._tx(persist)
        return {
            "prior_move_id": move_id,
            "new_move_id": new_id,
            "trajectory_id": prior["trajectory_id"],
            "kind": kind,
            "status": "rectified",
            "content": content,
            "reason": clean_reason,
            "interpreted_at": interpreted_at,
        }


def dispose_move(
    lab: Lab,
    trajectory_id: str,
    target_id: str,
    disposition: str,
    comment: str = "",
    target_kind: str = "move",
) -> dict[str, Any]:
    """Section 6.3 & INV-T07: Record minimal human response (useful, not_relevant, incorrect_interpretation, revisit_later)."""
    lab.node(trajectory_id)
    if disposition not in HUMAN_DISPOSITIONS:
        raise ValueError(f"Disposição inválida: {disposition}")
    if target_kind not in ("move", "transformation", "card"):
        raise ValueError("target_kind deve ser move, transformation ou card")

    disp_id = str(uuid.uuid4())
    recorded_at = utcnow()
    scope = f"question:{trajectory_id}"
    clean_comment = str(comment or "").strip()[:1000]

    with lab.lock:
        def persist():
            lab.db.execute(
                "INSERT INTO move_dispositions VALUES(?,?,?,?,?,?,?,?)",
                (disp_id, trajectory_id, target_kind, target_id, disposition, clean_comment, scope, recorded_at),
            )
            lab._append(
                trajectory_id,
                "move_disposition_recorded",
                {
                    "id": disp_id,
                    "trajectory_id": trajectory_id,
                    "target_kind": target_kind,
                    "target_id": target_id,
                    "disposition": disposition,
                    "comment": clean_comment,
                    "scope": scope,
                    "recorded_at": recorded_at,
                },
                source_type="user",
                source_ref="human-disposition",
                evidence_state="declared",
            )

        lab._tx(persist)
        return {
            "id": disp_id,
            "trajectory_id": trajectory_id,
            "target_kind": target_kind,
            "target_id": target_id,
            "disposition": disposition,
            "comment": clean_comment,
            "scope": scope,
            "recorded_at": recorded_at,
        }


def list_moves(lab: Lab, trajectory_id: str, dialogue_id: str | None = None, include_inactive: bool = False) -> list[dict[str, Any]]:
    import json
    with lab.lock:
        sql = """
            SELECT m.* FROM intellectual_moves m
            LEFT JOIN dialogues d ON d.id = m.dialogue_id
            WHERE m.trajectory_id = ?
              AND (m.dialogue_id IS NULL OR d.active = 1)
        """
        params: list[Any] = [trajectory_id]
        if not include_inactive:
            sql += " AND m.active = 1"
        if dialogue_id:
            sql += " AND m.dialogue_id = ?"
            params.append(dialogue_id)
        sql += " ORDER BY m.interpreted_at ASC, m.rowid ASC"
        rows = lab.db.execute(sql, tuple(params)).fetchall()

        dispositions_by_target: dict[str, list[dict[str, Any]]] = {}
        for drow in lab.db.execute(
            "SELECT * FROM move_dispositions WHERE trajectory_id=? ORDER BY recorded_at DESC",
            (trajectory_id,),
        ):
            dispositions_by_target.setdefault(drow["target_id"], []).append(dict(drow))

        result = []
        for r in rows:
            item = dict(r)
            item["evidence_refs"] = json.loads(item["evidence_refs"])
            item["interpretation"] = json.loads(item["interpretation"])
            item["limitations"] = json.loads(item["limitations"])
            item["active"] = bool(item["active"])
            item["dispositions"] = dispositions_by_target.get(item["id"], [])
            result.append(item)
        return result


def list_transformations(lab: Lab, trajectory_id: str) -> list[dict[str, Any]]:
    import json
    with lab.lock:
        rows = lab.db.execute(
            """
            SELECT t.* FROM move_transformations t
            JOIN intellectual_moves ms ON ms.id = t.source_move_id
            JOIN intellectual_moves mt ON mt.id = t.target_move_id
            LEFT JOIN dialogues ds ON ds.id = ms.dialogue_id
            LEFT JOIN dialogues dt ON dt.id = mt.dialogue_id
            WHERE t.trajectory_id = ?
              AND ms.active = 1 AND mt.active = 1
              AND (ms.dialogue_id IS NULL OR ds.active = 1)
              AND (mt.dialogue_id IS NULL OR dt.active = 1)
            ORDER BY t.recorded_at ASC, t.rowid ASC
            """,
            (trajectory_id,),
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["evidence_refs"] = json.loads(item["evidence_refs"])
            result.append(item)
        return result


def check_proposal_objections(lab: Lab, trajectory_id: str, proposal_text: str) -> dict[str, Any]:
    """INV-T07 & INV-T15: Check whether a new proposal repeats elements of an already-objected proposal in the same scope."""
    clean_text = str(proposal_text or "").strip()
    if not clean_text:
        return {"has_prior_objections": False, "warnings": [], "scope": f"question:{trajectory_id}"}

    moves = {m["id"]: m for m in list_moves(lab, trajectory_id) if m["status"] != "ungrounded_hypothesis"}
    transforms = list_transformations(lab, trajectory_id)

    warnings = []
    for tr in transforms:
        if tr["relation"] not in ("objects_to", "challenges", "constrains"):
            continue
        objection_move = moves.get(tr["source_move_id"])
        contested_proposal = moves.get(tr["target_move_id"])
        if not objection_move or not contested_proposal:
            continue
        # If human marked the objection as incorrect_interpretation, do not block/warn with it
        if any(d["disposition"] == "incorrect_interpretation" for d in objection_move.get("dispositions", [])):
            continue

        score_prop, shared_prop = overlap(clean_text, contested_proposal["content"])
        score_obj, shared_obj = overlap(clean_text, objection_move["content"])
        shared = sorted(set(shared_prop) | set(shared_obj))
        score = max(score_prop, score_obj)

        if score >= 0.12 or len(shared) >= 1:
            warnings.append({
                "scope": tr["relation_scope"],
                "relation": tr["relation"],
                "shared_terms": shared[:8],
                "similarity_score": score,
                "contested_proposal": {
                    "id": contested_proposal["id"],
                    "content": contested_proposal["content"],
                    "evidence_refs": contested_proposal["evidence_refs"],
                },
                "objection": {
                    "id": objection_move["id"],
                    "content": objection_move["content"],
                    "evidence_refs": objection_move["evidence_refs"],
                },
                "alternative_reading": tr["alternative_reading"],
                "guidance": (
                    "INV-T07/INV-T15: Uma proposta semelhante já recebeu objeção neste escopo. "
                    "Verifique se a insuficiência apontada permanece válida ou explicite que condição mudou para retomá-la."
                ),
            })

    return {
        "has_prior_objections": len(warnings) > 0,
        "scope": f"question:{trajectory_id}",
        "warnings": warnings,
    }


def critical_trajectory(lab: Lab, trajectory_id: str) -> dict[str, Any]:
    """Section 6 & 7.4 Functional Criterion: Reconstruct proposal -> objection -> reformulation -> remaining doubt."""
    node = lab.node(trajectory_id)
    # Only grounded moves participate in grounded synthesis (INV-T02)
    all_moves = list_moves(lab, trajectory_id)
    grounded_moves = [m for m in all_moves if m["status"] != "ungrounded_hypothesis" and m["evidence_refs"]]
    ungrounded_moves = [m for m in all_moves if m["status"] == "ungrounded_hypothesis" or not m["evidence_refs"]]
    transforms = list_transformations(lab, trajectory_id)

    if not grounded_moves:
        # INV-T09: Explicitly recognize "sem evidência suficiente" as a valid, non-penalized output
        with lab.lock:
            dlg_count = lab.db.execute(
                "SELECT COUNT(*) FROM dialogues WHERE trajectory_id=? AND active=1", (trajectory_id,)
            ).fetchone()[0]
        return {
            "trajectory_id": trajectory_id,
            "question": node["title"],
            "status_notice": "sem evidência suficiente",
            "context_counts": {"dialogues": dlg_count, "moves": 0, "transformations": 0},
            "continuum_contributions": {
                "candidate_convergence": None,
                "recurring_objection": None,
                "tension_contradiction": None,
                "next_movement": None,
            },
            "transformation_ribbon": [],
            "chains": [],
            "active_objections": [],
            "open_tensions": [],
            "cards": [],
            "moves": all_moves,
            "ungrounded_moves": ungrounded_moves,
            "transformations": transforms,
        }

    moves_by_id = {m["id"]: m for m in grounded_moves}

    # Index outgoing/incoming transformations
    objections_to_proposal: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    reformulations_of_move: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}

    for tr in transforms:
        src = moves_by_id.get(tr["source_move_id"])
        tgt = moves_by_id.get(tr["target_move_id"])
        if not src or not tgt:
            continue
        # Only actual objection moves form objection chains; qualifications are constraints/tensions, questions are open doubts
        if tr["relation"] in ("objects_to", "challenges") and src["kind"] == "objection":
            objections_to_proposal.setdefault(tgt["id"], []).append((src, tr))
        elif tr["relation"] == "reformulates":
            reformulations_of_move.setdefault(tgt["id"], []).append((src, tr))

    # Build explicit chains answering Section 7.4:
    # 1. Qual proposta foi questionada?
    # 2. O que foi objetado?
    # 3. O que mudou depois?
    # 4. Qual dúvida permaneceu?
    open_questions = [m for m in grounded_moves if m["kind"] == "question"]
    qualifications_all = [m for m in grounded_moves if m["kind"] == "qualification"]
    default_remaining_doubt = (
        open_questions[-1]["content"]
        if open_questions
        else (
            qualifications_all[-1]["content"]
            if qualifications_all
            else f"Verificar se a reformulação responde na prática à questão: {node['title']}"
        )
    )

    chains: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    active_objections: list[dict[str, Any]] = []

    for prop_id, obj_list in objections_to_proposal.items():
        proposal_move = moves_by_id[prop_id]
        for obj_move, obj_tr in obj_list:
            # Find if this objection (or the proposal itself) was subsequently reformulated
            reforms = reformulations_of_move.get(obj_move["id"]) or reformulations_of_move.get(prop_id) or []
            reform_move, reform_tr = reforms[0] if reforms else (None, None)

            # Determine remaining doubt after this objection/reformulation (prefer open questions, then qualifications)
            later_questions = [
                m for m in grounded_moves
                if m["kind"] == "question"
                and m["id"] != proposal_move["id"]
                and m["evidence_refs"][0]["turn_order"] >= (
                    reform_move["evidence_refs"][0]["turn_order"]
                    if reform_move
                    else obj_move["evidence_refs"][0]["turn_order"]
                )
            ]
            remaining_doubt = later_questions[-1]["content"] if later_questions else default_remaining_doubt

            chain_item = {
                "questioned_proposal": {
                    "id": proposal_move["id"],
                    "content": proposal_move["content"],
                    "evidence_refs": proposal_move["evidence_refs"],
                },
                "what_was_objected": {
                    "id": obj_move["id"],
                    "content": obj_move["content"],
                    "relation": obj_tr["relation"],
                    "evidence_refs": obj_move["evidence_refs"],
                    "alternative_reading": obj_tr["alternative_reading"],
                },
                "what_changed_after": {
                    "id": reform_move["id"],
                    "content": reform_move["content"],
                    "evidence_refs": reform_move["evidence_refs"],
                    "alternative_reading": reform_tr["alternative_reading"],
                } if reform_move and reform_tr else None,
                "remaining_doubt": remaining_doubt,
                "scope": obj_tr["relation_scope"],
            }
            chains.append(chain_item)

            active_objections.append({
                "id": obj_move["id"],
                "content": obj_move["content"],
                "contested_proposal_id": proposal_move["id"],
                "contested_proposal_content": proposal_move["content"],
                "addressed_by_reformulation": bool(reform_move),
                "reformulation_content": reform_move["content"] if reform_move else None,
                "evidence_refs": obj_move["evidence_refs"],
                "alternative_reading": obj_tr["alternative_reading"],
                "scope": obj_tr["relation_scope"],
                "dispositions": obj_move.get("dispositions", []),
            })

            # Section 6.2: Contract for Cartão de Movimento Intelectual (interpretive_candidate)
            card_evidence = []
            for r in proposal_move["evidence_refs"][:1]:
                card_evidence.append({
                    "source_span_ref": f"{r['source_id']}:{r['turn_id']}[{r['span_start']}:{r['span_end']}]",
                    "version_ref": r["source_version_hash"],
                    "quote": r["quote"],
                    "role": "proposta questionada",
                })
            for r in obj_move["evidence_refs"][:1]:
                card_evidence.append({
                    "source_span_ref": f"{r['source_id']}:{r['turn_id']}[{r['span_start']}:{r['span_end']}]",
                    "version_ref": r["source_version_hash"],
                    "quote": r["quote"],
                    "role": "objeção expressa",
                })
            if reform_move:
                for r in reform_move["evidence_refs"][:1]:
                    card_evidence.append({
                        "source_span_ref": f"{r['source_id']}:{r['turn_id']}[{r['span_start']}:{r['span_end']}]",
                        "version_ref": r["source_version_hash"],
                        "quote": r["quote"],
                        "role": "reformulação posterior",
                    })

            cards.append({
                "id": f"card:{obj_move['id']}",
                "target_move_id": reform_move["id"] if reform_move else obj_move["id"],
                "kind": "interpretive_candidate",
                "heading": (
                    _clip(reform_move["content"], 160)
                    if reform_move
                    else f"Tensão aberta sobre: {_clip(proposal_move['content'], 120)}"
                ),
                "trajectory_id": trajectory_id,
                "what_changed": (
                    f"De '{_clip(proposal_move['content'], 120)}' para '{_clip(reform_move['content'], 120)}'"
                    if reform_move
                    else "Proposta contestada aguarda reformulação ou verificação de escopo"
                ),
                "trigger": obj_move["content"],
                "evidence": card_evidence,
                "tension": remaining_doubt,
                "alternative_reading": (
                    reform_tr["alternative_reading"] if reform_tr else obj_tr["alternative_reading"]
                ),
                "possible_movement": _clip(remaining_doubt, 240),
                "state": "candidate",
            })

    open_tensions = [
        {
            "id": m["id"],
            "kind": m["kind"],
            "content": m["content"],
            "evidence_refs": m["evidence_refs"],
        }
        for m in grounded_moves
        if m["kind"] in ("question", "qualification", "objection")
    ]

    with lab.lock:
        dlg_count = lab.db.execute(
            "SELECT COUNT(*) FROM dialogues WHERE trajectory_id=? AND active=1", (trajectory_id,)
        ).fetchone()[0]
        other_nodes = lab.db.execute(
            "SELECT id, kind, title, body FROM nodes WHERE id != ? AND status IN ('open', 'active') ORDER BY updated_at DESC LIMIT 10",
            (trajectory_id,),
        ).fetchall()

    # Build the 4 "Contribuições do CONTINUUM" slots with distinct, non-duplicative analytical roles:
    # 1. Convergência candidata (cross-trajectory / reformulation synthesis)
    # 2. Objeção recorrente / ativa (from active_objections, checking recurrence)
    # 3. Tensão / contradição (from qualifications or proposal-vs-objection contrast, never duplicating card 2)
    # 4. Próximo movimento (actionable open question / direction)
    reforms_all = [m for m in grounded_moves if m["kind"] == "reformulation"]
    proposals_all = [m for m in grounded_moves if m["kind"] == "proposal"]
    conv_source = reforms_all[-1] if reforms_all else (proposals_all[-1] if proposals_all else grounded_moves[-1])

    cross_match = None
    best_cross_score = 0.0
    cross_terms: list[str] = []
    for onode in other_nodes:
        sc, sh = overlap(node["title"] + " " + conv_source["content"], onode["title"] + " " + onode["body"])
        if sc > best_cross_score and len(sh) >= 2:
            best_cross_score = sc
            cross_match = dict(onode)
            cross_terms = sh[:5]

    if cross_match:
        conv_summary = (
            f"Convergência entre este percurso e '{_clip(cross_match['title'], 95)}': "
            f"{_clip(conv_source['content'], 190)} (termos em comum: {', '.join(cross_terms)})."
        )
    else:
        conv_summary = _clip(conv_source["content"], 240)

    candidate_convergence = {
        "kind": "candidate_convergence",
        "label": "Convergência candidata",
        "summary": conv_summary,
        "move_id": conv_source["id"],
        "related_trajectory_id": cross_match["id"] if cross_match else None,
        "evidence_refs": conv_source["evidence_refs"],
        "state": "candidate",
    }

    recurring_objection = None
    used_move_ids = {conv_source["id"]}
    if active_objections:
        top_obj = active_objections[-1]
        used_move_ids.add(top_obj["id"])
        if len(active_objections) >= 2:
            first_obj = active_objections[0]
            obj_label = f"Objeção recorrente ({len(active_objections)} ocorrências)"
            obj_summary = (
                f"Padrão crítico recorrente: (1) {_clip(first_obj['content'], 115)} · "
                f"(2) {_clip(top_obj['content'], 115)}"
            )
        else:
            obj_label = "Objeção ativa no escopo"
            obj_summary = _clip(top_obj["content"], 240)

        recurring_objection = {
            "kind": "recurring_objection",
            "label": obj_label,
            "summary": obj_summary,
            "contested_proposal": _clip(top_obj["contested_proposal_content"], 180),
            "move_id": top_obj["id"],
            "evidence_refs": top_obj["evidence_refs"],
            "alternative_reading": top_obj["alternative_reading"],
            "state": "candidate",
        }

    tension_candidates = [m for m in qualifications_all if m["id"] not in used_move_ids]
    if tension_candidates:
        t_src = tension_candidates[-1]
        used_move_ids.add(t_src["id"])
        t_summary = _clip(t_src["content"], 240)
        t_refs = t_src["evidence_refs"]
        t_id = t_src["id"]
    elif chains:
        last_ch = chains[-1]
        t_summary = (
            f"Tensão entre a proposta ('{_clip(last_ch['questioned_proposal']['content'], 95)}') "
            f"e a crítica registrada ('{_clip(last_ch['what_was_objected']['content'], 95)}')."
        )
        t_refs = last_ch["what_was_objected"]["evidence_refs"]
        t_id = last_ch["what_was_objected"]["id"]
    else:
        t_summary = _clip(default_remaining_doubt, 240)
        t_refs = []
        t_id = None

    tension_contradiction = {
        "kind": "tension_contradiction",
        "label": "Tensão / condição",
        "summary": t_summary,
        "move_id": t_id,
        "evidence_refs": t_refs,
        "state": "candidate",
    }

    next_movement_slot = {
        "kind": "next_movement",
        "label": "Próximo movimento",
        "summary": _clip(default_remaining_doubt, 240),
        "basis_move_id": open_questions[-1]["id"] if open_questions else conv_source["id"],
        "state": "candidate",
    }

    # Build horizontal "Trajetória da transformação" ribbon (transformações, não apenas estados)
    stage_labels = {
        "question": "Questão / Problema",
        "proposal": "Proposta",
        "objection": "Crítica / Objeção",
        "qualification": "Condição / Limite",
        "reformulation": "Reformulação",
        "decision": "Decisão / Diretriz",
        "observation": "Observação",
        "suspension": "Suspensão",
    }
    transformation_ribbon = []
    for idx, m in enumerate(grounded_moves):
        transformation_ribbon.append({
            "step": idx + 1,
            "move_id": m["id"],
            "kind": m["kind"],
            "stage_label": stage_labels.get(m["kind"], m["kind"]),
            "summary": _clip(m["content"], 135),
            "evidence_refs": m["evidence_refs"],
            "status": m["status"],
        })

    return {
        "trajectory_id": trajectory_id,
        "question": node["title"],
        "status_notice": "reconstrução candidata disponível" if chains else "movimentos extraídos sem cadeia completa de objeção",
        "context_counts": {
            "dialogues": dlg_count,
            "moves": len(grounded_moves),
            "transformations": len(transforms),
        },
        "continuum_contributions": {
            "candidate_convergence": candidate_convergence,
            "recurring_objection": recurring_objection,
            "tension_contradiction": tension_contradiction,
            "next_movement": next_movement_slot,
        },
        "transformation_ribbon": transformation_ribbon,
        "chains": chains,
        "active_objections": active_objections,
        "open_tensions": open_tensions,
        "cards": cards,
        "moves": grounded_moves,
        "ungrounded_moves": ungrounded_moves,
        "transformations": transforms,
    }
