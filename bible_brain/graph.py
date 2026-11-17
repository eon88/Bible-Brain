"""User-controlled Cross-reference, Trace and Study panels."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget, QInputDialog, QMessageBox)
from .database import ScriptureAnchor
from .workspace import DATA_ERRORS, button, item_heading

CONNECTION_TYPES = [("repeated_expression", "Repeated word or expression"), ("direct_quotation", "Direct quotation"), ("shared_symbol", "Shared symbol"), ("thematic_parallel", "Thematic parallel"), ("structural_parallel", "Structural parallel"), ("possible_allusion", "Possible allusion")]

class GraphWorkspace(QWidget):
    navigateRequested = Signal(object)
    traceChanged = Signal(object)
    def __init__(self, session, notify, show_error):
        super().__init__(); self.session=session; self.notify=notify; self.show_error=show_error; self.selection=[]; self.active_trace=None
        layout=QVBoxLayout(self); head=QHBoxLayout(); head.addWidget(QLabel("Explore"),1); self.closeButton=QPushButton("×"); self.closeButton.clicked.connect(self.hide); head.addWidget(self.closeButton); layout.addLayout(head)
        self.tabs=QTabWidget(); self.tabs.addTab(self._cross_panel(),"Cross-references"); self.tabs.addTab(self._trace_panel(),"Trace"); self.tabs.addTab(self._study_panel(),"Studies"); layout.addWidget(self.tabs)
    @property
    def database(self): return self.session.database
    def set_selection(self, anchors): self.selection=list(anchors); self.refresh()
    def refresh(self): self._refresh_connections(); self._refresh_traces(); self._refresh_studies()
    def _cross_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Connections"),1); top.addWidget(button("Add connection", "addConnection", self._add_connection,"primary")); l.addLayout(top)
        self.connections=QListWidget(); self.connections.setObjectName("graphConnections"); self.connections.itemDoubleClicked.connect(self._open_connection); l.addWidget(self.connections,1)
        controls=QHBoxLayout(); self.review=QComboBox(); self.review.addItems(["Keep","Investigate","Park","Reject"]); controls.addWidget(self.review); controls.addWidget(button("Apply review", "reviewConnection", self._review_connection)); controls.addWidget(button("Edit", "editConnection", self._edit_connection)); l.addLayout(controls); return w
    def _refresh_connections(self):
        if not hasattr(self,'connections'): return
        self.connections.clear()
        if not self.selection: return
        try: anchor_id=self.database.scripture_anchor(self.selection[0])
        except DATA_ERRORS: return
        for row in self.database.knowledge_connections(anchor_id):
            other=row['to_verse'] if row['from_id']==anchor_id else row['from_verse']
            text=f"{other or row['to_title'] or row['from_title']} · {row['type']} · {row['status']}"
            if row['evidence']: text += f" — {row['evidence']}"
            item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,row['id']); self.connections.addItem(item)
    def _parse_reference(self, value, translation=None):
        bits=value.strip().replace(':',' ').split()
        if len(bits)!=3: raise ValueError("Use a reference like REV 22:2.")
        return ScriptureAnchor(bits[0].upper(),int(bits[1]),int(bits[2]),translation)
    def _add_connection(self):
        if not self.selection: return
        dialog=QDialog(self); dialog.setWindowTitle("Add Scripture connection"); form=QFormLayout(dialog)
        target=QLineEdit(); target.setPlaceholderText("REV 22:2"); form.addRow("Other passage",target)
        kind=QComboBox(); [kind.addItem(label,code) for code,label in CONNECTION_TYPES]; form.addRow("Classify as",kind)
        evidence=QPlainTextEdit(); evidence.setPlaceholderText("Explain the textual evidence or hypothesis…"); form.addRow("Evidence",evidence)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); form.addRow(controls)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            source=self.database.scripture_anchor(self.selection[0]); dest=self.database.scripture_anchor(self._parse_reference(target.text(),self.selection[0].translation)); self.database.create_relationship(source,dest,kind.currentData(),evidence=evidence.toPlainText()); self.refresh(); self.notify("Connection saved")
        except DATA_ERRORS as error: self.show_error("Could not add the connection",error)
    def _selected_connection(self):
        item=self.connections.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None
    def _review_connection(self):
        rid=self._selected_connection()
        if not rid: return
        status={"Keep":"approved","Investigate":"investigate","Park":"parked","Reject":"rejected"}[self.review.currentText()]
        try: self.database.review_knowledge(rid,status,"User","Reviewed in Explore panel",relationship=True); self.refresh()
        except DATA_ERRORS as error: self.show_error("Could not review the connection",error)
    def _edit_connection(self):
        rid=self._selected_connection()
        if not rid: return
        row=self.database._connection.execute("SELECT * FROM knowledge_relationships WHERE id=?",(rid,)).fetchone()
        evidence,ok=QInputDialog.getMultiLineText(self,"Edit connection","Supporting evidence",row['evidence'])
        if ok:
            try: self.database.update_relationship(rid,evidence=evidence); self.refresh()
            except DATA_ERRORS as error: self.show_error("Could not edit the connection",error)
    def _open_connection(self,item):
        rid=item.data(Qt.ItemDataRole.UserRole); row=self.database._connection.execute("SELECT from_id,to_id FROM knowledge_relationships WHERE id=?",(rid,)).fetchone()
        for object_id in row:
            a=self.database._connection.execute("SELECT verse_id FROM scripture_anchors WHERE object_id=?",(object_id,)).fetchone()
            if a:
                b,c,v=a[0].split(':'); self.navigateRequested.emit(ScriptureAnchor(b,int(c),int(v),self.selection[0].translation if self.selection else None)); break
    def _trace_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Named traces"),1); top.addWidget(button("Create trace","createTrace",self._create_trace,"primary")); l.addLayout(top)
        self.traces=QListWidget(); self.traces.setObjectName("traceList"); self.traces.currentItemChanged.connect(lambda *_: self._refresh_trace_members()); l.addWidget(self.traces,1)
        controls=QHBoxLayout(); controls.addWidget(button("Add to trace","addToTrace",self._add_to_trace)); self.active=QPushButton("Activate"); self.active.setCheckable(True); self.active.toggled.connect(self._toggle_trace); controls.addWidget(self.active); l.addLayout(controls)
        self.trace_members_view=QListWidget(); self.trace_members_view.setObjectName("traceMembers"); self.trace_members_view.itemDoubleClicked.connect(self._open_trace_member); l.addWidget(self.trace_members_view,1); return w
    def _refresh_traces(self):
        if not hasattr(self,'traces'): return
        selected=self.traces.currentItem().data(Qt.ItemDataRole.UserRole) if self.traces.currentItem() else self.active_trace; self.traces.clear()
        for row in self.database.traces():
            i=QListWidgetItem(row['title']); i.setData(Qt.ItemDataRole.UserRole,row['id']); i.setToolTip(row['description']); self.traces.addItem(i)
            if row['id']==selected: self.traces.setCurrentItem(i)
        self._refresh_trace_members()
    def _selected_trace(self): return self.traces.currentItem().data(Qt.ItemDataRole.UserRole) if self.traces.currentItem() else None
    def _refresh_trace_members(self):
        if not hasattr(self,'trace_members_view'): return
        self.trace_members_view.clear(); tid=self._selected_trace()
        if not tid: return
        for row in self.database.trace_members(tid):
            i=QListWidgetItem(row['verse_id'] or row['title']); i.setData(Qt.ItemDataRole.UserRole,row['id']); self.trace_members_view.addItem(i)
    def _create_trace(self):
        name,ok=QInputDialog.getText(self,"Create trace","Name")
        if ok:
            try: self.database.create_trace(name); self._refresh_traces()
            except DATA_ERRORS as error: self.show_error("Could not create the trace",error)
    def _add_to_trace(self):
        tid=self._selected_trace()
        if not tid or not self.selection: return
        try:
            for anchor in self.selection: self.database.add_trace_member(tid,self.database.scripture_anchor(anchor),self.database.trace_members(tid).__len__())
            self._refresh_trace_members(); self.notify("Added to trace")
        except DATA_ERRORS as error: self.show_error("Could not add to trace",error)
    def _toggle_trace(self,checked):
        self.active_trace=self._selected_trace() if checked else None; self.active.setText("Deactivate" if checked else "Activate"); self.traceChanged.emit(self.active_trace)
    def _open_trace_member(self,item):
        ref=item.text().split(':')
        if len(ref)==3: self.navigateRequested.emit(ScriptureAnchor(ref[0],int(ref[1]),int(ref[2]),self.selection[0].translation if self.selection else None))
    def _study_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Studies"),1); top.addWidget(button("New study","newStudy",self._create_study,"primary")); l.addLayout(top)
        self.study_list=QListWidget(); self.study_list.setObjectName("studyList"); self.study_list.itemDoubleClicked.connect(self._open_study); l.addWidget(self.study_list,1); return w
    def _refresh_studies(self):
        if not hasattr(self,'study_list'): return
        self.study_list.clear()
        for row in self.database.studies():
            i=QListWidgetItem(row['title']); i.setData(Qt.ItemDataRole.UserRole,row['id']); i.setToolTip(row['summary']); self.study_list.addItem(i)
    def _create_study(self):
        dialog=QDialog(self); dialog.setWindowTitle("New study"); form=QFormLayout(dialog); title=QLineEdit(); summary=QPlainTextEdit(); observations=QPlainTextEdit(); questions=QPlainTextEdit(); conclusions=QPlainTextEdit()
        for label,widget in (("Title",title),("Summary",summary),("Observations",observations),("Questions",questions),("Conclusions",conclusions)): form.addRow(label,widget)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); form.addRow(controls)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try: self.database.create_study(title.text(),summary.toPlainText(),observations.toPlainText(),questions.toPlainText(),conclusions=conclusions.toPlainText(),anchors=self.selection); self._refresh_studies(); self.notify("Study saved")
        except DATA_ERRORS as error: self.show_error("Could not create the study",error)
    def _open_study(self,item):
        row=self.database.study(item.data(Qt.ItemDataRole.UserRole)); QMessageBox.information(self,"Study",f"{row['title']}\n\n{row['summary']}\n\nObservations\n{row['observations']}\n\nQuestions\n{row['questions']}\n\nConclusions\n{row['conclusions']}")
