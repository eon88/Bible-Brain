"""Windows presentation for the local Scripture reader and research session."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .reader import ChapterReader
from .session import APPEARANCES, TEXT_SIZES
from .typography import load_fonts
from .workspace import DATA_ERRORS, ResearchWorkspace, SelectBox, button, item_heading
from .graph import GraphWorkspace
from .investigate import InvestigatePanel
from .lenses import LensPanel
from .conversation_panel import ConversationPanel
from .discovery import DiscoveryPanel


LOGGER = logging.getLogger(__name__)
LIGHT = {
    "paper": "#faf8f2", "surface": "#fffdf8", "chrome": "#f3efe5",
    "line": "#ded6c6", "ink": "#2e2a23", "soft": "#695e50",
    "accent": "#8a402c", "hover": "#713221", "accent_text": "#ffffff",
    "selected": "#efe4d5", "disabled": "#a3988b",
}
DARK = {
    "paper": "#20211f", "surface": "#282924", "chrome": "#252621",
    "line": "#45453d", "ink": "#f2ebdf", "soft": "#c0b4a1",
    "accent": "#e8ad92", "hover": "#f9c2a8", "accent_text": "#322016",
    "selected": "#433831", "disabled": "#8d8378",
}


class MainWindow(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.serif, self.sans = load_fonts()
        self.session = session
        self.selection = []
        self.book_names = {}
        self._quote_key = None
        self._quote_verses = {}
        self.setWindowTitle("Bible Brain")
        self.setObjectName("mainWindow")
        self.setMinimumSize(640, 545)
        self.resize(1170, 800)

        self.page = QWidget()
        self.page.setObjectName("appPage")
        layout = QVBoxLayout(self.page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._make_header())

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self._make_scripture())
        self.workspace = ResearchWorkspace(session, self.format_anchor, self.notify, self.show_error)
        self.workspace.closeRequested.connect(lambda: self.research_button.setChecked(False))
        self.workspace.navigateRequested.connect(self._open_reference)
        self.splitter.addWidget(self.workspace)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 0)
        self.workspace.hide()
        layout.addWidget(self.splitter, 1)
        self.graph = GraphWorkspace(session, self.notify, self.show_error)
        self.graph.navigateRequested.connect(self._open_reference)
        self.graph.traceChanged.connect(self._set_trace)
        self.splitter.addWidget(self.graph)
        self.graph.hide()
        self.investigate = InvestigatePanel(session, self.notify, self.show_error)
        self.investigate.navigateRequested.connect(self._open_reference)
        self.splitter.addWidget(self.investigate)
        self.investigate.hide()
        self.lenses = LensPanel(session, self.notify, self.show_error)
        self.splitter.addWidget(self.lenses)
        self.lenses.hide()
        self.conversation = ConversationPanel(session, self.notify, self.show_error)
        self.splitter.addWidget(self.conversation)
        self.conversation.hide()
        self.discovery = DiscoveryPanel(session, self.notify, self.show_error)
        self.splitter.addWidget(self.discovery)
        self.discovery.hide()
        self.setCentralWidget(self.page)

        status = QStatusBar()
        status.setObjectName("sessionStatus")
        status.setSizeGripEnabled(False)
        status.messageChanged.connect(lambda message: status.setVisible(bool(message)))
        self.setStatusBar(status)
        status.hide()

        self._setup_shortcuts()
        self._apply_theme()
        QApplication.styleHints().colorSchemeChanged.connect(self._on_system_theme)
        self.reload_database()
        self.reader.setFocus()

    @property
    def database(self):
        return self.session.database

    def _make_header(self):
        header = QFrame()
        header.setObjectName("appHeader")
        header.setFixedHeight(65)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(25, 0, 24, 0)
        layout.setSpacing(9)

        brand = QLabel("Bible Brain")
        brand.setObjectName("wordmark")
        layout.addWidget(brand)
        layout.addStretch(1)

        self.research_button = QPushButton("Research")
        self.research_button.setObjectName("toggleResearch")
        self.research_button.setCheckable(True)
        self.research_button.setToolTip("Show or hide research (Ctrl+Shift+R)")
        self.research_button.toggled.connect(self._toggle_research)
        layout.addWidget(self.research_button)
        self.explore_button = QPushButton("Explore")
        self.explore_button.setObjectName("toggleExplore")
        self.explore_button.setCheckable(True)
        self.explore_button.toggled.connect(self._toggle_explore)
        layout.addWidget(self.explore_button)
        self.investigate_button = QPushButton("Investigate")
        self.investigate_button.setObjectName("toggleInvestigate")
        self.investigate_button.setCheckable(True)
        self.investigate_button.toggled.connect(self._toggle_investigate)
        layout.addWidget(self.investigate_button)
        self.lenses_button = QPushButton("Lenses")
        self.lenses_button.setObjectName("toggleLenses")
        self.lenses_button.setCheckable(True)
        self.lenses_button.toggled.connect(lambda checked: self.lenses.setVisible(checked))
        layout.addWidget(self.lenses_button)
        self.conversation_button = QPushButton("Process Conversation")
        self.conversation_button.setObjectName("processConversation")
        self.conversation_button.setCheckable(True)
        self.conversation_button.toggled.connect(lambda checked: self.conversation.setVisible(checked))
        layout.addWidget(self.conversation_button)
        self.discovery_button = QPushButton("Discover Connections")
        self.discovery_button.setObjectName("discoverConnections")
        self.discovery_button.setCheckable(True)
        self.discovery_button.toggled.connect(lambda checked: self.discovery.setVisible(checked))
        layout.addWidget(self.discovery_button)
        layout.addWidget(button("Settings", "openSettings", self._show_settings, "quiet"))
        return header

    def _make_scripture(self):
        scripture = QWidget()
        scripture.setObjectName("scripturePane")
        layout = QVBoxLayout(scripture)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("chapterToolbar")
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(22, 9, 22, 9)
        controls.setSpacing(8)

        self.previous = button("‹", "previousChapter", lambda: self._step(-1), "quiet")
        self.previous.setAccessibleName("Previous chapter")
        self.previous.setToolTip("Previous chapter (Alt+Left)")
        self.next = button("›", "nextChapter", lambda: self._step(1), "quiet")
        self.next.setAccessibleName("Next chapter")
        self.next.setToolTip("Next chapter (Alt+Right)")
        controls.addWidget(self.previous)
        controls.addWidget(self.next)
        controls.addSpacing(7)

        self.book = self._combo("bookSelector", "Book")
        self.book.setMinimumContentsLength(11)
        self.book.currentIndexChanged.connect(self._change_book)
        controls.addWidget(self.book)
        self.chapter = self._combo("chapterSelector", "Chapter")
        self.chapter.setMinimumContentsLength(7)
        self.chapter.currentIndexChanged.connect(self._render_chapter)
        controls.addWidget(self.chapter)
        controls.addStretch(1)
        self.edition = self._combo("translationSelector", "Translation")
        self.edition.setMinimumContentsLength(5)
        self.edition.currentIndexChanged.connect(self._change_translation)
        controls.addWidget(self.edition)
        self.import_button = button(
            "Import translation…", "importEmptyTranslation", self._import_translation, "primary"
        )
        controls.addWidget(self.import_button)
        layout.addWidget(toolbar)

        self.reader = ChapterReader(self.serif, self.sans)
        self.reader.scriptureSelected.connect(self._set_selection)
        layout.addWidget(self.reader, 1)

        self.selection_bar = QFrame()
        self.selection_bar.setObjectName("selectionBar")
        selection_layout = QHBoxLayout(self.selection_bar)
        selection_layout.setContentsMargins(24, 7, 24, 7)
        self.selection_label = QLabel()
        self.selection_label.setObjectName("currentScriptureSelection")
        self.selection_label.setTextFormat(Qt.TextFormat.PlainText)
        self.selection_label.setProperty("role", "selection")
        selection_layout.addWidget(self.selection_label, 1)
        clear = button("Clear", "clearSelection", self._clear_selection, "quiet")
        selection_layout.addWidget(clear)
        selection_layout.addWidget(button("Original language", "originalLanguage", self._show_original_language, "quiet"))
        selection_layout.addWidget(button("New note", "newSelectionNote", self._note_from_selection, "primary"))
        layout.addWidget(self.selection_bar)
        self.selection_bar.hide()
        return scripture

    @staticmethod
    def _combo(name, label):
        combo = SelectBox()
        combo.setObjectName(name)
        combo.setAccessibleName(label)
        combo.setToolTip(label)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        return combo

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self._step(-1))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self._step(1))
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.research_button.toggle)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._show_settings)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save_note_shortcut)

    def _save_note_shortcut(self):
        if self.workspace.isVisible() and self.workspace.stack.currentIndex() == 1:
            self.workspace.save()

    def _toggle_research(self, enabled):
        self.workspace.setVisible(enabled)
        if enabled:
            if self.splitter.orientation() == Qt.Orientation.Horizontal:
                width = self.splitter.width()
                side = min(420, max(340, width // 3))
                self.splitter.setSizes([width - side, side])
            else:
                height = self.splitter.height()
                self.splitter.setSizes([height * 2 // 5, height * 3 // 5])

    def _toggle_explore(self, enabled):
        self.graph.setVisible(enabled)
        if enabled:
            self.graph.set_selection(self.selection)

    def _toggle_investigate(self, enabled):
        self.investigate.setVisible(enabled)
        if enabled:
            self.investigate.set_selection(self.selection)

    def _set_trace(self, trace_id):
        self.discovery.set_trace(trace_id)
        if not trace_id:
            self.reader.highlight_verses([])
            return
        verses = []
        for row in self.database.trace_members(trace_id):
            if row["verse_id"]:
                book, chapter, verse = row["verse_id"].split(":")
                if book == self.reader.book and int(chapter) == self.reader.chapter:
                    verses.append(int(verse))
        self.reader.highlight_verses(verses, "#e8d7a5")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        orientation = Qt.Orientation.Vertical if self.width() < 870 else Qt.Orientation.Horizontal
        if orientation != self.splitter.orientation():
            self.splitter.setOrientation(orientation)
            if self.workspace.isVisible():
                self._toggle_research(True)

    def reload_database(self):
        self._reload_editions()
        self.workspace.refresh()

    def _reload_editions(self):
        previous = self._location()
        self.book_names.clear()
        self._quote_key = None
        rows = self.database.translations()
        self.edition.blockSignals(True)
        self.edition.clear()
        for row in rows:
            self.edition.addItem(row["code"].upper(), row["code"])
            self.edition.setItemData(self.edition.count() - 1, row["name"], Qt.ItemDataRole.ToolTipRole)
        self.edition.setCurrentIndex(max(0, self.edition.findData(previous[0])))
        self.edition.blockSignals(False)
        self.import_button.setVisible(not rows)
        for control in (self.edition, self.book, self.chapter):
            control.setEnabled(bool(rows))
        self._change_translation(preferred=previous[1:])

    def _location(self):
        return self.edition.currentData(), self.book.currentData(), self.chapter.currentData()

    def _change_translation(self, _index=0, preferred=None):
        preferred = preferred or self._location()[1:]
        translation = self.edition.currentData()
        self.book.blockSignals(True)
        self.book.clear()
        if translation:
            for row in self.database.books(translation):
                self.book.addItem(row["name"], row["code"])
                self.book_names[row["code"]] = row["name"]
        self.book.setCurrentIndex(max(0, self.book.findData(preferred[0])))
        self.book.blockSignals(False)
        self._change_book(preferred=preferred[1])

    def _change_book(self, _index=0, preferred=None):
        translation, book, _ = self._location()
        self.chapter.blockSignals(True)
        self.chapter.clear()
        if translation and book:
            for chapter in self.database.chapters(translation, book):
                self.chapter.addItem(f"Chapter {chapter}", chapter)
        self.chapter.setCurrentIndex(max(0, self.chapter.findData(preferred)))
        self.chapter.blockSignals(False)
        self._render_chapter()

    def _render_chapter(self):
        self._set_selection([])
        translation, book, chapter = self._location()
        if not (translation and book and chapter):
            self.previous.setEnabled(False)
            self.next.setEnabled(False)
            self.reader.show_message(
                "Import a Bible translation",
                "Choose a licensed local Scripture dataset to begin reading.",
                self.colors,
            )
            return
        title = f"{self.book.currentText()} {chapter}"
        edition = self.edition.itemData(self.edition.currentIndex(), Qt.ItemDataRole.ToolTipRole)
        self.reader.show_chapter(
            translation, book, chapter, title, edition,
            self.database.verses(translation, book, chapter), self.session.text_size, self.colors,
        )
        self.previous.setEnabled(self.database.next_chapter(translation, book, chapter, -1) is not None)
        self.next.setEnabled(self.database.next_chapter(translation, book, chapter, 1) is not None)

    def _goto_chapter(self, translation, book, chapter):
        edition_index = self.edition.findData(translation)
        if edition_index < 0:
            return False
        self.edition.blockSignals(True)
        self.edition.setCurrentIndex(edition_index)
        self.edition.blockSignals(False)
        self._change_translation(preferred=(book, chapter))
        return self._location() == (translation, book, chapter)

    def _step(self, direction):
        translation, book, chapter = self._location()
        if not (translation and book and chapter):
            return
        destination = self.database.next_chapter(translation, book, chapter, direction)
        if destination is not None:
            self._goto_chapter(translation, *destination)

    def _set_selection(self, anchors):
        self.selection = list(anchors)
        self.workspace.set_selection(self.selection)
        self.graph.set_selection(self.selection)
        self.investigate.set_selection(self.selection)
        self.discovery.set_selection(self.selection)
        if anchors:
            label = self.format_anchor(anchors[0])
            if len(anchors) > 1:
                label += f"–{anchors[-1].verse}"
            self.selection_label.setText(label)
        self.selection_bar.setVisible(bool(anchors))

    def _clear_selection(self):
        cursor = self.reader.textCursor()
        cursor.clearSelection()
        self.reader.setTextCursor(cursor)
        self.reader.setExtraSelections([])
        self._set_selection([])

    def _show_original_language(self):
        if not self.selection:
            return
        rows = []
        seen = set()
        for anchor in self.selection:
            for row in self.database.original_tokens(anchor.book, anchor.chapter, anchor.verse):
                if row["id"] not in seen:
                    seen.add(row["id"]); rows.append(row)
        dialog = QDialog(self)
        dialog.setWindowTitle("Original-language information")
        dialog.resize(720, 460)
        layout = QVBoxLayout(dialog)
        if not rows:
            layout.addWidget(QLabel("No original-language resource is installed for this passage.\n"
                                    "Import a licensed Bible Brain original-language JSON resource in Settings."))
        else:
            note = QLabel("Dictionary definitions are lexical data. Contextual meaning is not inferred here; "
                          "record and evaluate contextual conclusions in Research notes.")
            note.setWordWrap(True); layout.addWidget(note)
            text = QTextBrowser(); text.setOpenLinks(False)
            lines = []
            for row in rows:
                morphology = row["morphology_label"] or row["morphology_code"] or "Not supplied"
                definition = row["dictionary_definition"] or "No dictionary definition supplied"
                lines.append(f"{row['verse_id']} · {row['ordinal'] + 1}. {row['surface']}  —  {row['strongs']}\n"
                             f"Lemma: {row['lemma']}  | Transliteration: {row['transliteration']}\n"
                             f"Form: {morphology}\nDictionary definition: {definition}\n")
            text.setPlainText("\n".join(lines)); layout.addWidget(text)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        controls.rejected.connect(dialog.reject); controls.accepted.connect(dialog.accept); layout.addWidget(controls)
        dialog.exec()

    def _note_from_selection(self):
        self.research_button.setChecked(True)
        self.workspace.new_note(anchors=self.selection)

    def _open_reference(self, anchor):
        if anchor.translation:
            editions = [anchor.translation]
        else:
            current = self.edition.currentData()
            editions = [current] + [
                self.edition.itemData(i) for i in range(self.edition.count())
                if self.edition.itemData(i) != current
            ]
        for translation in editions:
            if not translation:
                continue
            verses = self.database.verses(translation, anchor.book, anchor.chapter)
            if any(verse["number"] == anchor.verse for verse in verses):
                if self._location() != (translation, anchor.book, anchor.chapter):
                    self._goto_chapter(translation, anchor.book, anchor.chapter)
                self.reader.select_anchor(anchor)
                return
        self.notify("This reference is unavailable in the installed translations.")

    def format_anchor(self, anchor, with_quote=False):
        label = f"{self.book_names.get(anchor.book, anchor.book)} {anchor.chapter}:{anchor.verse}"
        if anchor.translation and with_quote:
            key = (anchor.translation, anchor.book, anchor.chapter)
            if key != self._quote_key:
                self._quote_verses = {
                    verse["number"]: verse["text"] for verse in self.database.verses(*key)
                }
                self._quote_key = key
            text = self._quote_verses.get(anchor.verse, "")
            label += f" · {anchor.translation.upper()} · “{text[anchor.start:anchor.end]}”"
        return label

    def _on_system_theme(self, _scheme):
        if self.session.appearance == "System":
            self._refresh_appearance()

    def _refresh_appearance(self):
        scrollbar = self.reader.verticalScrollBar()
        position = scrollbar.value() / max(1, scrollbar.maximum())
        self._apply_theme()
        self._render_chapter()
        scrollbar.setValue(round(position * scrollbar.maximum()))

    def _apply_theme(self):
        system_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        dark = self.session.appearance == "Dark" or (self.session.appearance == "System" and system_dark)
        self.colors = DARK if dark else LIGHT
        c = self.colors
        palette = QPalette()
        for role, color in {
            QPalette.ColorRole.Window: "chrome",
            QPalette.ColorRole.WindowText: "ink",
            QPalette.ColorRole.Base: "surface",
            QPalette.ColorRole.AlternateBase: "selected",
            QPalette.ColorRole.Button: "surface",
            QPalette.ColorRole.ButtonText: "ink",
            QPalette.ColorRole.Text: "ink",
            QPalette.ColorRole.PlaceholderText: "soft",
            QPalette.ColorRole.Highlight: "accent",
            QPalette.ColorRole.HighlightedText: "accent_text",
            QPalette.ColorRole.ToolTipBase: "surface",
            QPalette.ColorRole.ToolTipText: "ink",
        }.items():
            palette.setColor(role, QColor(c[color]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["disabled"]))
        self.setPalette(palette)
        self.setStyleSheet(_stylesheet(c, self.serif, self.sans))

    def _show_settings(self):
        dialog = QDialog(self)
        dialog.setObjectName("applicationSettings")
        dialog.setWindowTitle("Bible Brain settings")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(21, 19, 21, 19)
        layout.setSpacing(12)

        layout.addWidget(item_heading("Appearance"))
        appearance_form = QFormLayout()
        appearance = self._combo("appearanceSelector", "Theme")
        appearance.addItems(APPEARANCES)
        appearance.setCurrentText(self.session.appearance)
        appearance_form.addRow("Theme", appearance)
        size = QSpinBox()
        size.setObjectName("readerTextSize")
        size.setRange(TEXT_SIZES.start, TEXT_SIZES.stop - 1)
        size.setSuffix(" pt")
        size.setValue(self.session.text_size)
        appearance_form.addRow("Reader text", size)
        layout.addLayout(appearance_form)

        layout.addSpacing(10)
        layout.addWidget(item_heading("Local database"))
        path_label = QLabel(str(self.session.database_path))
        path_label.setObjectName("databaseLocation")
        path_label.setTextFormat(Qt.TextFormat.PlainText)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        def select_database(create):
            if self._switch_database(create):
                path_label.setText(str(self.session.database_path))

        files = QHBoxLayout()
        files.addWidget(button("Open database…", "openDatabase", lambda: select_database(False)))
        files.addWidget(button("Create database…", "createDatabase", lambda: select_database(True)))
        layout.addLayout(files)

        backup = QHBoxLayout()
        backup.addWidget(button("Back up…", "backupDatabase", self._create_backup))
        backup.addWidget(button("Restore…", "restoreDatabase", self._restore_backup))
        layout.addLayout(backup)
        layout.addWidget(button("Import translation…", "importTranslation", self._import_translation))
        layout.addWidget(button("Import original-language resource…", "importOriginalLanguage", self._import_original_language))

        layout.addSpacing(10)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        footer = QHBoxLayout()
        footer.addWidget(button("Licenses…", "openLicenses", lambda: self._show_licenses(dialog), "quiet"))
        footer.addStretch(1)
        footer.addWidget(controls)
        layout.addLayout(footer)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.session.set_appearance(appearance.currentText(), size.value())
                self._refresh_appearance()
            except DATA_ERRORS as error:
                self.show_error("Could not save appearance settings", error)

    def _switch_database(self, create):
        if not self.workspace.can_leave():
            return False
        picker = QFileDialog.getSaveFileName if create else QFileDialog.getOpenFileName
        title = "Create local Bible Brain database" if create else "Open local Bible Brain database"
        initial = self.session.database_path.parent if create else self.session.database_path
        chosen, _ = picker(self._dialog_parent(), title, str(initial), "SQLite database (*.sqlite3 *.db);;All files (*)")
        if not chosen:
            return False
        path = Path(chosen)
        if create and not path.suffix:
            path = path.with_suffix(".sqlite3")
        try:
            if create and path.exists():
                raise ValueError("Choose a new database filename. To load an existing database, use Open database.")
            self.session.switch_database(path)
            self.reload_database()
            self.notify("Local database opened")
            return True
        except DATA_ERRORS as error:
            self.show_error("Could not open the selected database", error)
            return False

    def _import_translation(self):
        chosen, _ = QFileDialog.getOpenFileName(
            self._dialog_parent(), "Import licensed translation", "", "Bible Brain dataset (*.json *.json.gz);;All files (*)"
        )
        if chosen:
            try:
                count = self.session.import_dataset(Path(chosen))
                self._reload_editions()
                self.notify(f"Imported {count:,} verse addresses" if count else "Translation already installed")
            except DATA_ERRORS as error:
                self.show_error("Could not import the translation", error)

    def _import_original_language(self):
        chosen, _ = QFileDialog.getOpenFileName(
            self._dialog_parent(), "Import licensed original-language resource", "",
            "Bible Brain original-language dataset (*.bb-lang *.json *.json.gz);;All files (*)"
        )
        if chosen:
            try:
                count = self.session.import_original_language(Path(chosen))
                self.notify(f"Imported {count:,} original-language tokens" if count else "Resource already installed")
            except DATA_ERRORS as error:
                self.show_error("Could not import the original-language resource", error)

    def _create_backup(self):
        default = self.session.database_path.parent / "Bible Brain backup.sqlite3"
        chosen, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(), "Back up saved research and Scripture", str(default), "SQLite database (*.sqlite3)"
        )
        if chosen:
            try:
                path = Path(chosen)
                self.session.backup(path if path.suffix else path.with_suffix(".sqlite3"))
                QMessageBox.information(self._dialog_parent(), "Backup complete", "The database backup was saved.")
            except DATA_ERRORS as error:
                self.show_error("Could not create the backup", error)

    def _restore_backup(self):
        if not self.workspace.can_leave():
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self._dialog_parent(), "Restore a Bible Brain backup", str(self.session.database_path.parent),
            "SQLite database (*.sqlite3 *.db);;All files (*)",
        )
        if not chosen:
            return
        response = QMessageBox.question(
            self._dialog_parent(), "Restore backup", "Replace the active database with this backup? "
            "Bible Brain will save a recovery copy of the active database first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response == QMessageBox.StandardButton.Yes:
            try:
                previous = self.session.restore(Path(chosen))
                self.reload_database()
                QMessageBox.information(
                    self._dialog_parent(), "Database restored", f"The previous database was saved at:\n{previous}"
                )
            except DATA_ERRORS as error:
                self.show_error("Could not restore the database", error)

    def notify(self, message):
        self.statusBar().showMessage(message, 4200)

    def show_error(self, message, error):
        LOGGER.warning("%s (%s)", message, type(error).__name__)
        QMessageBox.warning(self._dialog_parent(), message, str(error))

    def _dialog_parent(self):
        return QApplication.activeModalWidget() or self

    @staticmethod
    def _show_licenses(parent):
        dialog = QDialog(parent)
        dialog.setWindowTitle("Third-party licenses")
        dialog.resize(660, 480)
        layout = QVBoxLayout(dialog)
        notices = QTextBrowser()
        notices.setOpenExternalLinks(True)
        base = Path(__file__).resolve().parent.parent
        for directory in ("licenses", "docs"):
            file = base / directory / "THIRD_PARTY.md"
            if file.is_file():
                notices.setMarkdown(file.read_text(encoding="utf-8"))
                break
        else:
            notices.setPlainText(
                "Qt and PySide6 are used under the GNU Lesser General Public License v3. "
                "The bundled World English Bible Protestant Edition is public-domain Scripture."
            )
        layout.addWidget(notices)
        finish = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        finish.rejected.connect(dialog.reject)
        layout.addWidget(finish)
        dialog.exec()

    def closeEvent(self, event):
        if self.workspace.can_leave():
            event.accept()
        else:
            event.ignore()


def _stylesheet(c, serif, sans):
    return f"""
        QWidget {{
            color: {c["ink"]};
            font-family: "{sans}";
            font-size: 10pt;
        }}
        QWidget#appPage, QWidget#scripturePane {{ background: {c["paper"]}; }}
        QFrame#appHeader, QFrame#chapterToolbar, QFrame#selectionBar, QStatusBar {{
            background: {c["chrome"]};
        }}
        QFrame#appHeader, QFrame#chapterToolbar {{ border-bottom: 1px solid {c["line"]}; }}
        QFrame#selectionBar {{ border-top: 1px solid {c["line"]}; }}
        QSplitter::handle {{ background: {c["line"]}; }}
        QWidget#researchWorkspace, QDialog, QMenu, QScrollArea#noteEditorScroll, QWidget#noteEditor {{
            background: {c["chrome"]};
        }}
        QLabel#wordmark {{
            font-family: "{serif}";
            font-size: 22pt;
            color: {c["ink"]};
        }}
        QLabel[role="panelTitle"] {{ font-family: "{serif}"; font-size: 21pt; }}
        QLabel[role="section"] {{ font-weight: 600; }}
        QLabel[role="selection"] {{ font-weight: 600; color: {c["accent"]}; }}
        QLabel[role="muted"], QStatusBar {{ color: {c["soft"]}; }}
        QPushButton, QComboBox, QLineEdit, QSpinBox, QPlainTextEdit, QListWidget, QTreeWidget {{
            background: {c["surface"]};
            border: 1px solid {c["line"]};
            border-radius: 5px;
        }}
        QPushButton {{ padding: 6px 11px; min-height: 18px; }}
        QPushButton[variant="quiet"] {{ background: transparent; border-color: transparent; }}
        QPushButton:hover, QPushButton:checked, QPushButton[variant="quiet"]:hover {{
            background: {c["selected"]};
            border-color: {c["line"]};
        }}
        QPushButton[variant="primary"] {{
            color: {c["accent_text"]};
            background: {c["accent"]};
            border-color: {c["accent"]};
            font-weight: 600;
        }}
        QPushButton[variant="primary"]:hover {{ background: {c["hover"]}; }}
        QPushButton:focus, QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{
            border-color: {c["accent"]};
        }}
        QPushButton:disabled, QComboBox:disabled {{ color: {c["disabled"]}; }}
        QPushButton#previousChapter, QPushButton#nextChapter, QPushButton#closeResearch {{
            font-size: 15pt;
            padding: 1px 7px 4px;
            min-width: 19px;
        }}
        QComboBox {{ padding: 6px 25px 6px 8px; min-height: 18px; }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border: 0;
        }}
        QComboBox::down-arrow {{ image: none; }}
        QLineEdit, QSpinBox {{ padding: 6px 7px; }}
        QPlainTextEdit {{ padding: 5px; selection-background-color: {c["accent"]}; }}
        QTextBrowser#chapterReader {{
            background: {c["paper"]};
            border: 0;
            selection-background-color: {c["accent"]};
            selection-color: {c["accent_text"]};
        }}
        QTreeWidget, QListWidget {{ padding: 4px; outline: 0; }}
        QTreeWidget::item, QListWidget::item {{ min-height: 27px; padding: 1px 4px; }}
        QTreeWidget::item:selected, QListWidget::item:selected {{
            background: {c["selected"]};
            color: {c["ink"]};
        }}
        QMenu::item {{ padding: 6px 14px; }}
        QMenu::item:selected {{ background: {c["selected"]}; }}
        QMenu::item:disabled {{ color: {c["disabled"]}; }}
    """
