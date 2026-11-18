import tempfile, unittest
from pathlib import Path
from bible_brain.database import Database, ScriptureAnchor
from bible_brain.conversation import import_file, manual_extract

class ReleaseAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Database(Path(self.tmp.name)/"library.sqlite3"); self.addCleanup(self.tmp.cleanup); self.addCleanup(self.db.close)
        rows=[]
        for book, name, ch, vs in (("GEN","Genesis",3,22),("REV","Revelation",2,7),("REV","Revelation",22,2),("REV","Revelation",22,14),("REV","Revelation",10,1)):
            rows.append((book,name,1 if book == "GEN" else 2,ch,vs,f"Tree of life passage {book} {ch}:{vs}"))
        self.db.import_translation(code="TEST",name="Fixture",language="en",license="Internal",source_url="fixture",verses=rows)
    def test_tree_of_life_discovery_and_review(self):
        trace=self.db.create_trace("Tree of Life"); anchors=[ScriptureAnchor("REV",2,7,"TEST"),ScriptureAnchor("GEN",3,22,"TEST")]
        for a in anchors:self.db.add_trace_member(trace,self.db.scripture_anchor(a))
        self.assertTrue(self.db.discover_connections(anchors,trace))
    def test_conversation_reimport_and_selective_review(self):
        p=Path(self.tmp.name)/"conversation.txt"; p.write_text("user: Revelation 10:1 observation\n\nassistant: possible interpretation",encoding="utf-8")
        c=import_file(p); cid,new=self.db.import_conversation(fingerprint=c.fingerprint,title=c.title,body=c.body,messages=c.messages); self.assertTrue(new)
        for row in manual_extract(c,self.db): self.db.create_conversation_proposal(conversation_id=cid,**row)
        self.assertFalse(self.db.import_conversation(fingerprint=c.fingerprint,title=c.title,body=c.body,messages=c.messages)[1]); self.assertEqual(len(self.db.conversation_proposals(cid)),2)
    def test_rejected_discovery_is_not_approved(self):
        pid=self.db.save_discovery({"kind":"pattern","title":"Speculative","body":"Maybe","source_ids":["REV:2:7"],"limitations":"Needs evidence"}); self.db.review_discovery(pid,"rejected"); self.assertEqual(self.db.discovery_proposals()[0]["status"],"rejected")
    def test_incremental_fts_update_and_rebuild(self):
        oid=self.db.create_knowledge_object("observation","Alpha","שלום Unicode"); self.assertTrue(self.db.search_research("שלום")); self.db.rebuild_search_index(); self.assertEqual(self.db.search_research("Unicode")[0]["id"],oid)
    def test_backup_restore_after_release_migration(self):
        oid=self.db.create_knowledge_object("observation","Persist","release"); backup=Path(self.tmp.name)/"backup.sqlite3"; self.db.backup_to(backup); self.db.create_knowledge_object("observation","Later","change"); self.db.restore_from(backup); self.assertEqual(self.db.knowledge_object(oid)["title"],"Persist")

if __name__ == "__main__": unittest.main()
