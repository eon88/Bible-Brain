import os
import unittest

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from bible_brain.database import ScriptureAnchor
from bible_brain.reader import ChapterReader


class ReaderSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.reader = ChapterReader()
        self.addCleanup(self.reader.close)
        self.reader.show_chapter(
            "TEST", "GEN", 1, "Genesis 1", "Selection fixture",
            [{"number": 1, "text": "A 🌿 word"}, {"number": 2, "text": "Other words"},
             {"number": 3, "text": ""}],
            19, {"soft": "#666666", "ink": "#222222", "selected": "#eeeeee"},
        )
        self.selections = []
        self.reader.scriptureSelected.connect(self.selections.append)

    def test_selection_converts_qt_offsets_to_unicode_offsets(self):
        first, second, _ = self.reader.spans
        cursor = self.reader.textCursor()
        cursor.setPosition(first.text_start + 2)
        cursor.setPosition(second.text_start + 5, QTextCursor.MoveMode.KeepAnchor)
        self.reader.setTextCursor(cursor)
        self.reader.publish_selection()
        self.assertEqual(self.selections[-1], [
            ScriptureAnchor("GEN", 1, 1, "TEST", 2, 8),
            ScriptureAnchor("GEN", 1, 2, "TEST", 0, 5),
        ])

    def test_empty_publisher_verse_can_be_selected_by_address(self):
        anchor = ScriptureAnchor("GEN", 1, 3)
        self.reader.select_anchor(anchor)
        self.assertEqual(self.selections[-1], [anchor])
