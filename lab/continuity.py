"""Persistent reference spaces and automatic, explicitly lexical context packages."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unicodedata

from .core import canonical, digest, utcnow
from .retrieval import _matched_docs, _matched_nodes, overlap

ENGINE = 'lexical-reference-v1'


def schema(lab):
    lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS working_notes (
            node_id TEXT PRIMARY KEY REFERENCES nodes(id),
            text TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS continuity_packages (
            event_id TEXT PRIMARY KEY REFERENCES events(event_id),
            node_id TEXT NOT NULL REFERENCES nodes(id), basis_hash TEXT NOT NULL,
            payload TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_versions_document ON document_versions(document_id);
        CREATE INDEX IF NOT EXISTS idx_events_kind_seq ON events(kind,seq);
        CREATE INDEX IF NOT EXISTS idx_packages_node ON continuity_packages(node_id,created_at);
        CREATE TRIGGER IF NOT EXISTS packages_immutable_update BEFORE UPDATE ON continuity_packages
            BEGIN SELECT RAISE(ABORT, 'packages are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS packages_immutable_delete BEFORE DELETE ON continuity_packages
            BEGIN SELECT RAISE(ABORT, 'packages are immutable'); END;
        CREATE TABLE IF NOT EXISTS contribution_feedback (
            node_id TEXT NOT NULL REFERENCES nodes(id), suggestion_id TEXT NOT NULL,
            state TEXT NOT NULL, PRIMARY KEY(node_id,suggestion_id)
        );
    ''')
    from .proposals import schema as proposal_schema
    proposal_schema(lab)


def note(lab, ident):
    node = lab.node(ident)
    row = lab.db.execute('SELECT * FROM working_notes WHERE node_id=?', (ident,)).fetchone()
    return dict(row) if row else {'node_id': ident, 'text': node['body'], 'revision': 0, 'updated_at': node['updated_at']}


def save_note(lab, ident, text, revision):
    if not isinstance(text, str) or len(text) > 20000 or type(revision) is not int or revision < 0:
        raise ValueError('Texto ou revisão inválidos')
    def run():
        prior = note(lab, ident)
        if prior['text'] == text:
            return prior  # Retry after a lost response is idempotent.
        if prior['revision'] != revision:
            raise ValueError('Este espaço mudou em outro ambiente. Seu rascunho foi mantido; recarregue antes de conciliar as versões.')
        after = {'node_id': ident, 'text': text, 'revision': revision + 1, 'updated_at': utcnow()}
        lab.db.execute('''INSERT INTO working_notes VALUES(:node_id,:text,:revision,:updated_at)
            ON CONFLICT(node_id) DO UPDATE SET text=excluded.text,revision=excluded.revision,updated_at=excluded.updated_at''', after)
        lab.db.execute('UPDATE nodes SET updated_at=? WHERE id=?', (after['updated_at'], ident))
        lab._append(ident, 'working_note_saved', {'before': prior, 'after': after},
                    source_type='user', source_ref='reference-space', evidence_state='declared')
        return after
    result = lab._tx(run)
    refresh(lab, ident)
    return result


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def next_movement(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        heading = normalize(line.strip().lstrip('#').strip())
        if any(heading.startswith(prefix) for prefix in ('proximo movimento', 'proximo passo', 'ponto de retomada')):
            if ':' in line and line.split(':', 1)[1].strip():
                return line.split(':', 1)[1].strip()[:700]
            for following in lines[index + 1:]:
                if following.strip():
                    return following.strip()[:700]
    return None


def catalog_state(lab):
    docs = [tuple(r) for r in lab.db.execute('SELECT id,content_hash,present FROM documents ORDER BY id')]
    nodes = [tuple(r) for r in lab.db.execute('SELECT id,kind,title,status,updated_at FROM nodes ORDER BY id')]
    node_seq = lab.db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE kind IN ('node_created','node_revised')").fetchone()[0]
    sources = [tuple(r) for r in lab.db.execute('SELECT id,label,active FROM sources ORDER BY id')]
    notes = [tuple(r) for r in lab.db.execute('SELECT node_id,revision FROM working_notes ORDER BY node_id')]
    return digest({'documents': docs, 'nodes': nodes, 'sources': sources, 'notes': notes, 'node_seq': node_seq})


def basis(lab, node, working, catalog=None):
    return digest({'engine': ENGINE, 'node': node, 'note': working, 'catalog': catalog if catalog is not None else catalog_state(lab)})


def build(lab, node, working, fingerprint):
    # The title is the initial intention; current writing contributes additional vocabulary.
    query = (node['title'] + '\n' + working['text'][-1800:] + '\n' + node['body'][:1000])[:4000]
    documents = _matched_docs(lab, query, 5)
    evidence = []
    for doc in documents:
        row = lab.db.execute('''SELECT d.content_hash,d.body,s.label,s.active FROM documents d
            JOIN sources s ON s.id=d.source_id WHERE d.id=?''', (doc['id'],)).fetchone()
        version = lab.db.execute('''SELECT v.event_id FROM document_versions v JOIN events e ON e.event_id=v.event_id
            WHERE v.document_id=? ORDER BY e.seq DESC LIMIT 1''', (doc['id'],)).fetchone()
        evidence.append({**doc, 'content_hash': row['content_hash'], 'version_event_id': version['event_id'],
                         'source_label': row['label'], 'source_active': bool(row['active']),
                         'context_notice': 'Este documento contém exemplo hipotético; confira o contexto completo.'
                         if 'exemplo hipotetico' in normalize(row['body']) else None})
    related = [n for n in _matched_nodes(lab, query, 12) if n['id'] != node['id']][:3]
    contributions = []
    for doc in evidence[:3]:
        contributions.append({'id': 'document:' + doc['id'] + ':' + doc['content_hash'], 'kind': 'reference',
                              'title': doc['title'], 'text': doc['snippet'], 'document_id': doc['id'],
                              'version_event_id': doc['version_event_id'], 'content_hash': doc['content_hash'],
                              'source': doc['source_label'], 'context_notice': doc['context_notice'],
                              'basis': 'lexical_fts', 'state': 'candidate'})
    # Never invent a relationship or scientific conclusion; compare references conservatively.
    connections = []
    for i, first in enumerate(evidence):
        for second in evidence[i + 1:]:
            if first['source_id'] == second['source_id']:
                continue
            score, terms = overlap(first['title'] + ' ' + first['snippet'], second['title'] + ' ' + second['snippet'])
            if len(terms) >= 2 and score >= .12:
                connections.append({'from_id': first['id'], 'to_id': second['id'], 'terms': terms[:8],
                                    'score': score, 'state': 'candidate', 'basis': 'lexical_overlap'})
    last = lab.db.execute('''SELECT * FROM events WHERE stream_id=? AND kind IN
        ('node_created','node_revised','working_note_saved') ORDER BY seq DESC LIMIT 1''', (node['id'],)).fetchone()
    content = working['text'] or node['body']
    return {'engine': ENGINE, 'node_id': node['id'], 'basis_hash': fingerprint,
            'generated_at': utcnow(), 'intention': node['title'],
            'where_left': content[-700:] if content else '',
            'next_movement': next_movement(content),
            'last_change': {'event_id': last['event_id'], 'kind': last['kind'], 'recorded_at': last['recorded_at'],
                            'source_type': last['source_type'], 'source_ref': last['source_ref']} if last else None,
            'evidence': evidence, 'related': [{'id': n['id'], 'title': n['title'], 'kind': n['kind']} for n in related],
            'contributions': contributions, 'connections': sorted(connections,key=lambda c: -c['score'])[:3],
            'limitations': ['Contexto organizado por recuperação lexical; não é síntese semântica nem conclusão científica.',
                            'Somente fontes autorizadas observadas entram no contexto; exemplos exigem leitura integral.']}


def refresh(lab, ident=None):
    """Prepare versioned reference packages after safe observations/writes; no source files edited."""
    def run():
        nodes = [lab.node(ident)] if ident else [dict(r) for r in lab.db.execute(
            "SELECT * FROM nodes WHERE status IN ('open','active') ORDER BY updated_at DESC,id LIMIT 500")]
        catalog = catalog_state(lab)
        changed = 0
        for node in nodes:
            working = note(lab, node['id'])
            fingerprint = basis(lab, node, working, catalog)
            previous = lab.db.execute('''SELECT p.* FROM continuity_packages p JOIN events e ON e.event_id=p.event_id
                WHERE e.stream_id=? AND e.kind='continuity_prepared' ORDER BY e.seq DESC LIMIT 1''', (node['id'],)).fetchone()
            if previous and previous['basis_hash'] == fingerprint:
                continue
            package = build(lab, node, working, fingerprint)
            old_evidence = {d['id']: d['content_hash'] for d in json.loads(previous['payload'])['evidence']} if previous else {}
            package['changed_evidence'] = [d['id'] for d in package['evidence'] if old_evidence.get(d['id']) != d['content_hash']]
            event = lab._append(node['id'], 'continuity_prepared', package,
                                source_type='automation', source_ref=ENGINE, evidence_state='generated')
            lab.db.execute('INSERT INTO continuity_packages VALUES(?,?,?,?,?)',
                           (event['event_id'], node['id'], fingerprint, canonical(package), package['generated_at']))
            changed += 1
        return {'prepared': changed}
    return lab._tx(run)


def transformations(lab, ident):
    rows = lab.db.execute('''
        SELECT l.id AS link_id, l.source_id, l.target_id, l.relation, l.state, l.reason, l.updated_at AS link_updated_at,
               n.id AS node_id, n.kind, n.title, n.status, n.updated_at
        FROM links l
        JOIN nodes n ON n.id = CASE WHEN l.source_id = ? THEN l.target_id ELSE l.source_id END
        WHERE l.source_id = ? OR l.target_id = ?
        ORDER BY l.updated_at DESC, l.id
    ''', (ident, ident, ident)).fetchall()
    items = []
    for r in rows:
        items.append({
            'link_id': r['link_id'],
            'direction': 'outgoing' if r['source_id'] == ident else 'incoming',
            'relation': r['relation'],
            'state': r['state'],
            'reason': r['reason'],
            'link_updated_at': r['link_updated_at'],
            'node': {
                'id': r['node_id'],
                'kind': r['kind'],
                'title': r['title'],
                'status': r['status'],
                'updated_at': r['updated_at'],
            }
        })
    return items


def transform_node(lab, source_id, kind, title, body='', relation='evolves_into', reason='', state='endorsed'):
    lab.node(source_id)
    effective_reason = (reason or '').strip() or f'Desdobramento em {kind}: {title.strip()[:120]}'
    target = lab.create_node(kind, title, body)
    link = lab.add_link(source_id, target['id'], relation, effective_reason, state)
    refresh(lab, source_id)
    refresh(lab, target['id'])
    return {'source_id': source_id, 'node': target, 'link': link}


def reference(lab, ident):
    # One read snapshot even when another process is contributing concurrently.
    with lab.lock:
        owns_transaction = not lab.db.in_transaction
        if owns_transaction:
            lab.db.execute('BEGIN')
        try:
            node = lab.node(ident)
            working = note(lab, ident)
            row = lab.db.execute("""SELECT p.* FROM continuity_packages p JOIN events e ON e.event_id=p.event_id
                WHERE e.stream_id=? AND e.kind='continuity_prepared' ORDER BY e.seq DESC LIMIT 1""", (ident,)).fetchone()
            package = json.loads(row['payload']) if row else None
            feedback = {r['suggestion_id']: r['state'] for r in lab.db.execute(
                'SELECT suggestion_id,state FROM contribution_feedback WHERE node_id=?', (ident,))}
            from .proposals import authorship, list_proposals
            return {'node': node, 'note': working, 'package': package, 'package_event_id': row['event_id'] if row else None,
                    'authorship': authorship(lab, ident), 'proposals': list_proposals(lab, ident),
                    'transformations': transformations(lab, ident),
                    'stale': not row or row['basis_hash'] != basis(lab, node, working), 'feedback': feedback}
        finally:
            if owns_transaction:
                lab.db.execute('ROLLBACK')


def feedback(lab, ident, suggestion_id, state):
    if state not in ('dismissed', 'incorporated', 'available'):
        raise ValueError('Estado de contribuição inválido')
    def run():
        current = reference(lab, ident)
        known = any(suggestion_id == c['id'] for row in lab.db.execute('SELECT payload FROM continuity_packages WHERE node_id=?', (ident,)) for c in json.loads(row['payload'])['contributions'])
        if not known:
            raise ValueError('Contribuição não pertence a este espaço')
        prior = current['feedback'].get(suggestion_id, 'available')
        if prior != state:
            lab.db.execute('INSERT INTO contribution_feedback VALUES(?,?,?) ON CONFLICT(node_id,suggestion_id) DO UPDATE SET state=excluded.state',
                           (ident, suggestion_id, state))
            lab._append(ident, 'contribution_reviewed', {'suggestion_id': suggestion_id, 'before': prior, 'state': state},
                        source_type='user', source_ref='reference-space', evidence_state='declared')
        return {'suggestion_id': suggestion_id, 'state': state}
    return lab._tx(run)


def export_reference(lab, ident):
    current = reference(lab, ident)
    package = current['package']
    node = current['node']
    lines = ['# ' + node['title'].replace('\n', ' '), '',
             f"Natureza: `{node['kind']}` · Estado: `{node['status']}`", '',
             current['note']['text'], '',
             '## Referência persistente', '', f"Percurso: `{ident}` · revisão do texto: {current['note']['revision']}",
             f"Pacote: `{current['package_event_id'] or 'não preparado'}`"]
    if current['transformations']:
        lines.extend(['', '## Transformações e vínculos', ''])
        for t in current['transformations']:
            arrow = '→' if t['direction'] == 'outgoing' else '←'
            lines.append(f"- {arrow} **{t['relation']}** ({t['state']}) · [{t['node']['kind']}] {t['node']['title']} (`{t['node']['id']}`) — {t['reason']}")
    lines.extend(['', '## Fontes aproximadas', ''])
    for doc in package['evidence'] if package else []:
        lines.append(f"- {doc['title']} · snapshot `{doc['version_event_id']}` · SHA-256 `{doc['content_hash']}`")
    lines.extend(['', 'Referências aproximadas por termos em comum; conferir o contexto antes de interpretar.'])
    return {'markdown': '\n'.join(lines) + '\n'}


def _git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, timeout=10, check=False)


def _ensure_workspace_git(lab) -> Path:
    if any(lab.workspace == Path(root['path']) or lab.workspace.is_relative_to(Path(root['path'])) for root in lab.sources()):
        raise ValueError('O workspace não pode ficar dentro de uma fonte observada')
    lab.workspace.mkdir(parents=True, exist_ok=True)
    git_dir = lab.workspace / '.git'
    if not git_dir.exists():
        _git_run(lab.workspace, 'init', '-b', 'main')
        _git_run(lab.workspace, 'config', 'user.name', 'CONTINUUM Lab')
        _git_run(lab.workspace, 'config', 'user.email', 'continuum@local.lab')
    return lab.workspace


def git_history(lab, ident: str) -> dict:
    lab.node(ident)
    filename = f'percurso-{ident}.md'
    dest = lab.workspace / filename
    if not (lab.workspace / '.git').exists() or not dest.exists():
        return {'versioned': False, 'path': str(dest), 'commits': [], 'diff': ''}
    log_res = _git_run(lab.workspace, 'log', '-n', '15', '--pretty=format:%h|%cI|%s', '--', filename)
    commits = []
    for line in log_res.stdout.splitlines():
        parts = line.split('|', 2)
        if len(parts) == 3:
            commits.append({'hash': parts[0], 'date': parts[1], 'subject': parts[2]})
    diff_res = _git_run(lab.workspace, 'show', '--stat', '--patch', '--format=', 'HEAD', '--', filename)
    return {
        'versioned': bool(commits),
        'path': str(dest),
        'commits': commits,
        'diff': diff_res.stdout[:12000] if commits else ''
    }


def git_checkpoint(lab, ident: str, message: str = '') -> dict:
    current = reference(lab, ident)
    ws = _ensure_workspace_git(lab)
    filename = f'percurso-{ident}.md'
    dest = ws / filename
    markdown = export_reference(lab, ident)['markdown']
    dest.write_text(markdown, encoding='utf-8')
    _git_run(ws, 'add', filename)
    status_res = _git_run(ws, 'status', '--porcelain', '--', filename)
    committed = False
    if status_res.stdout.strip():
        node = current['node']
        rev = current['note']['revision']
        commit_msg = (message or '').strip() or f"{node['kind']}({node['status']}): {node['title'][:72]} [rev {rev}]"
        commit_res = _git_run(ws, 'commit', '-m', commit_msg[:240], '--', filename)
        committed = commit_res.returncode == 0
    hist = git_history(lab, ident)
    head_hash = hist['commits'][0]['hash'] if hist['commits'] else None
    if committed and head_hash:
        lab._tx(lambda: lab._append(
            ident, 'git_checkpoint_recorded',
            {'path': str(dest), 'commit': head_hash, 'revision': current['note']['revision']},
            source_type='user', source_ref='git-workspace', evidence_state='generated'
        ))
    return {**hist, 'committed': committed, 'head': head_hash}
