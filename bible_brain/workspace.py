"""Folder navigation and the note editor in the collapsible research panel."""

import sqlite3

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import ScriptureAnchor


DATA_ERRORS = (ValueError, sqlite3.Error, OSError)
ITEM_ID = Qt.ItemDataRole.UserRole


def button(label, name, action, variant="secondary"):
    control = QPushButton(label)
    control.setObjectName(name)
    control.setProperty("variant", variant)
    control.clicked.connect(action)
    return control


def item_heading(text):
    heading = QLabel(text)
    heading.setProperty("role", "section")
    return heading


class SelectBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setPen(QPen(self.palette().color(group, QPalette.ColorRole.Text), 1.15))
        x = self.width() - 13
        y = self.height() / 2
        painter.drawPolyline(QPolygonF([QPointF(x - 4, y - 2), QPointF(x, y + 2), QPointF(x + 4, y - 2)]))


class ResearchWorkspace(QWidget):
    closeRequested = Signal()
    navigateRequested = Signal(object)

    def __init__(self, session, format_anchor, notify, show_error):
        super().__init__()
        self.setObjectName("researchWorkspace")
        self.setMinimumWidth(288)
        self.setMinimumHeight(240)
        self.session = session
        self.format_anchor = format_anchor
        self.notify = notify
        self.show_error = show_error
        self.active_note = None
        self.selection = []
        self.anchors = []
        self.label_ids = set()
        self.baseline = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(19, 16, 19, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Research")
        title.setProperty("role", "panelTitle")
        header.addWidget(title, 1)
        close_button = button("×", "closeResearch", self.closeRequested.emit, "quiet")
        close_button.setAccessibleName("Hide research")
        close_button.setToolTip("Hide research")
        header.addWidget(close_button)
        layout.addLayout(header)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._make_library())
        editor_scroll = QScrollArea()
        editor_scroll.setObjectName("noteEditorScroll")
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor_scroll.setWidget(self._make_editor())
        self.stack.addWidget(editor_scroll)
        layout.addWidget(self.stack, 1)

    @property
    def database(self):
        return self.session.database

    @property
    def folder_id(self):
        current = self.folders.currentItem()
        return current.data(0, ITEM_ID) if current else None

    def _make_library(self):
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        top = QHBoxLayout()
        top.addWidget(item_heading("Folders"), 1)
        self.folder_actions = QPushButton("Manage")
        self.folder_actions.setObjectName("folderActions")
        self.folder_actions.setProperty("variant", "quiet")
        folder_menu = QMenu(self.folder_actions)
        self.create_action = folder_menu.addAction("New folder…", self._create_folder)
        self.rename_action = folder_menu.addAction("Rename folder…", self._rename_folder)
        self.move_action = folder_menu.addAction("Move folder…", self._move_folder)
        self.delete_action = folder_menu.addAction("Delete folder…", self._delete_folder)
        folder_menu.aboutToShow.connect(self._set_available_actions)
        self.folder_actions.setMenu(folder_menu)
        top.addWidget(self.folder_actions)
        layout.addLayout(top)

        self.folders = QTreeWidget()
        self.folders.setObjectName("researchFolders")
        self.folders.setAccessibleName("Research folders")
        self.folders.setHeaderHidden(True)
        self.folders.setIndentation(16)
        self.folders.setMinimumHeight(75)
        self.folders.itemSelectionChanged.connect(self.refresh_notes)
        layout.addWidget(self.folders, 4)

        notes_header = QHBoxLayout()
        notes_header.addWidget(item_heading("Notes"), 1)
        notes_header.addWidget(button("New note", "newWorkspaceNote", self.new_note, "primary"))
        layout.addLayout(notes_header)

        self.notes = QListWidget()
        self.notes.setObjectName("researchNotes")
        self.notes.setAccessibleName("Notes in selected folder")
        self.notes.setMinimumHeight(75)
        self.notes.itemActivated.connect(self._open_item)
        self.notes.itemClicked.connect(self._open_item)
        layout.addWidget(self.notes, 6)
        self.empty_notes = QLabel("This folder is empty.")
        self.empty_notes.setProperty("role", "muted")
        layout.addWidget(self.empty_notes)
        return library

    def _make_editor(self):
        editor = QWidget()
        editor.setObjectName("noteEditor")
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        top = QHBoxLayout()
        top.addWidget(button("‹ Notes", "backToNotes", self.return_to_library, "quiet"))
        top.addStretch(1)
        self.revisions = button("History", "noteHistory", self._show_revisions, "quiet")
        top.addWidget(self.revisions)
        layout.addLayout(top)

        self.title = QLineEdit()
        self.title.setObjectName("noteTitle")
        self.title.setAccessibleName("Note title")
        self.title.setPlaceholderText("Note title")
        layout.addWidget(self.title)

        self.body = QPlainTextEdit()
        self.body.setObjectName("noteBody")
        self.body.setAccessibleName("Note body")
        self.body.setPlaceholderText("Write your observations…")
        self.body.setMinimumHeight(85)
        layout.addWidget(self.body, 1)

        filed = QHBoxLayout()
        folder_label = item_heading("Folder")
        filed.addWidget(folder_label)
        self.destination = SelectBox()
        self.destination.setObjectName("noteFolder")
        self.destination.setAccessibleName("Note folder")
        self.destination.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        folder_label.setBuddy(self.destination)
        filed.addWidget(self.destination, 1)
        layout.addLayout(filed)

        ref_header = QHBoxLayout()
        ref_header.addWidget(item_heading("Scripture"), 1)
        self.attach = button("Attach selection", "attachSelection", self._attach_selection, "quiet")
        self.attach.setEnabled(False)
        ref_header.addWidget(self.attach)

        self.links = QListWidget()
        self.links.setObjectName("noteReferences")
        self.links.setAccessibleName("Scripture links")
        self.links.setMaximumHeight(84)
        self.links.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.links.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.links.itemActivated.connect(self._navigate_to_link)
        self.remove_link = button("×", "removeReference", self._remove_reference, "quiet")
        self.remove_link.setAccessibleName("Remove selected Scripture link")
        self.remove_link.setToolTip("Remove selected Scripture link")
        self.remove_link.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.links.currentItemChanged.connect(lambda current, _: self.remove_link.setEnabled(current is not None))
        ref_header.addWidget(self.remove_link)
        layout.addLayout(ref_header)
        layout.addWidget(self.links)

        bottom = QHBoxLayout()
        self.labels_button = button("Labels", "noteLabels", self._edit_labels)
        bottom.addWidget(self.labels_button)
        bottom.addStretch(1)
        bottom.addWidget(button("Save note", "saveNote", self.save, "primary"))
        layout.addLayout(bottom)
        return editor

    def refresh(self, selected_id=None):
        self.stack.setCurrentIndex(0)
        selected_id = self.folder_id if selected_id is None else selected_id
        rows = self.database.folders()
        tree_state = self._expanded_ids()
        self.folders.blockSignals(True)
        self.folders.clear()
        root = QTreeWidgetItem(["Unfiled"])
        root.setData(0, ITEM_ID, None)
        self.folders.addTopLevelItem(root)
        items = {folder["id"]: QTreeWidgetItem([folder["name"]]) for folder in rows}
        for folder in rows:
            item = items[folder["id"]]
            item.setData(0, ITEM_ID, folder["id"])
            parent = items.get(folder["parent_id"])
            if parent is None:
                self.folders.addTopLevelItem(item)
            else:
                parent.addChild(item)
        for item_id in tree_state:
            if item_id in items:
                items[item_id].setExpanded(True)
        current = items.get(selected_id, root)
        ancestor = current.parent()
        while ancestor:
            ancestor.setExpanded(True)
            ancestor = ancestor.parent()
        self.folders.setCurrentItem(current)
        self.folders.blockSignals(False)
        self.refresh_notes()

    def _expanded_ids(self):
        expanded = set()
        for index in range(self.folders.topLevelItemCount()):
            pending = [self.folders.topLevelItem(index)]
            while pending:
                item = pending.pop()
                if item.isExpanded():
                    expanded.add(item.data(0, ITEM_ID))
                pending.extend(item.child(i) for i in range(item.childCount()))
        return expanded

    def refresh_notes(self):
        rows = self.database.notes(self.folder_id)
        self.notes.clear()
        for row in rows:
            item = QListWidgetItem(row["title"])
            item.setData(ITEM_ID, row["id"])
            self.notes.addItem(item)
        self.empty_notes.setVisible(not rows)

    def set_selection(self, anchors):
        self.selection = list(anchors)
        self.attach.setEnabled(bool(self.selection))

    def _set_available_actions(self):
        self.create_action.setText("New subfolder…" if self.folder_id is not None else "New folder…")
        for action in (self.rename_action, self.move_action, self.delete_action):
            action.setEnabled(self.folder_id is not None)

    def _create_folder(self):
        title = self.create_action.text().removesuffix("…")
        name, accepted = QInputDialog.getText(self, title, "Folder name")
        if accepted:
            try:
                folder_id = self.database.create_folder(name, self.folder_id)
                self.refresh(folder_id)
            except DATA_ERRORS as error:
                self.show_error("Could not create the folder", error)

    def _rename_folder(self):
        folder_id = self.folder_id
        if folder_id is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename folder", "Folder name", text=self.folders.currentItem().text(0)
        )
        if accepted:
            try:
                self.database.rename_folder(folder_id, name)
                self.refresh(folder_id)
            except DATA_ERRORS as error:
                self.show_error("Could not rename the folder", error)

    def _move_folder(self):
        folder_id = self.folder_id
        if folder_id is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Move folder")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose a new parent folder."))
        combo = SelectBox()
        parent_item = self.folders.currentItem().parent()
        parent_id = parent_item.data(0, ITEM_ID) if parent_item else None
        self._populate_folders(combo, parent_id, exclude=folder_id)
        layout.addWidget(combo)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        layout.addWidget(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.move_folder(folder_id, combo.currentData())
                self.refresh(folder_id)
            except DATA_ERRORS as error:
                self.show_error("Could not move the folder", error)

    def _delete_folder(self):
        folder_id = self.folder_id
        item = self.folders.currentItem()
        if folder_id is None:
            return
        response = QMessageBox.question(
            self, "Delete folder", f'Delete “{item.text(0)}”?\n\n'
            "Its notes and subfolders will move to the parent folder or workspace.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if response == QMessageBox.StandardButton.Yes:
            try:
                parent_id = item.parent().data(0, ITEM_ID) if item.parent() else None
                self.database.delete_folder(folder_id)
                self.refresh(parent_id)
            except DATA_ERRORS as error:
                self.show_error("Could not delete the folder", error)

    def _populate_folders(self, combo, selected, exclude=None):
        folders_by_parent = {}
        for folder in self.database.folders():
            folders_by_parent.setdefault(folder["parent_id"], []).append(folder)
        combo.clear()
        combo.addItem("Unfiled" if exclude is None else "Top level", None)
        pending = [(folder, 0) for folder in reversed(folders_by_parent.get(None, []))]
        while pending:
            folder, depth = pending.pop()
            if folder["id"] == exclude:
                continue
            combo.addItem("    " * depth + folder["name"], folder["id"])
            pending.extend(
                (child, depth + 1) for child in reversed(folders_by_parent.get(folder["id"], []))
            )
        combo.setCurrentIndex(max(0, combo.findData(selected)))

    def new_note(self, _checked=False, anchors=()):
        if self.can_leave():
            self._fill_editor(None, "", "", self.folder_id, anchors, set())
            self.title.setFocus()

    def _open_item(self, item):
        if not self.can_leave():
            return
        try:
            self._open_note(item.data(ITEM_ID))
        except DATA_ERRORS as error:
            self.show_error("Could not open the note", error)

    def _open_note(self, note_id):
        note = self.database.note(note_id)
        anchors = [
            ScriptureAnchor(
                row["book"], row["chapter"], row["verse"], row["translation"], row["start"], row["end"]
            ) for row in self.database.note_anchors(note_id)
        ]
        labels = {row["id"] for row in self.database.note_labels(note_id)}
        self._fill_editor(note_id, note["title"], note["body"], note["folder_id"], anchors, labels)

    def _fill_editor(self, note_id, title, body, folder_id, anchors, label_ids):
        self.active_note = note_id
        self.title.setText(title)
        self.body.setPlainText(body)
        self._populate_folders(self.destination, folder_id)
        self.anchors = list(anchors)
        self.label_ids = set(label_ids)
        self._display_links()
        self._display_labels()
        self.revisions.setEnabled(note_id is not None)
        self.baseline = self._snapshot()
        self.stack.setCurrentIndex(1)

    def _snapshot(self):
        return (
            self.title.text(),
            self.body.toPlainText(),
            self.destination.currentData(),
            tuple(self.anchors),
            frozenset(self.label_ids),
        )

    def can_leave(self):
        if self.stack.currentIndex() != 1 or self.baseline == self._snapshot():
            return True
        response = QMessageBox.question(
            self, "Unsaved note", "Save changes to this note?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save,
        )
        if response == QMessageBox.StandardButton.Save:
            return self.save()
        return response == QMessageBox.StandardButton.Discard

    def return_to_library(self):
        if self.can_leave():
            self.refresh(self.destination.currentData())

    def _attach_selection(self):
        for anchor in self.selection:
            if anchor not in self.anchors:
                self.anchors.append(anchor)
        self._display_links()

    def _remove_reference(self):
        index = self.links.currentRow()
        if index >= 0:
            self.anchors.pop(index)
            self._display_links()

    def _navigate_to_link(self, item):
        self.navigateRequested.emit(self.anchors[self.links.row(item)])

    def _display_links(self):
        self.links.clear()
        for anchor in self.anchors:
            item = QListWidgetItem(self.format_anchor(anchor, with_quote=True))
            item.setToolTip(f"{item.text()}\nOpen this reference with a double click or Enter.")
            self.links.addItem(item)
        self.links.setMaximumHeight(48 if len(self.anchors) == 1 else 84)
        self.links.setVisible(bool(self.anchors))
        self.remove_link.setVisible(bool(self.anchors))
        self.remove_link.setEnabled(False)

    def _display_labels(self):
        suffix = f" ({len(self.label_ids)})" if self.label_ids else ""
        self.labels_button.setText(f"Labels{suffix}")

    def _edit_labels(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Note labels")
        dialog.resize(300, 310)
        layout = QVBoxLayout(dialog)
        available = QListWidget()
        available.setObjectName("chooseNoteLabels")
        layout.addWidget(available)

        def add_item(label_id, name, checked):
            item = QListWidgetItem(name)
            item.setData(ITEM_ID, label_id)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            available.addItem(item)

        for label in self.database.labels():
            add_item(label["id"], label["name"], label["id"] in self.label_ids)

        def create():
            name, accepted = QInputDialog.getText(dialog, "New label", "Label name")
            if accepted:
                try:
                    label_id = self.database.create_label(name)
                    add_item(label_id, name.strip(), True)
                except DATA_ERRORS as error:
                    self.show_error("Could not create the label", error)

        layout.addWidget(button("New label…", "createNoteLabel", create))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(dialog.accept)
        controls.rejected.connect(dialog.reject)
        layout.addWidget(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.label_ids = {
                available.item(i).data(ITEM_ID) for i in range(available.count())
                if available.item(i).checkState() == Qt.CheckState.Checked
            }
            self._display_labels()

    def save(self):
        title, body, folder_id, anchors, label_ids = self._snapshot()
        try:
            if self.active_note is None:
                self.active_note = self.database.create_note(title, body, folder_id, anchors, label_ids=label_ids)
            else:
                self.database.update_note(
                    self.active_note, title, body, folder_id, anchors, label_ids=label_ids
                )
            self._open_note(self.active_note)
            self.notify("Note saved")
            return True
        except DATA_ERRORS as error:
            self.show_error("Could not save the note", error)
            return False

    def _show_revisions(self):
        if not self.can_leave() or self.active_note is None:
            return
        try:
            if self.baseline != self._snapshot():
                self._open_note(self.active_note)
            versions = self.database.note_revisions(self.active_note)
            if not versions:
                self.notify("No earlier versions are saved")
                return
            self._revision_dialog(versions)
        except DATA_ERRORS as error:
            self.show_error("Could not open note history", error)

    def _revision_dialog(self, versions):
        dialog = QDialog(self)
        dialog.setWindowTitle("Note history")
        dialog.resize(500, 420)
        layout = QVBoxLayout(dialog)
        choices = SelectBox()
        for version in versions:
            choices.addItem(version["created_at"], version["id"])
        layout.addWidget(choices)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        layout.addWidget(preview)

        def show_version(index):
            version = versions[index]
            preview.setPlainText(f"{version['title']}\n\n{version['body']}")

        choices.currentIndexChanged.connect(show_version)
        show_version(0)
        actions = QHBoxLayout()
        actions.addWidget(button("Close", "closeNoteHistory", dialog.reject))
        actions.addStretch()
        actions.addWidget(button("Restore version", "restoreNoteVersion", dialog.accept, "primary"))
        layout.addLayout(actions)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.database.restore_note_revision(self.active_note, choices.currentData())
            self._open_note(self.active_note)
            self.notify("Note version restored")
