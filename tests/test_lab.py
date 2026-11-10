"""Executable falsification checks for the Continuum hypothesis."""
import hashlib
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

from lab.core import Lab
from lab.retrieval import discover, markdown_pack
from lab.server import create_handler


class LabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lab = Lab(self.root / "store" / "lab.sqlite", self.root / "workspace")

    def tearDown(self):
        self.lab.close()
        self.temp.cleanup()

    def source(self, name="one"):
        p=self.root/name
        p.mkdir(exist_ok=True)
        self.lab.register_source(str(p),name)
        return p

    def test_empty_bank_and_genesis_anchor(self):
        self.assertEqual(self.lab.verify()["checked"],0)
        self.assertTrue(self.lab.verify(self.lab.anchor())["ok"])

    def test_observation_requires_authorized_source(self):
        p=self.root/"unregistered"
        p.mkdir()
        (p/"work.md").write_text("# Um trabalho",encoding="utf-8")
        self.assertEqual(self.lab.scan()["added"],0)
        with self.assertRaises(ValueError):self.lab.register_source("","empty")
        self.lab.register_source(str(p),"Work")
        self.assertEqual(self.lab.scan()["added"],1)

    def test_pause_authorization_preserves_history_and_blocks_new_scan(self):
        p=self.source()
        (p/"one.md").write_text("# Inicial",encoding="utf-8")
        self.lab.scan()
        ident=self.lab.sources()[0]["id"]
        self.lab.set_source_active(ident,False)
        (p/"two.md").write_text("# Posterior",encoding="utf-8")
        self.assertEqual(self.lab.scan()["added"],0)
        self.assertEqual(self.lab.dashboard()["totals"]["documents"],1)
        self.lab.set_source_active(ident,True)
        self.assertEqual(self.lab.scan()["added"],1)
        self.assertTrue(self.lab.verify()["ok"])

    def test_registration_is_idempotent(self):
        p=self.root/"docs";p.mkdir()
        a=self.lab.register_source(str(p),"docs")
        b=self.lab.register_source(str(p),"new-label")
        self.assertEqual(a["id"],b["id"])
        self.assertEqual(self.lab.verify()["checked"],1)

    def test_document_idempotence_revision_and_immutable_snapshots(self):
        p=self.source();f=p/"conceito.md"
        f.write_text("# Questão central\n\nNossa primeira interpretação.",encoding="utf-8")
        self.assertEqual(self.lab.scan()["added"],1)
        count=self.lab.verify()["checked"]
        self.assertEqual(self.lab.scan()["unchanged"],1)
        self.assertEqual(self.lab.verify()["checked"],count)
        first=self.lab.db.execute("SELECT * FROM document_versions").fetchone()
        self.assertEqual(first["content_bytes"],f.read_bytes())
        f.write_text("# Questão central\n\nNossa segunda interpretação com evidências.",encoding="utf-8")
        self.assertEqual(self.lab.scan()["changed"],1)
        versions=self.lab.db.execute("SELECT * FROM document_versions ORDER BY observed_at").fetchall()
        self.assertEqual(len(versions),2)
        self.assertNotEqual(versions[0]["content_hash"],versions[1]["content_hash"])
        self.assertTrue(self.lab.verify()["ok"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute("UPDATE document_versions SET content_hash='hacked'")

    def test_missing_then_return_not_confused_with_deletion_cause(self):
        p=self.source();f=p/"return.md";f.write_text("# Reaparece\n\nRelato",encoding="utf-8")
        self.lab.scan();f.unlink()
        self.assertEqual(self.lab.scan()["missing"],1)
        self.assertEqual(self.lab.scan()["missing"],0)
        f.write_text("# Reaparece\n\nRelato",encoding="utf-8")
        self.assertEqual(self.lab.scan()["changed"],1)
        self.assertEqual(self.lab.db.execute("SELECT present FROM documents").fetchone()[0],1)
        kinds=[x[0] for x in self.lab.db.execute("SELECT kind FROM events")]
        self.assertIn("document_not_found",kinds)
        self.assertIn("document_returned",kinds)

    def test_incomplete_scan_does_not_infer_missing(self):
        p=self.source();f=p/"small.md";f.write_text("# Pequeno",encoding="utf-8")
        self.lab.scan();f.unlink()
        (p/"giant.txt").write_text("x"*1_000_010,encoding="utf-8")
        self.assertEqual(self.lab.scan()["missing"],0)
        (p/"giant.txt").unlink()
        self.assertEqual(self.lab.scan()["missing"],1)

    def test_symlinks_are_not_traversed(self):
        p=self.source();external=self.root/"external";external.mkdir()
        (external/"private.md").write_text("# Confidencial",encoding="utf-8")
        (p/"link.md").symlink_to(external/"private.md")
        (p/"outside").symlink_to(external,target_is_directory=True)
        self.assertEqual(self.lab.scan()["added"],0)

    def test_node_revision_keeps_before_and_after(self):
        n=self.lab.create_node("question","Qual problema?","Hipótese inicial")
        r=self.lab.revise_node(n["id"],status="active",body="Hipótese revista",reason="Novos dados")
        self.assertEqual(r["status"],"active")
        t=self.lab.trajectory(n["id"])
        self.assertEqual([e["kind"] for e in t["events"]],["node_created","node_revised"])
        self.assertEqual(t["events"][1]["payload"]["before"]["body"],"Hipótese inicial")
        self.assertTrue(self.lab.verify()["ok"])
        with self.assertRaises(ValueError):self.lab.revise_node(n["id"],status="resolved",reason="")

    def test_noop_revision_creates_no_noise(self):
        n=self.lab.create_node("idea","Idempotência")
        self.lab.revise_node(n["id"],reason="Sem mudanças")
        self.assertEqual(len(self.lab.trajectory(n["id"])["events"]),1)

    def test_declared_relation_is_not_scientific_confirmation(self):
        a=self.lab.create_node("question","Resiliência")
        b=self.lab.create_node("hypothesis","Autonomia")
        with self.assertRaises(ValueError):self.lab.add_link(a["id"],a["id"],"relates_to","Razão")
        link=self.lab.add_link(a["id"],b["id"],"relates_to","Comparar conceitos", "candidate")
        self.assertEqual(link["state"],"candidate")
        e=self.lab.db.execute("SELECT * FROM events WHERE stream_id=?",(link["id"],)).fetchone()
        self.assertEqual(e["evidence_state"],"declared")

    def test_retrieval_accent_and_source_reference(self):
        p=self.source();(p/"ref.md").write_text("# Idempotência\n\nA idempotência sustenta a repetição segura de ações.",encoding="utf-8")
        self.lab.scan()
        result=discover(self.lab,"idempotencia repeticao")
        self.assertEqual(len(result["documents"]),1)
        self.assertIn("ref.md",result["documents"][0]["path"])
        report=markdown_pack(result)
        self.assertIn("Fonte",report)
        self.assertIn("idempotencia repeticao",report)

    def test_candidate_contradiction_is_only_lexical(self):
        a=self.source("A");b=self.source("B")
        content="# Integridade temporal e idempotência\n\nIntegridade temporal, idempotência e continuidade entre documentos e sistemas de registro."
        (a/"a.md").write_text(content,encoding="utf-8")
        (b/"b.md").write_text(content+" Investigação alternativa.",encoding="utf-8")
        self.lab.scan()
        found=discover(self.lab,"integridade temporal idempotência")
        self.assertEqual(len(found["documents"]),2)
        self.assertTrue(found["connections"])
        self.assertEqual(found["connections"][0]["state"],"candidate")
        self.assertEqual(found["connections"][0]["basis"],"lexical_overlap")

    def test_absence_is_not_claimed_as_nonexistence(self):
        result=discover(self.lab,"inexistente e não indexado")
        self.assertIn("não demonstra inexistência",result["summary"])

    def test_sqlite_journal_guards(self):
        self.lab.create_node("idea","Histórico")
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute("DELETE FROM events")
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute("UPDATE events SET payload='{}'")

    def test_tampering_detected_against_journal(self):
        self.lab.create_node("idea","Histórico")
        self.lab.db.execute("DROP TRIGGER events_immutable_update")
        self.lab.db.execute("UPDATE events SET payload='{}'")
        self.assertFalse(self.lab.verify()["ok"])

    def test_snapshot_tampering_detected(self):
        p=self.source();(p/"snap.md").write_text("# Integridade",encoding="utf-8")
        self.lab.scan()
        self.lab.db.execute("DROP TRIGGER document_versions_immutable_update")
        self.lab.db.execute("UPDATE document_versions SET content_bytes=?",(b"ALTERADO",))
        self.assertEqual(self.lab.verify()["error"],"snapshot_mismatch")

    def test_anchor_detects_tail_loss(self):
        n=self.lab.create_node("idea","Primeiro")
        self.lab.create_node("idea","Segundo")
        anchor=self.lab.anchor()
        self.lab.db.execute("DROP TRIGGER events_immutable_delete")
        self.lab.db.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
        self.assertTrue(self.lab.verify()["ok"]) # Without independent anchor, tail deletion is invisible.
        self.assertFalse(self.lab.verify(anchor)["ok"])

    def test_concurrent_declared_events_are_serialized(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i:self.lab.create_node("question",f"Questão {i}"),range(30)))
        self.assertEqual(self.lab.verify()["checked"],30)
        self.assertTrue(self.lab.verify()["ok"])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lab = Lab(self.root / "store" / "lab.sqlite", self.root / "workspace")
        self.http=ThreadingHTTPServer(("127.0.0.1",0),create_handler(self.lab))
        self.port=self.http.server_port
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown();self.thread.join(timeout=3);self.http.server_close()
        self.lab.close()
        self.temp.cleanup()

    def call(self, method, path, data=None, headers=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.port,timeout=3)
        body=json.dumps(data).encode() if data is not None else None
        h={"Host":f"127.0.0.1:{self.port}"}
        if data is not None: h.update({"Content-Type":"application/json","X-Lab-Intent":"user"})
        if headers: h.update(headers)
        conn.request(method,path,body,headers=h)
        r=conn.getresponse();content=r.read();status=r.status;conn.close()
        return status,content

    def test_http_user_journey(self):
        status,_=self.call("GET","/")
        self.assertEqual(status,200)
        status,body=self.call("POST","/api/nodes",{"kind":"question","title":"Que investigar?"})
        self.assertEqual(status,200)
        ident=json.loads(body)["id"]
        status,body=self.call("GET",f"/api/trajectory?id={ident}")
        self.assertEqual(status,200)
        self.assertEqual([e["kind"] for e in json.loads(body)["events"]], ["node_created", "continuity_prepared"])
        status,_=self.call("GET","/not-allowed")
        self.assertEqual(status,404)

    def test_no_write_without_intent_or_valid_origin(self):
        status,_=self.call("POST","/api/nodes",{"kind":"question","title":"X"},{"X-Lab-Intent":""})
        self.assertEqual(status,403)
        status,_=self.call("POST","/api/nodes",{"kind":"question","title":"X"},{"Origin":"https://evil.example"})
        self.assertEqual(status,403)
        status,_=self.call("GET","/api/dashboard",headers={"Host":"attacker.example"})
        self.assertEqual(status,403)
        self.assertEqual(self.lab.dashboard()["totals"]["nodes"],0)

    def test_api_generate_draft_only_on_click(self):
        status,body=self.call("POST","/api/draft",{"query":"Como acompanhar experimentos?"})
        self.assertEqual(status,200)
        path=Path(json.loads(body)["path"])
        self.assertTrue(path.is_file())
        self.assertTrue(path.is_relative_to(self.lab.workspace))
        self.assertIn("Como acompanhar",path.read_text())
        self.assertTrue(self.lab.verify()["ok"])

    def test_pause_source_through_http(self):
        p=self.root/"docs";p.mkdir()
        status,body=self.call("POST","/api/sources",{"path":str(p),"label":"Pastas"})
        self.assertEqual(status,200)
        ident=json.loads(body)["id"]
        status,body=self.call("POST","/api/sources/active",{"id":ident,"active":False})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)["active"],0)

    def test_reject_missing_source_and_workspace_overlap(self):
        status,_=self.call("POST","/api/sources",{"path":"/path/that/does/not/exist","label":"Falha"})
        self.assertEqual(status,400)
        self.lab.register_source(str(self.lab.workspace.parent),"Source that contains workspace")
        status,content=self.call("POST","/api/draft",{"query":"Como preservar o passado?"})
        self.assertEqual(status,400)
        self.assertIn(b"workspace",content)

    def test_extended_api_and_bounds(self):
        node = self.lab.create_node("idea", "API ampliada")
        for path, key in (("/api/nodes?limit=1", "nodes"),
                          ("/api/node?id=" + node["id"], "title"),
                          ("/api/documents", "documents"),
                          ("/api/events?limit=1", "next_after"),
                          ("/api/verify", "ok"),
                          ("/api/anchor", "seq"),
                          ("/api/capabilities", "operations")):
            status, body = self.call("GET", path)
            self.assertEqual(status, 200, body)
            self.assertIn(key, json.loads(body))
        for path in ("/api/nodes?limit=-1", "/api/events?after=-1", "/api/nodes?limit=501",
                     "/api/nodes?limit=no", "/api/documents?unknown=x", "/api/document?id=missing"):
            status, _ = self.call("GET", path)
            self.assertEqual(status, 400)

    def test_shared_reference_http_contract(self):
        status, body = self.call("POST", "/api/nodes", {"kind": "idea", "title": "Criar com continuidade"})
        ident = json.loads(body)["id"]
        status, body = self.call("POST", "/api/reference/note", {"id": ident, "text": "Esboço preservado", "revision": 0})
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["revision"], 1)
        status, body = self.call("GET", "/api/reference?id=" + ident)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["note"]["text"], "Esboço preservado")
        self.assertFalse(json.loads(body)["stale"])
        status, body = self.call("GET", "/api/reference/export?id=" + ident)
        self.assertEqual(status, 200)
        self.assertIn("Esboço preservado", body.decode())
        status, _ = self.call("POST", "/api/reference/note", {"id": ident, "text": "Sobrescrita antiga", "revision": 0})
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/reference/note", {"id": ident, "text": "X", "revision": 1}, {"X-Lab-Intent": ""})
        self.assertEqual(status, 403)

    def test_project_svg_assets_are_served(self):
        import xml.etree.ElementTree as ET
        for path in ("/favicon.svg", "/assets/continuum-symbol.svg", "/assets/continuum-icons.svg"):
            status, body = self.call("GET", path)
            self.assertEqual(status, 200)
            self.assertEqual(ET.fromstring(body).tag, "{http://www.w3.org/2000/svg}svg")

    def test_investigation_preserves_full_question_and_retry(self):
        import uuid
        query = "Como preservar " + "evidência " * 80
        body = {"query": query, "request_id": str(uuid.uuid4())}
        status, response = self.call("POST", "/api/investigations", body)
        self.assertEqual(status, 200, response)
        node = json.loads(response)["question_node"]
        self.assertEqual(node["body"], query.strip())
        self.assertEqual(len(node["title"]), 240)
        self.lab.revise_node(node["id"], body="Nova interpretação", reason="Evidência nova")
        status, response = self.call("POST", "/api/investigations", body)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(response)["question_node"]["id"], node["id"])
        self.assertEqual(len(self.lab.nodes()), 1)
        self.assertEqual(len([e for e in self.lab.trajectory(node["id"])["events"] if e["kind"] != "continuity_prepared"]), 2)
        status, _ = self.call("POST", "/api/investigations", {**body, "query": "Outra pergunta"})
        self.assertEqual(status, 400)
        status, _ = self.call("POST", "/api/investigations", body, {"X-Lab-Intent": ""})
        self.assertEqual(status, 403)
        self.assertTrue(self.lab.verify()["ok"])

    def test_no_arbitrary_file_serving(self):
        for attack in ("/../../etc/passwd","/%2e%2e/%2e%2e/etc/passwd","/lab/core.py"):
            status,_=self.call("GET",attack)
            self.assertEqual(status,404)


if __name__=="__main__":
    unittest.main()
