"""Persistence, provenance, temporal integrity and authorized observations.

Only the journal is historical truth. All other tables are replaceable projections.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
import re
import sqlite3
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTOR = ContextVar("continuum_actor", default=None)


@contextmanager
def provenance(source_type, source_ref):
    token = ACTOR.set((source_type, source_ref))
    try:
        yield
    finally:
        ACTOR.reset(token)


FILE_TYPES = {".md", ".markdown", ".txt", ".tex"}
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "build", "dist", "output", ".cache"}
MAX_SIZE = 1_000_000
MAX_FILES_PER_SOURCE = 3_000
VALID_KINDS = {"question", "idea", "hypothesis", "decision", "experiment", "opportunity"}
VALID_STATUSES = {"open", "active", "suspended", "resolved"}
VALID_LINK_STATES = {"candidate", "endorsed", "rejected"}
VALID_RELATIONS = {"relates_to", "supports", "contradicts", "evolves_into", "depends_on"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def words(text: str) -> list[str]:
    deaccent = unicodedata.normalize("NFKD", text.casefold())
    deaccent = "".join(c for c in deaccent if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9_]{3,}", deaccent)


def read_title(body: str, fallback: str) -> str:
    for line in body.splitlines()[:60]:
        t = line.strip()
        if t.startswith("# ") or t.startswith("\\title{"):
            return t.removeprefix("# ").removeprefix("\\title{").rstrip("}")[:180]
    return fallback[:180]


def chunks_of(body: str, limit: int = 1400) -> list[str]:
    """Text slices are a retrieval projection, never a historical claim."""
    blocks = re.split(r"\n\s*\n", body)
    result: list[str] = []
    current = ""
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) > limit:
            if current:
                result.append(current)
                current = ""
            result.extend(block[i:i + limit] for i in range(0, len(block), limit))
        elif len(current) + len(block) + 2 > limit:
            if current:
                result.append(current)
            current = block
        else:
            current += ("\n\n" if current else "") + block
    if current:
        result.append(current)
    return result[:100]


class Lab:
    def __init__(self, database: str | Path, workspace: str | Path | None = None):
        self.database = Path(database).expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.workspace = Path(workspace or self.database.parent / "drafts").expanduser().resolve()
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.database, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._schema()
        from .continuity import schema
        schema(self)

    def close(self) -> None:
        self.db.close()

    def _schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE NOT NULL,
            stream_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            evidence_state TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS events_immutable_update
            BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'journal is immutable'); END;
        CREATE TRIGGER IF NOT EXISTS events_immutable_delete
            BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'journal is immutable'); END;
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, label TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1, last_scan_at TEXT
        );
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
            path TEXT NOT NULL UNIQUE, title TEXT NOT NULL, body TEXT NOT NULL,
            content_hash TEXT NOT NULL, observed_at TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS document_versions (
            event_id TEXT PRIMARY KEY REFERENCES events(event_id),
            document_id TEXT NOT NULL, content_bytes BLOB NOT NULL,
            content_hash TEXT NOT NULL, observed_at TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS document_versions_immutable_update
            BEFORE UPDATE ON document_versions BEGIN SELECT RAISE(ABORT, 'versions are immutable'); END;
        CREATE TRIGGER IF NOT EXISTS document_versions_immutable_delete
            BEFORE DELETE ON document_versions BEGIN SELECT RAISE(ABORT, 'versions are immutable'); END;
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            title, body, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
        );
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid,title,body) VALUES (new.id,new.title,new.body);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts,rowid,title,body) VALUES('delete',old.id,old.title,old.body);
        END;
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
            body TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS links (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES nodes(id),
            target_id TEXT NOT NULL REFERENCES nodes(id), relation TEXT NOT NULL,
            state TEXT NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL,
            CHECK (source_id != target_id)
        );
        CREATE TABLE IF NOT EXISTS investigations (
            request_id TEXT PRIMARY KEY,
            node_id TEXT NOT NULL REFERENCES nodes(id),
            query TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_stream ON events(stream_id,seq);
        CREATE INDEX IF NOT EXISTS idx_docs_source ON documents(source_id);
        """)

    def _append(self, stream_id: str, kind: str, payload: dict, *,
                source_type: str, source_ref: str, evidence_state: str,
                occurred_at: str | None = None) -> dict:
        if source_type == "user" and ACTOR.get():
            source_type, source_ref = ACTOR.get()
        prev = self.db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        row = dict(event_id=str(uuid.uuid4()), stream_id=stream_id, kind=kind,
                   payload=canonical(payload), source_type=source_type, source_ref=source_ref,
                   occurred_at=occurred_at or utcnow(), recorded_at=utcnow(),
                   evidence_state=evidence_state, previous_hash=prev[0] if prev else "GENESIS")
        row["event_hash"] = digest(row)
        cur = self.db.execute("""INSERT INTO events(event_id,stream_id,kind,payload,source_type,
            source_ref,occurred_at,recorded_at,evidence_state,previous_hash,event_hash)
            VALUES (:event_id,:stream_id,:kind,:payload,:source_type,:source_ref,
            :occurred_at,:recorded_at,:evidence_state,:previous_hash,:event_hash)""", row)
        row["seq"] = cur.lastrowid
        row["payload"] = payload
        return row

    def _tx(self, fn):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                result = fn()
                self.db.execute("COMMIT")
                return result
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def verify(self, anchor: dict | None = None) -> dict:
        with self.lock:
            previous = "GENESIS"
            count = 0
            anchor_seen = None
            for row in self.db.execute("SELECT * FROM events ORDER BY seq"):
                val = dict(row)
                actual = val.pop("event_hash")
                seq = val.pop("seq")
                if val["previous_hash"] != previous or digest(val) != actual:
                    return {"ok": False, "checked": count, "error_at": seq, "error": "hash_chain_mismatch"}
                previous = actual
                count += 1
                if anchor and seq == anchor.get("seq"):
                    anchor_seen = actual
            if anchor:
                # The genesis marker is not an external proof of subsequent history.
                if anchor.get("seq") == 0:
                    anchor_matches = anchor.get("hash") == "GENESIS"
                else:
                    anchor_matches = anchor_seen == anchor.get("hash")
                if not anchor_matches:
                    return {"ok": False, "checked": count, "error": "anchor_mismatch"}
            # Verify source snapshots independently, not just the journal's internal chain.
            rows = self.db.execute("""SELECT e.seq, e.payload, v.content_bytes, v.content_hash
                FROM events e LEFT JOIN document_versions v ON v.event_id=e.event_id
                WHERE e.kind IN ('document_observed','document_changed','document_returned')""").fetchall()
            for item in rows:
                expected = json.loads(item["payload"])["content_hash"]
                if item["content_bytes"] is None or item["content_hash"] != expected or hashlib.sha256(item["content_bytes"]).hexdigest() != expected:
                    return {"ok": False, "checked": count, "error": "snapshot_mismatch", "error_at": item["seq"]}
            for row in self.db.execute("SELECT p.event_id,p.payload,e.payload AS recorded FROM continuity_packages p JOIN events e ON e.event_id=p.event_id"):
                if row["payload"] != row["recorded"]:
                    return {"ok": False, "checked": count, "error": "continuity_package_mismatch", "event_id": row["event_id"]}
            return {"ok": True, "checked": count, "snapshots_checked": len(rows), "head": previous}

    def anchor(self) -> dict:
        row = self.db.execute("SELECT seq,event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return {"schema": "lab-anchor-v1", "seq": row[0] if row else 0,
                "hash": row[1] if row else "GENESIS", "issued_at": utcnow()}

    def register_source(self, path: str, label: str) -> dict:
        if not str(path).strip():
            raise ValueError("Informe o caminho de uma pasta autorizada")
        root = Path(path).expanduser().resolve(strict=True)
        if not root.is_dir():
            raise ValueError("A fonte deve ser um diretório existente")
        if len(str(root)) > 1000 or not label.strip():
            raise ValueError("Fonte ou nome inválido")
        ident = str(uuid.uuid4())
        def run():
            old = self.db.execute("SELECT * FROM sources WHERE path=?", (str(root),)).fetchone()
            if old:
                return dict(old)
            self.db.execute("INSERT INTO sources(id,label,path) VALUES(?,?,?)", (ident,label.strip()[:120],str(root)))
            self._append(ident,"source_authorized",{"path":str(root),"label":label.strip()[:120]},
                         source_type="user",source_ref="local-ui-or-cli",evidence_state="declared")
            return dict(self.db.execute("SELECT * FROM sources WHERE id=?", (ident,)).fetchone())
        return self._tx(run)

    def set_source_active(self, ident: str, active: bool) -> dict:
        if not isinstance(active,bool):
            raise ValueError("Estado da fonte precisa ser booleano")
        def run():
            row = self.db.execute("SELECT * FROM sources WHERE id=?",(ident,)).fetchone()
            if not row:
                raise ValueError("Fonte não encontrada")
            if bool(row["active"]) == active:
                return dict(row)
            self._append(ident,"source_resumed" if active else "source_paused",
                {"source_id":ident,"path":row["path"],"active":active},
                source_type="user",source_ref="local-ui-or-cli",evidence_state="declared")
            self.db.execute("UPDATE sources SET active=? WHERE id=?",(int(active),ident))
            return dict(self.db.execute("SELECT * FROM sources WHERE id=?",(ident,)).fetchone())
        return self._tx(run)

    def sources(self) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM sources ORDER BY label")]

    def _index_document(self, ident: str, title: str, body: str) -> None:
        self.db.execute("DELETE FROM chunks WHERE document_id=?", (ident,))
        for block in chunks_of(body):
            self.db.execute("INSERT INTO chunks(document_id,title,body) VALUES(?,?,?)",(ident,title,block))

    def scan(self) -> dict:
        """Only explicitly authorized roots are traversed; never writes into them."""
        stats = {"added": 0, "changed": 0, "missing": 0, "unchanged": 0, "skipped": 0, "sources": 0}
        for root in self.sources():
            if not root["active"]:
                continue
            base = Path(root["path"])
            if not base.is_dir():
                stats["skipped"] += 1
                continue
            stats["sources"] += 1
            seen = set()
            count = 0
            source_issues = [False]
            def walk_error(_):
                source_issues[0] = True
            # A per-root upper bound avoids unbounded accidental ingestion.
            for parent, directories, files in os.walk(base, followlinks=False, onerror=walk_error):
                directories[:] = sorted(d for d in directories if d not in SKIP_DIRS and not (Path(parent)/d).is_symlink())
                for filename in sorted(files):
                    path = Path(parent) / filename
                    if path.suffix.casefold() not in FILE_TYPES or path.is_symlink():
                        continue
                    count += 1
                    if count > MAX_FILES_PER_SOURCE:
                        stats["skipped"] += 1
                        source_issues[0] = True
                        continue
                    try:
                        if not path.is_file() or path.stat().st_size > MAX_SIZE:
                            stats["skipped"] += 1
                            source_issues[0] = True
                            continue
                        raw = path.read_bytes()
                        body = raw.decode("utf-8", errors="replace")
                        content_hash = hashlib.sha256(raw).hexdigest()
                    except (OSError, PermissionError):
                        stats["skipped"] += 1
                        source_issues[0] = True
                        continue
                    absolute = str(path.absolute())
                    seen.add(absolute)
                    def ingest():
                        old = self.db.execute("SELECT * FROM documents WHERE path=?",(absolute,)).fetchone()
                        if old and old["content_hash"] == content_hash and old["present"] == 1:
                            return "unchanged"
                        ident = old["id"] if old else str(uuid.uuid4())
                        kind = "document_changed" if old else "document_observed"
                        if old and old["present"] == 0:
                            kind = "document_returned"
                        title = read_title(body, path.stem)
                        journal_event = self._append(ident,kind,{"title":title,"path":absolute,
                            "content_hash":content_hash,"previous_hash":old["content_hash"] if old else None,
                            "source_id":root["id"]},source_type="filesystem",source_ref=absolute,
                            evidence_state="observed")
                        self.db.execute("""INSERT INTO document_versions(event_id,document_id,content_bytes,content_hash,observed_at)
                            VALUES(?,?,?,?,?)""",(journal_event["event_id"],ident,raw,content_hash,utcnow()))
                        self.db.execute("""INSERT INTO documents(id,source_id,path,title,body,content_hash,observed_at,present)
                            VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title,body=excluded.body,content_hash=excluded.content_hash,
                            observed_at=excluded.observed_at,present=1""",
                            (ident,root["id"],absolute,title,body,content_hash,utcnow()))
                        self._index_document(ident,title,body)
                        return "added" if not old else "changed"
                    stats[ self._tx(ingest) ] += 1
            def missing():
                old_rows = self.db.execute("SELECT id,path FROM documents WHERE source_id=? AND present=1",
                                           (root["id"],)).fetchall()
                n=0
                for item in old_rows:
                    if item["path"] not in seen:
                        # Unknown scan errors and truncation must not be interpreted as deletion.
                        if count > MAX_FILES_PER_SOURCE or source_issues[0]:
                            continue
                        self._append(item["id"],"document_not_found",{"path":item["path"]},
                            source_type="filesystem",source_ref=item["path"],evidence_state="observed")
                        self.db.execute("UPDATE documents SET present=0 WHERE id=?",(item["id"],))
                        self.db.execute("DELETE FROM chunks WHERE document_id=?",(item["id"],))
                        n+=1
                self.db.execute("UPDATE sources SET last_scan_at=? WHERE id=?",(utcnow(),root["id"]))
                return n
            stats["missing"] += self._tx(missing)
        return stats

    def create_node(self, kind: str, title: str, body: str = "") -> dict:
        if kind not in VALID_KINDS or not title.strip() or len(title) > 240 or len(body) > 20_000:
            raise ValueError("Tipo, título ou descrição inválidos")
        ident = str(uuid.uuid4())
        now = utcnow()
        def run():
            self.db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?)",
                            (ident,kind,title.strip(),body,"open",now,now))
            self._append(ident,"node_created",{"kind":kind,"title":title.strip(),"body":body,"status":"open"},
                source_type="user",source_ref="local-ui-or-cli",evidence_state="declared")
            return self.node(ident)
        return self._tx(run)

    def record_question(self, query: str, request_id: str) -> dict:
        """Persist a submitted question atomically; retries reuse the original node."""
        query = query.strip()
        if not query or len(query) > 4000:
            raise ValueError("A questão deve ter entre 1 e 4000 caracteres")
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, AttributeError) as exc:
            raise ValueError("request_id deve ser UUID") from exc
        def run():
            existing = self.db.execute("SELECT * FROM investigations WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["query"] != query:
                    raise ValueError("request_id já utilizado para outra questão")
                return self.node(existing["node_id"])
            ident, now = str(uuid.uuid4()), utcnow()
            title = query[:240]
            self.db.execute("INSERT INTO nodes VALUES(?,?,?,?,?,?,?)",
                            (ident, "question", title, query, "open", now, now))
            self._append(ident, "node_created",
                         {"kind": "question", "title": title, "body": query,
                          "status": "open", "request_id": request_id},
                         source_type="user", source_ref="investigation", evidence_state="declared")
            self.db.execute("INSERT INTO investigations VALUES(?,?,?)", (request_id, ident, query))
            return self.node(ident)
        return self._tx(run)

    def node(self, ident: str) -> dict:
        row = self.db.execute("SELECT * FROM nodes WHERE id=?",(ident,)).fetchone()
        if row is None:
            raise ValueError("Questão ou elemento não encontrado")
        return dict(row)

    def nodes(self, limit: int = 100) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM nodes ORDER BY updated_at DESC,id LIMIT ?",(min(500,limit),))]

    def revise_node(self, ident: str, *, title: str | None = None,
                    body: str | None = None, status: str | None = None, reason: str = "") -> dict:
        if not reason.strip():
            raise ValueError("A revisão precisa de uma justificativa")
        def run():
            prior = self.node(ident)
            after = {"title": prior["title"] if title is None else title.strip(),
                     "body": prior["body"] if body is None else body,
                     "status": prior["status"] if status is None else status}
            if not after["title"] or len(after["title"]) > 240 or len(after["body"]) > 20000 or after["status"] not in VALID_STATUSES:
                raise ValueError("Revisão inválida")
            if all(after[k] == prior[k] for k in after):
                return prior
            self._append(ident,"node_revised",{"before":{k:prior[k] for k in after},
                "after":after,"reason":reason[:2000]},source_type="user",
                source_ref="local-ui-or-cli",evidence_state="declared")
            self.db.execute("UPDATE nodes SET title=?,body=?,status=?,updated_at=? WHERE id=?",
                (after["title"],after["body"],after["status"],utcnow(),ident))
            return self.node(ident)
        return self._tx(run)

    def add_link(self, source_id: str, target_id: str, relation: str,
                 reason: str, state: str = "candidate") -> dict:
        if relation not in VALID_RELATIONS or state not in VALID_LINK_STATES or not reason.strip() or source_id == target_id:
            raise ValueError("A ligação precisa de dois nós distintos, tipo, estado e justificativa")
        ident = str(uuid.uuid4())
        def run():
            self.node(source_id)
            self.node(target_id)
            self.db.execute("INSERT INTO links VALUES(?,?,?,?,?,?,?)",
                (ident,source_id,target_id,relation,state,reason[:2000],utcnow()))
            self._append(ident,"link_declared",{"from":source_id,"to":target_id,
                "relation":relation,"state":state,"reason":reason[:2000]},
                source_type="user",source_ref="local-ui-or-cli",evidence_state="declared")
            return dict(self.db.execute("SELECT * FROM links WHERE id=?",(ident,)).fetchone())
        return self._tx(run)

    def trajectory(self, ident: str) -> dict:
        with self.lock:
            node = self.node(ident)
            rows = self.db.execute("SELECT * FROM events WHERE stream_id=? ORDER BY seq",(ident,)).fetchall()
            linked = self.db.execute("SELECT * FROM links WHERE source_id=? OR target_id=? ORDER BY updated_at DESC",(ident,ident)).fetchall()
            return {"node":node,"events":[self._event(r) for r in rows],"links":[dict(r) for r in linked]}

    @staticmethod
    def _event(row) -> dict:
        obj = dict(row)
        obj["payload"] = json.loads(obj["payload"])
        return obj

    def dashboard(self) -> dict:
        with self.lock:
            totals = {"documents":self.db.execute("SELECT COUNT(*) FROM documents WHERE present=1").fetchone()[0],
                "nodes":self.db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
                "events":self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "sources":self.db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]}
            recent_events = [self._event(r) for r in self.db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT 12")]
            return {"totals":totals,"questions":self.nodes(12),"recent_events":recent_events,
                    "sources":self.sources(),"integrity":self.verify()}
