import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from bible_brain.datasets import BUNDLED_WEB
from bible_brain.session import Session


class SessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.session = Session(self.directory)
        self.addCleanup(lambda: self.session.close())

    def test_repository_data_covers_complete_reader(self):
        with gzip.open(BUNDLED_WEB, "rt", encoding="utf-8") as stream:
            bundled = json.load(stream)
        self.assertEqual(len(bundled["verses"]), 31_103)
        self.assertEqual(sum(row[5] == "" for row in bundled["verses"]), 5)
        database = self.session.database
        self.assertEqual(len(database.books("WEBP")), 66)
        self.assertEqual(database.verses("WEBP", "GEN", 1)[0]["text"], bundled["verses"][0][5])
        self.assertEqual(database.next_chapter("WEBP", "GEN", 50, 1), ("EXO", 1))
        self.assertIsNone(database.next_chapter("WEBP", "REV", 22, 1))
        self.assertEqual(self.session.import_dataset(BUNDLED_WEB), 0)

    def test_imports_another_local_translation_and_rejects_invalid_file(self):
        with gzip.open(BUNDLED_WEB, "rt", encoding="utf-8") as stream:
            sample = json.load(stream)
        sample.update(code="TEST", name="WEB test excerpt", verses=sample["verses"][:2])
        translation = self.directory / "sample.json"
        translation.write_text(json.dumps(sample), encoding="utf-8")
        self.assertEqual(self.session.import_dataset(translation), 2)
        self.assertEqual(self.session.database.chapters("TEST", "GEN"), [1])
        duplicate = sample["verses"][0].copy()
        duplicate[3] = True
        sample.update(code="BAD", verses=[*sample["verses"], duplicate])
        translation.write_text(json.dumps(sample), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.session.import_dataset(translation)
        self.assertEqual({row["code"] for row in self.session.database.translations()}, {"TEST", "WEBP"})

        broken_archive = self.directory / "corrupt.json.gz"
        archive = gzip.compress(b"{}", mtime=0)
        broken_archive.write_bytes(archive[:10] + b"\x07" + archive[11:])
        with self.assertRaisesRegex(ValueError, "valid UTF-8 JSON"):
            self.session.import_dataset(broken_archive)

    def test_database_and_appearance_persist_without_moving_research(self):
        original = self.session.database_path
        note_id = self.session.database.create_note("Original note", "Saved in the original profile")
        alternate = self.directory / "alternate.sqlite3"
        self.session.switch_database(alternate)
        self.session.set_appearance("Dark", 22)
        self.assertEqual(self.session.database.notes(), [])
        self.session.close()
        self.session = Session(self.directory)
        self.assertEqual(self.session.database_path, alternate)
        self.assertEqual((self.session.appearance, self.session.text_size), ("Dark", 22))
        self.session.switch_database(original)
        self.assertEqual(self.session.database.note(note_id)["title"], "Original note")

    def test_invalid_database_does_not_replace_session(self):
        test_file = self.directory / "unrelated.sqlite3"
        with sqlite3.connect(test_file) as other:
            other.execute("CREATE TABLE unrelated(id INTEGER)")
        other.close()
        original = self.session.database_path
        with self.assertRaises((ValueError, sqlite3.Error)):
            self.session.switch_database(test_file)
        self.assertEqual(self.session.database_path, original)
        self.assertEqual(self.session.database.translations()[0]["code"], "WEBP")

    def test_unavailable_custom_database_is_not_recreated_on_start(self):
        path = self.directory / "custom.sqlite3"
        self.session.switch_database(path)
        self.session.close()
        path.rename(self.directory / "moved.sqlite3")
        with self.assertRaisesRegex(ValueError, "configured database"):
            Session(self.directory)
        self.assertFalse(path.exists())

    def test_restore_and_reopen_preserve_notes_and_previous_state(self):
        database = self.session.database
        note_id = database.create_note("Earlier title", "Study in progress")
        backup = self.directory / "study backup.sqlite3"
        self.session.backup(backup)
        database.update_note(note_id, "Later title", "Revised")
        previous = self.session.restore(backup)
        self.assertTrue(previous.is_file())
        self.assertEqual(self.session.database.note(note_id)["title"], "Earlier title")
        self.session.close()
        self.session = Session(self.directory)
        self.assertEqual(self.session.database.note(note_id)["title"], "Earlier title")
        self.session.restore(previous)
        self.assertEqual(self.session.database.note(note_id)["title"], "Later title")
