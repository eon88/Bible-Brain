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
    QPlainTextEdit, QPushButton, QSpinBox, QToolButton,
)

from bible_brain.database import ScriptureAnchor
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

    def test_reader_modes_selection_actions_and_companion_state(self):
        reader = self.window.reader
        span = reader.spans[0]
        cursor = reader.textCursor()
        cursor.setPosition(span.text_start)
        cursor.setPosition(span.text_start + 4, QTextCursor.MoveMode.KeepAnchor)
        reader.setTextCursor(cursor)
        reader.publish_selection()
        self.assertTrue(self.window.findChild(QToolButton, "saveSelection").isVisible())
        self.window.graph.pin_selection(self.window.selection)
        self.assertEqual(self.session.ui_state["companion_pin"]["label"], "GEN 1:1")
        self.assertTrue(self.session.ui_state["companion_pin"]["id"])
        self.assertEqual(self.session.ui_state["companion_history"][0]["id"], self.session.ui_state["companion_pin"]["id"])
        section = self.window.graph.findChild(QToolButton, "sectionToggle_connections_results")
        section.setChecked(False)
        self.assertFalse(self.session.ui_state["companion_sections"][self.session.ui_state["companion_pin"]["id"]]["connections:results"])
        self.window.graph.pin_selection(self.window.selection)
        self.assertFalse(section.isChecked())
        self.window.mode_selector.setCurrentText("Exploration")
        self.assertEqual(self.window.reader_mode, "Exploration")
        self.window.filter_actions["connections"].setChecked(False)
        self.assertFalse(self.session.ui_state["exploration_filters"]["connections"])
        self.window.mode_selector.setCurrentText("Mapping")
        self.assertTrue(self.window.mapping_panel.isVisible())
        self.window.mode_selector.setCurrentText("Reading")
        self.assertTrue(self.window.reader.isVisible())

    def test_companion_adapts_to_bottom_sheet_at_narrow_width(self):
        self.window.resize(700, 760)
        self.window._show_study()
        self.app.processEvents()
        self.assertEqual(self.window.splitter.orientation(), Qt.Orientation.Vertical)
        self.assertTrue(self.window.graph.isVisible())
        sizes = self.window.splitter.sizes()
        self.assertGreaterEqual(len(sizes), 2)
        self.assertGreater(sizes[0], 0)
        self.assertGreater(sizes[self.window.splitter.indexOf(self.window.graph)], 0)

    def test_phone_portrait_keeps_reader_visible_above_companion_sheet(self):
        self.window.resize(390, 844)
        self.window._show_study()
        self.app.processEvents()
        self.assertEqual(self.window.splitter.orientation(), Qt.Orientation.Vertical)
        sizes = self.window.splitter.sizes()
        graph_index = self.window.splitter.indexOf(self.window.graph)
        self.assertGreaterEqual(sizes[0], 260)
        self.assertGreaterEqual(sizes[graph_index], 280)
        self.assertTrue(self.window.reader.isVisible())
        self.assertTrue(self.window.graph.isVisible())

    def test_clean_launch_is_reading_first_with_companion_closed(self):
        self.assertEqual(self.window.reader_mode, "Reading")
        self.assertFalse(self.window.graph.isVisible())
        self.assertFalse(self.window.workspace.isVisible())
        self.assertFalse(self.window.investigate.isVisible())
        self.assertIn("In the beginning, God created", self.window.reader.toPlainText())

    def test_companion_sections_are_independent_and_persisted(self):
        self.window._show_study()
        self.app.processEvents()
        connection = self.window.graph.findChild(QToolButton, "sectionToggle_connections_results")
        trace = self.window.graph.findChild(QToolButton, "sectionToggle_traces_saved")
        study = self.window.graph.findChild(QToolButton, "sectionToggle_studies_dossiers")
        self.assertTrue(connection.isChecked() and trace.isChecked() and study.isChecked())
        connection.setChecked(False)
        trace.setChecked(False)
        state = self.session.ui_state["companion_sections"]
        pin = self.session.ui_state.get("companion_pin", {}).get("id", "none")
        self.assertFalse(state[pin]["connections:results"])
        self.assertFalse(state[pin]["traces:saved"])
        self.assertTrue(state[pin].get("studies:dossiers", True))

    def test_contextual_companion_actions_are_exposed(self):
        self.window._show_study()
        self.app.processEvents()
        self.assertIsNotNone(self.window.graph.findChild(QPushButton, "askAboutPassage"))
        self.assertIsNotNone(self.window.graph.findChild(QPushButton, "interpretThroughLens"))
        self.window._show_traces()
        self.app.processEvents()
        self.assertIsNotNone(self.window.graph.findChild(QPushButton, "companionOriginalLanguage"))

    def test_tree_of_life_journey_preserves_trace_order_and_origin(self):
        translation = self.window.edition.currentData()
        origin = ScriptureAnchor("REV", 2, 7, translation)
        second = ScriptureAnchor("REV", 22, 2, translation)
        third = ScriptureAnchor("GEN", 3, 22, translation)
        for anchor in (origin, second, third):
            self.session.database.scripture_anchor(anchor)
        trace_id = self.session.database.create_trace("Tree of Life", "Lost and restored access", "#4f7d4a")
        for position, anchor in enumerate((origin, second, third)):
            self.session.database.add_trace_member(trace_id, self.session.database.scripture_anchor(anchor), position)
        self.window.selection = [origin]
        self.window._open_reference(origin)
        self.window.graph.set_selection([origin])
        self.window._open_companion_tab(1)
        self.window.graph._refresh_traces()
        self.window.graph.traces.setCurrentRow(0)
        self.window.graph.active.setChecked(True)
        self.app.processEvents()
        self.assertEqual(self.window.trace_session_id, trace_id)
        self.assertEqual(self.window.trace_index, 0)
        self.assertEqual(self.window.trace_progress.text(), "1 of 3")
        self.window._trace_step(1)
        self.assertEqual(self.window.trace_index, 1)
        self.assertEqual(self.window.trace_progress.text(), "2 of 3")
        self.window._close_trace_from_reader()
        self.assertIsNone(self.window.trace_session_id)
        self.assertEqual((self.window.reader.book, self.window.reader.chapter), ("REV", 2))
