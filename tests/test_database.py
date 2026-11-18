"""Persistence tests use synthetic record values, never an installed Bible edition."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from bible_brain.database import Database, ScriptureAnchor


RECORDS = (
    ("GEN", "Genesis", 1, 1, 1, "Alpha 🕊 beta gamma."),
    ("GEN", "Genesis", 1, 1, 2, ""),
    ("GEN", "Genesis", 1, 3, 1, "Gap between chapters"),
    ("EXO", "Exodus", 2, 1, 1, "Next book"),
)
TRANSLATION = {
    "code": "TEST", "name": "Synthetic test edition", "language": "en",
    "license": "Test fixture", "source_url": "Internal test fixture",
}


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.path = self.directory / "library.sqlite3"
        self.path.touch()
        self.database = Database(self.path)
        self.addCleanup(self.database.close)

    def install(self, records=RECORDS, **metadata):
        return self.database.import_translation(**(TRANSLATION | metadata), verses=records)

    def test_sealed_translations_are_immutable_and_imports_idempotent(self):
        self.assertEqual(self.install(), 4)
        self.assertEqual(self.install(reversed(RECORDS), code="test"), 0)
        with self.assertRaisesRegex(ValueError, "already installed"):
            self.install(RECORDS[:-1])
        with self.assertRaisesRegex(ValueError, "Duplicate verse"):
            self.install((*RECORDS, RECORDS[-1]), code="BAD")
        self.assertEqual([row["code"] for row in self.database.translations()], ["TEST"])
        with closing(sqlite3.connect(self.path)) as direct:
            for query in (
                "UPDATE scripture_texts SET body = 'changed'",
                "DELETE FROM scripture_texts",
                "INSERT OR REPLACE INTO scripture_texts VALUES ('test', 'GEN:1:1', 'changed')",
                "DELETE FROM translations",
                "UPDATE translations SET sealed_at = NULL",
                "UPDATE translation_books SET name = 'changed'",
                "UPDATE canonical_verses SET number = 4 WHERE number = 1",
            ):
                with self.subTest(query=query), self.assertRaises(sqlite3.IntegrityError):
                    direct.execute(query)
        self.database.check_integrity()

    def test_navigation_and_stable_ids_across_editions(self):
        self.install()
        other = [("GEN", "Genesis II", 1, 1, 1, "Alternate text")]
        self.install(other, code="SECOND")
        db = self.database
        self.assertEqual([row["code"] for row in db.books("test")], ["GEN", "EXO"])
        self.assertEqual(db.chapters("TEST", "GEN"), [1, 3])
        self.assertEqual(db.chapters("SECOND", "GEN"), [1])
        first, empty_verse = db.verses("TEST", "GEN", 1)
        self.assertEqual((empty_verse["id"], empty_verse["text"]), ("GEN:1:2", ""))
        second = db.verses("SECOND", "GEN", 1)[0]
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["text"], second["text"])
        self.assertEqual(db.next_chapter("TEST", "GEN", 1, 1), ("GEN", 3))
        self.assertEqual(db.next_chapter("TEST", "GEN", 3, 1), ("EXO", 1))
        self.assertEqual(db.next_chapter("TEST", "EXO", 1, -1), ("GEN", 3))
        self.assertIsNone(db.next_chapter("TEST", "GEN", 1, -1))
        self.assertIsNone(db.next_chapter("TEST", "EXO", 1, 1))

    def test_changes_and_revision_recovery_preserve_unicode_selection_and_labels(self):
        self.install()
        db = self.database
        first = db.create_folder("Reading")
        other = db.create_folder("Studies")
        label = db.create_label("Word study")
        anchor = ScriptureAnchor("GEN", 1, 1, "TEST", 6, 12)
        note = db.create_note("Selection", "First draft", first, [anchor, anchor], label_ids=[label])
        version = db.note_revisions(note)[0]["id"]
        self.assertEqual(db.note_anchors(note)[0]["quote"], "🕊 beta")
        self.assertEqual(len(db.note_anchors(note)), 1)
        graph_anchor = db.scripture_anchor(anchor)
        self.assertEqual(db.relationships(note)[0]["to_id"], graph_anchor)
        self.assertEqual(db.scripture_anchor(ScriptureAnchor("GEN", 1, 1, "test", 6, 12)), graph_anchor)
        with self.assertRaises(ValueError):
            db.update_note(note, "Invalid", "Will roll back", anchors=[ScriptureAnchor("GEN", 1, 1, "TEST", 0, 100)])
        with self.assertRaises(sqlite3.IntegrityError):
            db.update_note(note, "Invalid label", "Will roll back", label_ids=["missing"])
        self.assertEqual(db.note(note)["body"], "First draft")
        self.assertEqual(len(db.note_revisions(note)), 1)
        db.update_note(note, "Revised", "Second draft", other, [], label_ids=[])
        self.assertEqual(db.note_anchors(note), [])
        self.assertEqual(db.note_labels(note), [])
        db.restore_note_revision(note, version)
        self.assertEqual(db.note(note)["folder_id"], first)
        self.assertEqual(db.note(note)["title"], "Selection")
        self.assertEqual(db.note_anchors(note)[0]["quote"], "🕊 beta")
        self.assertEqual(db.note_labels(note)[0]["id"], label)
        self.assertEqual(len(db.note_revisions(note)), 3)

    def test_folder_reorganization_preserves_links_and_notes(self):
        self.install()
        db = self.database
        first = db.create_folder("Original")
        second = db.create_folder("Destination")
        child = db.create_folder("Nested", first)
        db.create_folder("Nested", second)
        with self.assertRaisesRegex(ValueError, "already exists"):
            db.create_folder("nested", first)
        note = db.create_note("Notes", "Body", first, [ScriptureAnchor("GEN", 1, 1)])
        link = db.relationships(note)[0]["id"]
        with self.assertRaisesRegex(sqlite3.IntegrityError, "ancestor"):
            db.move_folder(first, child)
        db.rename_folder(first, "Renamed")
        db.move_folder(first, second)
        self.assertEqual(db.note(note)["folder_id"], first)
        self.assertEqual(db.relationships(note)[0]["id"], link)
        db.delete_folder(first)
        self.assertEqual(db.note(note)["folder_id"], second)
        child_row = next(row for row in db.folders() if row["id"] == child)
        self.assertEqual((child_row["parent_id"], child_row["name"]), (second, "Nested (2)"))
        self.assertEqual(db.relationships(note)[0]["id"], link)
        self.assertEqual(len(db.note_revisions(note)), 2)

    def test_graph_decisions_require_explicit_user_review(self):
        db = self.database
        self.install()
        proposal = db.create_knowledge_object("interpretation", "Draft suggestion", origin="ai", source_detail="Fixture")
        anchor = db.scripture_anchor(ScriptureAnchor("GEN", 1, 1))
        edge = db.create_relationship(proposal, anchor, "supports", evidence="Needs review", origin="ai")
        self.assertEqual(db.knowledge_object(proposal)["status"], "draft")
        self.assertEqual(db.relationships(proposal)[0]["status"], "draft")
        with closing(sqlite3.connect(self.path)) as direct:
            with self.assertRaisesRegex(sqlite3.IntegrityError, "review record"):
                direct.execute(
                    "UPDATE knowledge_objects SET status = 'approved', reviewed_by = 'ai', reviewed_at = 'now' WHERE id = ?",
                    (proposal,),
                )
        db.review_knowledge(proposal, "investigate", "Reader", "Read surrounding passages")
        db.review_knowledge(edge, "rejected", "Reader", "The cited text is insufficient", relationship=True)
        self.assertEqual(db.knowledge_object(proposal)["status"], "investigate")
        self.assertEqual(db.relationships(proposal)[0]["status"], "rejected")
        with self.assertRaises(sqlite3.IntegrityError):
            db.create_relationship(proposal, "missing-endpoint", "supports")

    def test_one_database_writer_per_path_and_no_overwrite_of_open_database(self):
        other = self.directory / "separate.sqlite3"
        with self.assertRaisesRegex(ValueError, "already open"):
            Database(self.path)
        with closing(Database(other)) as other_database:
            note = other_database.create_note("Other profile", "Keep safe")
            with self.assertRaisesRegex(ValueError, "already open"):
                self.database.backup_to(other)
            self.assertEqual(other_database.note(note)["body"], "Keep safe")
        self.database.close()
        with closing(Database(self.path)) as reopened:
            self.assertEqual(reopened.notes(), [])

    def test_backup_restore_and_recovery_copy_are_readable(self):
        self.install()
        db = self.database
        note = db.create_note("Before backup", "First", anchors=[ScriptureAnchor("GEN", 1, 1)])
        snapshot = db.backup_to(self.directory / "backup.sqlite3")
        db.update_note(note, "Before restore", "Newer", anchors=[])
        previous = db.restore_from(snapshot)
        self.assertEqual(db.note(note)["title"], "Before backup")
        self.assertEqual(len(db.note_anchors(note)), 1)
        with closing(Database(previous)) as recovered:
            self.assertEqual(recovered.note(note)["body"], "Newer")
            self.assertEqual(recovered.note_anchors(note), [])
        db.close()
        with closing(Database(self.path)) as reopened:
            self.assertEqual(reopened.note(note)["body"], "First")
            reopened.check_integrity()

    def test_invalid_backup_and_restore_source_do_not_replace_data(self):
        db = self.database
        note = db.create_note("Keep this", "local text")
        with self.assertRaisesRegex(ValueError, "different file"):
            db.backup_to(self.path)
        with self.assertRaisesRegex(ValueError, "SQLite journals"):
            db.backup_to(self.path.with_name(self.path.name + "-wal"))
        unrelated = self.directory / "foreign.sqlite3"
        with closing(sqlite3.connect(unrelated)) as direct:
            direct.execute("CREATE TABLE another_app (item TEXT)")
        with self.assertRaisesRegex(ValueError, "not a Bible Brain database"):
            db.restore_from(unrelated)
        modified = db.backup_to(self.directory / "modified.sqlite3")
        with closing(sqlite3.connect(modified)) as direct:
            direct.execute("DROP TRIGGER scripture_locked_update")
        with self.assertRaisesRegex(ValueError, "schema has been changed"):
            db.restore_from(modified)
        self.assertFalse(list(self.directory.glob("*.before-restore-*.sqlite3")))
        self.assertEqual(db.note(note)["body"], "local text")

    def test_locked_live_database_fails_restore_without_losing_recent_data(self):
        db = self.database
        note = db.create_note("Before backup", "First")
        backup = db.backup_to(self.directory / "backup.sqlite3")
        db.update_note(note, "Before restore", "Keep this")
        db._connection.execute("PRAGMA busy_timeout = 0")
        with closing(sqlite3.connect(self.path)) as external, patch("bible_brain.database.BACKUP_BUSY_SECONDS", 0):
            external.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(ValueError, "SQLite is busy"):
                db.restore_from(backup)
        self.assertEqual(db.note(note)["body"], "Keep this")
        db.check_integrity()

    def test_original_language_import_is_separate_from_translation_alignment(self):
        self.install()
        resource = {
            "code": "STEP-DEMO-EL", "language": "el", "name": "STEP Bible Greek demo",
            "license": "CC BY 4.0", "source_url": "https://github.com/STEPBible/STEPBible-Data",
            "lexemes": [{"strongs": "G0001", "lemma": "ἄλφα", "transliteration": "alpha", "definition": "the first letter"}],
            "morphologies": [{"code": "N", "label": "Noun", "description": "nominal form"}],
            "tokens": [{"book": "GEN", "chapter": 1, "verse": 1, "ordinal": 0, "surface": "ἄλφα", "strongs": "G0001", "morphology": "N"}],
        }
        path = self.directory / "greek.json"
        path.write_text(json.dumps(resource, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.database.import_original_language(**{key: resource[key] for key in ("code", "language", "name", "license", "source_url")}, lexemes=resource["lexemes"], tokens=resource["tokens"], morphologies=resource["morphologies"]), 1)
        token = self.database.original_tokens("GEN", 1, 1)[0]
        self.assertEqual((token["strongs"], token["lemma"], token["morphology_label"]), ("G0001", "ἄλφα", "Noun"))
        self.assertEqual(len(self.database.lexeme_occurrences("G0001")), 1)
        with self.assertRaises(ValueError):
            self.database.import_original_language(**{key: resource[key] for key in ("code", "language", "name", "license", "source_url")}, lexemes=resource["lexemes"], tokens=[{**resource["tokens"][0], "surface": "changed"}], morphologies=resource["morphologies"])

    def test_cross_references_traces_and_structured_studies_survive_review_and_restore(self):
        self.install((
            ("GEN", "Genesis", 1, 3, 22, "Tree of life"),
            ("REV", "Revelation", 66, 2, 7, "Tree of life"),
            ("REV", "Revelation", 66, 22, 2, "Tree of life"),
            ("REV", "Revelation", 66, 22, 14, "Blessed"),
        ))
        db = self.database
        a = db.scripture_anchor(ScriptureAnchor("REV", 2, 7, "TEST", 0, 12))
        b = db.scripture_anchor(ScriptureAnchor("REV", 22, 2))
        c = db.scripture_anchor(ScriptureAnchor("REV", 22, 14))
        d = db.scripture_anchor(ScriptureAnchor("GEN", 3, 22))
        edge = db.create_relationship(a, b, "thematic_parallel", evidence="Restored access", source_uri="fixture")
        self.assertEqual(db.create_relationship(a, b, "thematic_parallel", evidence="same edge"), edge)
        db.review_knowledge(edge, "approved", "Reader", "Confirmed by study", relationship=True)
        db.update_relationship(edge, evidence="Refined supporting evidence")
        self.assertEqual(db._connection.execute("SELECT status FROM knowledge_relationships WHERE id=?", (edge,)).fetchone()[0], "draft")
        db.review_knowledge(edge, "approved", "Reader", "Confirmed after edit", relationship=True)
        trace = db.create_trace("Tree of Life", "Lost and restored access", "#4f7d4a")
        db.add_trace_member(trace, a); db.add_trace_member(trace, b); db.add_trace_member(trace, c); db.add_trace_member(trace, d)
        self.assertEqual(len(db.trace_members(trace)), 4)
        members = db.trace_members(trace)
        db.move_trace_member(members[-1]["relationship_id"], 0)
        self.assertEqual(db.trace_members(trace)[0]["relationship_id"], members[-1]["relationship_id"])
        study = db.create_study("Tree of Life study", "Access", "Genesis loss", "How is access restored?", conclusions="Restoration", anchors=[ScriptureAnchor("REV", 2, 7, "TEST", 0, 12), ScriptureAnchor("REV", 22, 2)], trace_ids=[trace])
        self.assertEqual(db.study(study)["summary"], "Access")
        original_revision = db.note_revisions(study)[0]["id"]
        db.update_study(study, "Tree of Life study revised", "Access", "Genesis loss", "How is access restored?", conclusions="Restoration confirmed")
        self.assertEqual(db.study(study)["conclusions"], "Restoration confirmed")
        self.assertEqual(db.knowledge_object(study)["status"], "draft")
        db.restore_note_revision(study, original_revision)
        self.assertEqual(db.study(study)["conclusions"], "Restoration")
        image = self.directory / "tree.png"
        image.write_bytes(b"fake-png-bytes")
        attachment = db.attach_file(study, image)
        self.assertEqual(db.attachment_data(attachment)["size"], len(b"fake-png-bytes"))
        self.assertEqual(len(db.relationships(study)), 3)
        backup = db.backup_to(self.directory / "graph-backup.sqlite3")
        db.close()
        with closing(Database(self.path)) as reopened:
            self.assertEqual(len(reopened.trace_members(trace)), 4)
            self.assertEqual(reopened.study(study)["conclusions"], "Restoration")
            self.assertEqual(len(reopened.attachments(study)), 1)
            reopened.restore_from(backup)
            self.assertEqual(reopened._connection.execute("SELECT status FROM knowledge_relationships WHERE id=?", (edge,)).fetchone()[0], "approved")


if __name__ == "__main__":
    unittest.main()
