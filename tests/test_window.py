import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QLineEdit, QListWidget, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox,
)

from bible_brain.session import Session
from bible_brain.window import MainWindow


class ApplicationLaunchTests(unittest.TestCase):
    def test_main_opens_new_profile_and_exits_cleanly(self):
        # Run a real application event loop in a fresh process, then close it without interaction.
        launch = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from bible_brain import __main__ as entry

def application_for_test(args):
    app = QApplication(args)
    QTimer.singleShot(0, app.quit)
    return app

entry.QApplication = application_for_test
sys.exit(entry.main(['--data-dir', sys.argv[1]]))
"""
        with tempfile.TemporaryDirectory() as path:
            profile = Path(path)
            process = subprocess.run(
                [sys.executable, "-c", launch, path],
                env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertFalse((profile / "application.lock").exists())
            connection = sqlite3.connect((profile / "library.sqlite3").as_uri() + "?mode=ro", uri=True)
            try:
                self.assertEqual(connection.execute("SELECT count(*) FROM scripture_texts").fetchone()[0], 31_103)
            finally:
                connection.close()


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.session = Session(Path(directory.name))
        self.addCleanup(self.session.close)
        self.window = MainWindow(self.session)
        self.addCleanup(self._close_window)
        self.window.show()
        self.app.processEvents()

    def _close_window(self):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
            self.window.close()

    def click(self, name):
        button = self.window.findChild(QPushButton, name)
        self.assertIsNotNone(button, name)
        self.assertTrue(button.isVisible() and button.isEnabled(), name)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.app.processEvents()

    def test_chapter_navigation_and_scripture_linked_note(self):
        reader = self.window.reader
        self.assertIn("In the beginning, God created", reader.toPlainText())
        chapter = self.window.findChild(QComboBox, "chapterSelector")
        self.click("nextChapter")
        self.assertEqual(chapter.currentData(), 2)
        self.click("previousChapter")
        self.assertEqual(chapter.currentData(), 1)

        span = reader.spans[0]
        cursor = reader.textCursor()
        cursor.setPosition(span.text_start)
        cursor.setPosition(span.text_start + len("In the beginning"), QTextCursor.MoveMode.KeepAnchor)
        reader.setTextCursor(cursor)
        reader.publish_selection()
        self.click("newSelectionNote")
        references = self.window.findChild(QListWidget, "noteReferences")
        self.assertEqual(references.count(), 1)

        title = self.window.findChild(QLineEdit, "noteTitle")
        body = self.window.findChild(QPlainTextEdit, "noteBody")
        title.setText("Creation study")
        body.setPlainText("Opening observation")
        self.click("saveNote")
        body.setPlainText("Revised observation")
        self.click("saveNote")

        database = self.session.database
        note = database.notes()[0]
        self.assertEqual(note["title"], "Creation study")
        self.assertEqual(note["body"], "Revised observation")
        anchor = database.note_anchors(note["id"])[0]
        self.assertEqual((anchor["book"], anchor["chapter"], anchor["verse"]), ("GEN", 1, 1))
        self.assertEqual(anchor["quote"], "In the beginning")
        self.assertIn("Opening observation", [row["body"] for row in database.note_revisions(note["id"])])

    def test_settings_can_back_up_and_restore_the_active_library(self):
        note_id = self.session.database.create_note("Original", "Before backup")
        backup = str(self.session.data_dir / "backup.sqlite3")
        errors = []

        def use_settings():
            dialog = self.window.findChild(QDialog, "applicationSettings")
            try:
                self.click("backupDatabase")
                self.session.database.update_note(note_id, "Revised", "After backup")
                self.click("restoreDatabase")
                dialog.findChild(QComboBox, "appearanceSelector").setCurrentText("Dark")
                dialog.findChild(QSpinBox, "readerTextSize").setValue(21)
            except Exception as error:
                errors.append(error)
                dialog.reject()
            else:
                dialog.accept()

        with (
            patch.object(QFileDialog, "getSaveFileName", return_value=(backup, "")),
            patch.object(QFileDialog, "getOpenFileName", return_value=(backup, "")),
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(QMessageBox, "information") as information,
            patch.object(QMessageBox, "warning") as warning,
        ):
            QTimer.singleShot(0, use_settings)
            self.click("openSettings")

        if errors:
            raise errors[0]
        self.assertEqual(information.call_count, 2)
        warning.assert_not_called()
        self.assertEqual(self.session.database.note(note_id)["body"], "Before backup")
        self.assertEqual((self.session.appearance, self.session.text_size), ("Dark", 21))
