"""Text contributions remain proposals until explicitly reviewed in the browser."""
import json
import uuid

from .core import ACTOR, utcnow


def schema(lab):
    lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS note_proposals (
            id TEXT PRIMARY KEY, node_id TEXT NOT NULL REFERENCES nodes(id),
            text TEXT NOT NULL, base_revision INTEGER NOT NULL,
            event_id TEXT NOT NULL REFERENCES events(event_id),
            state TEXT NOT NULL DEFAULT 'pending'
        );
        CREATE INDEX IF NOT EXISTS idx_proposals_node ON note_proposals(node_id);
        CREATE TRIGGER IF NOT EXISTS proposal_text_immutable BEFORE UPDATE OF
            id,node_id,text,base_revision,event_id ON note_proposals
            BEGIN SELECT RAISE(ABORT, 'proposal text is immutable'); END;
    ''')


def list_proposals(lab, ident):
    return [dict(row) for row in lab.db.execute('''
        SELECT p.*,e.source_type,e.source_ref,e.recorded_at FROM note_proposals p
        JOIN events e ON e.event_id=p.event_id WHERE p.node_id=? ORDER BY e.seq
    ''', (ident,))]


def propose(lab, ident, text, revision, request_id):
    from .continuity import note
    request_id = str(uuid.UUID(request_id))
    if not text.strip() or len(text) > 20000:
        raise ValueError('A proposta precisa de texto, até 20000 caracteres')
    def run():
        old = lab.db.execute('SELECT * FROM note_proposals WHERE id=?', (request_id,)).fetchone()
        if old:
            if (old['node_id'], old['text'], old['base_revision']) != (ident, text, revision):
                raise ValueError('request_id já utilizado para outra proposta')
        else:
            if note(lab, ident)['revision'] != revision:
                raise ValueError('Este espaço mudou em outro ambiente. Leia a referência antes de propor.')
            event = lab._append(ident, 'note_proposed', {
                'id': request_id, 'text': text, 'base_revision': revision},
                source_type='user', source_ref='reference-space', evidence_state='declared')
            lab.db.execute('INSERT INTO note_proposals VALUES(?,?,?,?,?,?)',
                           (request_id, ident, text, revision, event['event_id'], 'pending'))
        return next(p for p in list_proposals(lab, ident) if p['id'] == request_id)
    return lab._tx(run)


def review(lab, ident, proposal_id, state, revision):
    from .continuity import note, refresh
    if ACTOR.get() and ACTOR.get()[0] == 'mcp_client':
        raise PermissionError('A revisão da proposta acontece no navegador pelo usuário.')
    if state not in ('incorporated', 'dismissed'):
        raise ValueError('Estado de proposta inválido')
    def run():
        proposal = next((p for p in list_proposals(lab, ident) if p['id'] == proposal_id), None)
        if not proposal:
            raise ValueError('Proposta não pertence a este espaço')
        if proposal['state'] == state:
            return proposal  # A lost response must never append twice.
        if proposal['state'] != 'pending':
            raise ValueError('Esta proposta já foi examinada')
        if state == 'incorporated':
            prior = note(lab, ident)
            if prior['revision'] != revision:
                raise ValueError('Este espaço mudou em outro ambiente. Confira novamente a prévia antes de incorporar.')
            text = prior['text'] + ('\n\n' if prior['text'] else '') + proposal['text']
            if len(text) > 20000:
                raise ValueError('A incorporação excede o limite de 20000 caracteres')
            after = {'node_id': ident, 'text': text, 'revision': revision + 1, 'updated_at': utcnow()}
            lab.db.execute('''INSERT INTO working_notes VALUES(:node_id,:text,:revision,:updated_at)
                ON CONFLICT(node_id) DO UPDATE SET text=excluded.text,revision=excluded.revision,updated_at=excluded.updated_at''', after)
            lab.db.execute('UPDATE nodes SET updated_at=? WHERE id=?', (after['updated_at'], ident))
            lab._append(ident, 'working_note_saved', {'before': prior, 'after': after,
                'proposal': {'id': proposal_id, 'event_id': proposal['event_id'],
                             'source_type': proposal['source_type'], 'source_ref': proposal['source_ref']}},
                source_type='user', source_ref='reference-space', evidence_state='declared')
        lab.db.execute('UPDATE note_proposals SET state=? WHERE id=?', (state, proposal_id))
        lab._append(ident, 'note_proposal_reviewed', {'id': proposal_id, 'state': state},
                    source_type='user', source_ref='reference-space', evidence_state='declared')
        return {**proposal, 'state': state}
    result = lab._tx(run)
    if state == 'incorporated':
        refresh(lab, ident)
    return result


def authorship(lab, ident):
    # Text origin is independent of the age of the lexical context package.
    last = lab.db.execute('''SELECT * FROM events WHERE stream_id=? AND
        kind='working_note_saved' ORDER BY seq DESC LIMIT 1''', (ident,)).fetchone()
    edits = lab.db.execute("SELECT COUNT(*) FROM events WHERE stream_id=? AND kind='working_note_saved'", (ident,)).fetchone()[0]
    if last is None:
        last = lab.db.execute("SELECT * FROM events WHERE stream_id=? AND kind IN ('node_created','node_revised') ORDER BY seq DESC LIMIT 1", (ident,)).fetchone()
    if last is None:
        return {'last_edit': None, 'edits': edits}
    return {'last_edit': {key: last[key] for key in ('event_id', 'kind', 'recorded_at', 'source_type', 'source_ref')},
            'proposal': json.loads(last['payload']).get('proposal'), 'edits': edits}


def verify_projection(lab):
    expected = {}
    for event in lab.db.execute("SELECT * FROM events WHERE kind IN ('note_proposed','note_proposal_reviewed') ORDER BY seq"):
        payload = json.loads(event['payload'])
        if event['kind'] == 'note_proposed':
            expected[payload['id']] = {'id': payload['id'], 'node_id': event['stream_id'],
                'text': payload['text'], 'base_revision': payload['base_revision'],
                'event_id': event['event_id'], 'state': 'pending'}
        elif payload['id'] in expected:
            expected[payload['id']]['state'] = payload['state']
    actual = {r['id']: dict(r) for r in lab.db.execute('SELECT * FROM note_proposals')}
    return actual == expected
