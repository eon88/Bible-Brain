"""User-controlled Cross-reference, Trace and Study panels."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget, QInputDialog, QMessageBox, QFileDialog, QToolButton)
from .database import ScriptureAnchor
from .workspace import DATA_ERRORS, button, item_heading

CONNECTION_TYPES = [("repeated_expression", "Repeated word or expression"), ("direct_quotation", "Direct quotation"), ("shared_symbol", "Shared symbol"), ("thematic_parallel", "Thematic parallel"), ("structural_parallel", "Structural parallel"), ("possible_allusion", "Possible allusion")]

class GraphWorkspace(QWidget):
    navigateRequested = Signal(object)
    traceChanged = Signal(object)
    contextActionRequested = Signal(str)
    def __init__(self, session, notify, show_error):
        super().__init__(); self.setObjectName("explorePanel"); self.session=session; self.notify=notify; self.show_error=show_error; self.selection=[]; self.active_trace=None; self.section_toggles={}
        layout=QVBoxLayout(self); layout.setContentsMargins(18,18,18,18); layout.setSpacing(12); head=QHBoxLayout(); title=QLabel("Study Companion"); title.setProperty("role","panelTitle"); head.addWidget(title); self.pin_label=QLabel("No pinned investigation"); self.pin_label.setObjectName("companionPin"); head.addWidget(self.pin_label,1); self.history_button=button("History", "companionHistory", self._show_history, "quiet"); head.addWidget(self.history_button); self.search=QLineEdit(); self.search.setPlaceholderText("Search your research…"); head.addWidget(self.search,1); head.addWidget(button("Search", "searchResearch", self._search)); self.closeButton=QPushButton("×"); self.closeButton.setToolTip("Close Study Companion"); self.closeButton.clicked.connect(self.hide); head.addWidget(self.closeButton); layout.addLayout(head)
        self.tabs=QTabWidget(); self.tabs.setObjectName("companionTabs"); self.tabs.addTab(self._cross_panel(),"Connections"); self.tabs.addTab(self._trace_panel(),"Traces"); self.tabs.addTab(self._study_panel(),"Studies"); self.tabs.currentChanged.connect(lambda index: self.session.update_ui_state(companion_tab=index)); layout.addWidget(self.tabs)
        state=self.session.ui_state; pin=state.get("companion_pin")
        if pin: self.pin_label.setText(f"Pinned · {pin.get('label','Investigation')}")
        self.tabs.setCurrentIndex(int(state.get("companion_tab",0)) if str(state.get("companion_tab",0)).isdigit() else 0)
        self._apply_section_state()
    @property
    def database(self): return self.session.database
    def set_selection(self, anchors): self.selection=list(anchors); self.refresh()

    def _section_pin(self):
        pin=self.session.ui_state.get("companion_pin") or {}
        return str(pin.get("id") or "none")

    def _section_expanded(self, tab, key):
        sections=self.session.ui_state.get("companion_sections",{})
        return bool(sections.get(self._section_pin(),{}).get(f"{tab}:{key}",True))

    def _set_section_expanded(self, tab, key, expanded):
        sections=self.session.ui_state.get("companion_sections",{})
        per_pin=dict(sections.get(self._section_pin(),{})); per_pin[f"{tab}:{key}"]=bool(expanded); sections=dict(sections); sections[self._section_pin()]=per_pin
        self.session.update_ui_state(companion_sections=sections)

    def _section(self, tab, key, title, content):
        wrapper=QWidget(); layout=QVBoxLayout(wrapper); layout.setContentsMargins(0,4,0,4); layout.setSpacing(3)
        toggle=QToolButton(); toggle.setObjectName(f"sectionToggle_{tab}_{key}"); toggle.setText(title); toggle.setCheckable(True); toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.toggled.connect(lambda checked: (content.setVisible(checked), toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow), self._set_section_expanded(tab,key,checked)))
        self.section_toggles[(tab,key)]=toggle; layout.addWidget(toggle); layout.addWidget(content); return wrapper

    def _empty_state(self, title, detail):
        panel=QWidget(); panel.setObjectName("companionEmptyState")
        layout=QVBoxLayout(panel); layout.setContentsMargins(24,28,24,28); layout.setSpacing(8)
        heading=QLabel(title); heading.setObjectName("emptyStateTitle"); heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body=QLabel(detail); body.setObjectName("emptyStateDetail"); body.setWordWrap(True); body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading); layout.addWidget(body); layout.addStretch(1)
        return panel

    def _apply_section_state(self):
        for (tab,key), toggle in self.section_toggles.items():
            expanded=self._section_expanded(tab,key); toggle.blockSignals(True); toggle.setChecked(expanded); toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow); toggle.blockSignals(False)
            parent=toggle.parentWidget();
            if parent and parent.layout() and parent.layout().count()>1: parent.layout().itemAt(1).widget().setVisible(expanded)

    def open_trace_picker(self, anchors):
        if not anchors:
            return
        dialog=QDialog(self); dialog.setWindowTitle("Choose a Trace"); dialog.resize(420, 420)
        layout=QVBoxLayout(dialog); layout.addWidget(QLabel("Choose a saved Trace for this exact selection. Nothing is activated until you press Activate."))
        traces=QListWidget()
        for row in self.database.traces():
            item=QListWidgetItem(row["title"]); item.setData(Qt.ItemDataRole.UserRole,row["id"]); item.setToolTip(row["description"]); traces.addItem(item)
        layout.addWidget(traces,1)
        controls=QHBoxLayout()
        choose=button("Choose", "chooseTrace", dialog.accept, "primary")
        create=button("Create new", "createTraceFromSelection", lambda: self._create_trace_from_picker(traces), "quiet")
        add=button("Add selected", "addSelectionToTrace", lambda: self._add_picker_selection(traces), "quiet")
        controls.addWidget(choose); controls.addWidget(create); controls.addWidget(add); controls.addWidget(button("Cancel", "cancelTracePicker", dialog.reject, "quiet")); layout.addLayout(controls)
        if dialog.exec()==QDialog.DialogCode.Accepted and traces.currentItem():
            self.traces.setCurrentRow(next((i for i in range(self.traces.count()) if self.traces.item(i).data(Qt.ItemDataRole.UserRole)==traces.currentItem().data(Qt.ItemDataRole.UserRole)), -1))
            self.notify("Trace selected; press Activate to begin Trace reading")

    def _create_trace_from_picker(self, traces):
        name,ok=QInputDialog.getText(self,"Create trace","Name")
        if not ok or not name.strip(): return
        try:
            trace_id=self.database.create_trace(name.strip()); self._refresh_traces()
            self.database.add_trace_member(trace_id,self.database.scripture_anchor(self.selection[0]),0)
            self._refresh_trace_members(); self.notify("Trace created and selection added")
        except DATA_ERRORS as error: self.show_error("Could not create the trace",error)

    def _add_picker_selection(self, traces):
        item=traces.currentItem()
        if not item: return
        try:
            trace_id=item.data(Qt.ItemDataRole.UserRole)
            self.database.add_trace_member(trace_id,self.database.scripture_anchor(self.selection[0]),len(self.database.trace_members(trace_id)))
            self._refresh_traces(); self.notify("Selection added to trace")
        except DATA_ERRORS as error: self.show_error("Could not add the selection to the trace",error)
    def pin_selection(self, anchors):
        if not anchors: return
        anchor=anchors[0]
        try:
            subject_id=self.database.scripture_anchor(anchor)
        except DATA_ERRORS:
            subject_id=f"{anchor.book}:{anchor.chapter}:{anchor.verse}:{anchor.start}:{anchor.end}"
        pin={"id":subject_id,"book":anchor.book,"chapter":anchor.chapter,"verse":anchor.verse,"start":anchor.start,"end":anchor.end,"translation":anchor.translation,"label":f"{anchor.book} {anchor.chapter}:{anchor.verse}"}
        state=self.session.ui_state; history=[item for item in state.get("companion_history",[]) if item.get("id",item.get("label")) != subject_id]
        history.insert(0,pin); self.session.update_ui_state(companion_pin=pin, companion_history=history[:50])
        self.pin_label.setText(f"Pinned · {pin['label']}"); self._apply_section_state()
    def _show_history(self):
        history=self.session.ui_state.get("companion_history",[])
        if not history:
            QMessageBox.information(self,"Recent investigations","No recent investigations yet."); return
        dialog=QDialog(self); dialog.setWindowTitle("Recent investigations"); layout=QVBoxLayout(dialog); items=QListWidget()
        for entry in history:
            item=QListWidgetItem(entry.get("label","Investigation")); item.setData(Qt.ItemDataRole.UserRole,entry); items.addItem(item)
        layout.addWidget(items); actions=QHBoxLayout(); actions.addWidget(button("Open", "openInvestigation", lambda: self._open_history(items,dialog), "primary")); actions.addWidget(button("Clear history", "clearInvestigationHistory", lambda: self._clear_history(dialog))); layout.addLayout(actions); dialog.resize(360,420); dialog.exec()
    def _open_history(self, items, dialog):
        item=items.currentItem()
        if not item: return
        entry=item.data(Qt.ItemDataRole.UserRole); self.session.update_ui_state(companion_pin=entry); self.pin_label.setText(f"Pinned · {entry.get('label','Investigation')}"); self._apply_section_state(); dialog.accept(); self.refresh()
    def _clear_history(self, dialog):
        if QMessageBox.question(self,"Clear history","Remove recent navigation history only? Saved research will remain.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        self.session.update_ui_state(companion_history=[]); dialog.accept()
    def refresh(self): self._refresh_connections(); self._refresh_traces(); self._refresh_studies()
    def _search(self):
        rows=self.database.search_research(self.search.text())
        if not rows:
            self.notify("No matching research found"); return
        QMessageBox.information(self,"Research search","\n".join(f"{r['title']} · {r['kind']} · {r['status']}" for r in rows))
    def _cross_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Connections"),1); top.addWidget(button("Original language", "companionOriginalLanguage", lambda: self.contextActionRequested.emit("original_language"),"quiet")); top.addWidget(button("Add connection", "addConnection", self._add_connection,"primary")); l.addLayout(top)
        self.connections=QListWidget(); self.connections.setObjectName("graphConnections"); self.connections.itemDoubleClicked.connect(self._open_connection); self.connections_section=self._section("connections","results","Connection results",self.connections); l.addWidget(self.connections_section,1)
        self.connections_empty=self._empty_state("Nothing connected yet", "Select a passage and add a relationship to begin building your Scripture graph."); l.addWidget(self.connections_empty,1)
        controls=QHBoxLayout(); self.review=QComboBox(); self.review.addItems(["Keep","Investigate","Park","Reject"]); controls.addWidget(self.review); controls.addWidget(button("Apply review", "reviewConnection", self._review_connection)); controls.addWidget(button("Edit", "editConnection", self._edit_connection)); l.addLayout(controls); return w
    def _refresh_connections(self):
        if not hasattr(self,'connections'): return
        self.connections.clear()
        if not self.selection:
            self.connections_section.setVisible(False); self.connections_empty.setVisible(True); return
        try: anchor_id=self.database.scripture_anchor(self.selection[0])
        except DATA_ERRORS:
            self.connections_section.setVisible(False); self.connections_empty.setVisible(True); return
        for row in self.database.knowledge_connections(anchor_id):
            other=row['to_verse'] if row['from_id']==anchor_id else row['from_verse']
            direction = "Outgoing" if row['from_id'] == anchor_id else "Incoming"
            text=f"{direction} · {other or row['to_title'] or row['from_title']} · {row['type']} · {row['status']}"
            if row['evidence']: text += f" — {row['evidence']}"
            if row['source_uri'] or row['source_detail']:
                text += f" · Source: {row['source_uri'] or row['source_detail']}"
            item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,row['id']); self.connections.addItem(item)
        has_rows=self.connections.count()>0; self.connections_section.setVisible(has_rows); self.connections_empty.setVisible(not has_rows)
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
        source_uri=QLineEdit(); source_uri.setPlaceholderText("Optional source URL or dataset identifier"); form.addRow("Source",source_uri)
        source_detail=QPlainTextEdit(); source_detail.setPlaceholderText("Optional source note, edition or provenance detail…"); form.addRow("Source detail",source_detail)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); form.addRow(controls)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            source=self.database.scripture_anchor(self.selection[0]); dest=self.database.scripture_anchor(self._parse_reference(target.text(),self.selection[0].translation)); self.database.create_relationship(source,dest,kind.currentData(),evidence=evidence.toPlainText(),source_uri=source_uri.text().strip() or None,source_detail=source_detail.toPlainText().strip() or None); self.refresh(); self.notify("Connection saved")
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
        selected = self.database.scripture_anchor(self.selection[0]) if self.selection else None
        object_id = row["to_id"] if row["from_id"] == selected else row["from_id"]
        a=self.database._connection.execute("SELECT verse_id FROM scripture_anchors WHERE object_id=?",(object_id,)).fetchone()
        if a:
            b,c,v=a[0].split(':'); self.navigateRequested.emit(ScriptureAnchor(b,int(c),int(v),self.selection[0].translation if self.selection else None))
    def _trace_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Named traces"),1); top.addWidget(button("Create trace","createTrace",self._create_trace,"primary")); l.addLayout(top)
        self.traces=QListWidget(); self.traces.setObjectName("traceList"); self.traces.currentItemChanged.connect(lambda *_: self._refresh_trace_members()); self.traces_section=self._section("traces","saved","Saved traces",self.traces); l.addWidget(self.traces_section,1)
        self.traces_empty=self._empty_state("No traces yet", "Create a named trace to follow a word, theme or passage across Scripture."); l.addWidget(self.traces_empty,1)
        controls=QHBoxLayout(); controls.addWidget(button("Add to trace","addToTrace",self._add_to_trace)); controls.addWidget(button("Edit trace","editTrace",self._edit_trace)); controls.addWidget(button("Move up","moveTraceUp",lambda: self._move_trace_member(-1))); controls.addWidget(button("Move down","moveTraceDown",lambda: self._move_trace_member(1))); self.active=QPushButton("Activate"); self.active.setCheckable(True); self.active.toggled.connect(self._toggle_trace); controls.addWidget(self.active); l.addLayout(controls)
        self.trace_members_view=QListWidget(); self.trace_members_view.setObjectName("traceMembers"); self.trace_members_view.itemDoubleClicked.connect(self._open_trace_member); l.addWidget(self._section("traces","members","Trace members",self.trace_members_view),1); return w
    def _refresh_traces(self):
        if not hasattr(self,'traces'): return
        selected=self.traces.currentItem().data(Qt.ItemDataRole.UserRole) if self.traces.currentItem() else self.active_trace; self.traces.clear()
        for row in self.database.traces():
            i=QListWidgetItem(row['title']); i.setData(Qt.ItemDataRole.UserRole,row['id']); i.setToolTip(row['description']); self.traces.addItem(i)
            if row['id']==selected: self.traces.setCurrentItem(i)
        has_rows=self.traces.count()>0; self.traces_section.setVisible(has_rows); self.traces_empty.setVisible(not has_rows)
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

    def _edit_trace(self):
        trace_id=self._selected_trace()
        if not trace_id: return
        row=next((item for item in self.database.traces() if item["id"] == trace_id), None)
        if row is None: return
        dialog=QDialog(self); dialog.setWindowTitle("Edit trace"); form=QFormLayout(dialog)
        title=QLineEdit(row["title"]); description=QPlainTextEdit(row["description"]); color=QLineEdit(row["color"])
        form.addRow("Name",title); form.addRow("Description",description); form.addRow("Colour",color)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); form.addRow(controls)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            self.database.update_trace(trace_id,title.text(),description.toPlainText(),color.text(),row["position"])
            self._refresh_traces(); self.notify("Trace updated")
        except DATA_ERRORS as error: self.show_error("Could not update the trace",error)
    def _add_to_trace(self):
        tid=self._selected_trace()
        if not tid or not self.selection: return
        try:
            for anchor in self.selection: self.database.add_trace_member(tid,self.database.scripture_anchor(anchor),self.database.trace_members(tid).__len__())
            self._refresh_trace_members(); self.notify("Added to trace")
        except DATA_ERRORS as error: self.show_error("Could not add to trace",error)

    def _move_trace_member(self, direction):
        item=self.trace_members_view.currentItem(); tid=self._selected_trace()
        if not item or not tid: return
        rows=self.database.trace_members(tid); current=self.trace_members_view.currentRow(); destination=current+direction
        if not (0 <= destination < len(rows)): return
        try:
            self.database.move_trace_member(item.data(Qt.ItemDataRole.UserRole), destination)
            self._refresh_trace_members(); self.trace_members_view.setCurrentRow(destination)
        except DATA_ERRORS as error: self.show_error("Could not reorder the trace",error)
    def _toggle_trace(self,checked):
        self.active_trace=self._selected_trace() if checked else None; self.active.setText("Deactivate" if checked else "Activate"); self.traceChanged.emit(self.active_trace)
    def _open_trace_member(self,item):
        ref=item.text().split(':')
        if len(ref)==3: self.navigateRequested.emit(ScriptureAnchor(ref[0],int(ref[1]),int(ref[2]),self.selection[0].translation if self.selection else None))
    def _study_panel(self):
        w=QWidget(); l=QVBoxLayout(w); top=QHBoxLayout(); top.addWidget(item_heading("Studies"),1); top.addWidget(button("Ask about passage","askAboutPassage",lambda: self.contextActionRequested.emit("ask"),"quiet")); top.addWidget(button("Interpret through lens","interpretThroughLens",lambda: self.contextActionRequested.emit("lens"),"quiet")); top.addWidget(button("New study","newStudy",self._create_study,"primary")); l.addLayout(top)
        self.study_list=QListWidget(); self.study_list.setObjectName("studyList"); self.study_list.itemDoubleClicked.connect(self._open_study); self.study_section=self._section("studies","dossiers","Study dossiers",self.study_list); l.addWidget(self.study_section,1)
        self.study_empty=self._empty_state("Every passage has more to explore", "Create a study to collect observations, questions and conclusions alongside Scripture."); l.addWidget(self.study_empty,1)
        controls=QHBoxLayout(); controls.addWidget(button("Edit", "editStudy", self._edit_study)); controls.addWidget(button("Attach Scripture", "attachStudyScripture", self._attach_study_selection)); controls.addWidget(button("Attach Trace", "attachStudyTrace", self._attach_study_trace)); controls.addWidget(button("Attach image", "attachStudyImage", self._attach_study_image)); controls.addWidget(button("History", "studyHistory", self._study_history)); l.addLayout(controls); return w
    def _refresh_studies(self):
        if not hasattr(self,'study_list'): return
        self.study_list.clear()
        for row in self.database.studies():
            i=QListWidgetItem(row['title']); i.setData(Qt.ItemDataRole.UserRole,row['id']); i.setToolTip(row['summary']); self.study_list.addItem(i)
        has_rows=self.study_list.count()>0; self.study_section.setVisible(has_rows); self.study_empty.setVisible(not has_rows)
    def _create_study(self):
        dialog, title, fields, traces = self._study_editor(None)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        summary, observations, questions, interpretations, conclusions = fields
        try:
            trace_ids=[item.data(Qt.ItemDataRole.UserRole) for item in traces.selectedItems()]
            self.database.create_study(title.text(),summary.toPlainText(),observations.toPlainText(),questions.toPlainText(),interpretations=interpretations.toPlainText(),conclusions=conclusions.toPlainText(),anchors=self.selection,trace_ids=trace_ids)
            self._refresh_studies(); self.notify("Study saved")
        except DATA_ERRORS as error: self.show_error("Could not create the study",error)

    def _study_editor(self, row):
        dialog=QDialog(self); dialog.setWindowTitle("New study" if row is None else "Edit study"); dialog.resize(760, 620)
        layout=QVBoxLayout(dialog); header=QHBoxLayout(); header.addWidget(QLabel("Study title")); title=QLineEdit(row["title"] if row else ""); title.setPlaceholderText("Give this study a clear working title"); header.addWidget(title,1); layout.addLayout(header)
        tabs=QTabWidget(); fields=[]
        for label,key,placeholder in (("Summary","summary","What is this study about?"),("Observations","observations","Record what the text says before interpreting it."),("Questions","questions","What needs to be tested or understood?"),("Interpretations","interpretations","State interpretations as working conclusions, not established evidence."),("Conclusions","conclusions","Summarize what you are prepared to retain.")):
            editor=QPlainTextEdit(row[key] if row else ""); editor.setPlaceholderText(placeholder); editor.setTabChangesFocus(False); fields.append(editor); tabs.addTab(editor,label)
        layout.addWidget(tabs,1)
        traces=QListWidget(); traces.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection); traces.setMaximumHeight(90); selected_trace_ids=set()
        if row:
            for relation in self.database.relationships(row["id"]):
                if relation["type"] == "study_related" and relation["from_id"] == row["id"]: selected_trace_ids.add(relation["to_id"])
        for trace in self.database.traces():
            item=QListWidgetItem(trace["title"]); item.setData(Qt.ItemDataRole.UserRole,trace["id"]); traces.addItem(item)
            if trace["id"] in selected_trace_ids: item.setSelected(True)
        layout.addWidget(QLabel("Attached traces")); layout.addWidget(traces)
        status=QLabel("Draft is local and remains unapproved until you decide what to keep."); status.setObjectName("editorStatus"); layout.addWidget(status)
        controls=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); controls.accepted.connect(dialog.accept); controls.rejected.connect(dialog.reject); layout.addWidget(controls)
        return dialog,title,fields,traces
    def _open_study(self,item):
        study_id=item.data(Qt.ItemDataRole.UserRole); row=self.database.study(study_id)
        dialog=QDialog(self); dialog.setWindowTitle(row["title"]); dialog.resize(620, 620)
        layout=QVBoxLayout(dialog); heading=QLabel(row["title"]); heading.setProperty("role","panelTitle"); layout.addWidget(heading)
        text=QPlainTextEdit(); text.setReadOnly(True)
        sections=[]
        for label,key in (("Summary","summary"),("Observations","observations"),("Questions","questions"),("Interpretations","interpretations"),("Conclusions","conclusions")):
            if row[key]: sections.append(f"{label}\n{row[key]}")
        anchors=self.database.note_anchors(study_id)
        if anchors: sections.append("Connected Scripture\n"+"\n".join(f"{a['book']} {a['chapter']}:{a['verse']}" for a in anchors))
        related_traces=[]
        for relation in self.database.relationships(study_id):
            if relation["type"] != "study_related" or relation["from_id"] != study_id:
                continue
            try:
                target=self.database.knowledge_object(relation["to_id"])
            except DATA_ERRORS:
                continue
            if target["kind"] == "trace":
                related_traces.append(target["title"])
        if related_traces:
            sections.append("Attached Traces\n"+"\n".join(sorted(set(related_traces), key=str.casefold)))
        text.setPlainText("\n\n".join(sections) or "This study is empty."); layout.addWidget(text,1)
        if anchors:
            linked=QListWidget(); linked.setObjectName("studyScriptureLinks")
            for anchor in anchors:
                link=QListWidgetItem(f"{anchor['book']} {anchor['chapter']}:{anchor['verse']}")
                link.setData(Qt.ItemDataRole.UserRole, anchor)
                linked.addItem(link)
            linked.itemDoubleClicked.connect(self._open_study_anchor)
            layout.addWidget(linked, 1)
        controls=QHBoxLayout(); controls.addWidget(button("Edit", "openStudyEdit", lambda: (dialog.accept(), self._select_study_for_edit(study_id))))
        controls.addStretch(1); controls.addWidget(button("Close", "closeStudy", dialog.accept)); layout.addLayout(controls); dialog.exec()

    def _open_study_anchor(self, item):
        anchor=item.data(Qt.ItemDataRole.UserRole)
        self.navigateRequested.emit(ScriptureAnchor(anchor["book"], int(anchor["chapter"]), int(anchor["verse"]), anchor["translation"], anchor["start"], anchor["end"]))

    def _select_study_for_edit(self, study_id):
        for index in range(self.study_list.count()):
            item=self.study_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole)==study_id:
                self.study_list.setCurrentItem(item); self._edit_study(); return

    def _selected_study(self):
        item=self.study_list.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _edit_study(self):
        study_id=self._selected_study()
        if not study_id: return
        row=self.database.study(study_id); dialog,title,fields,traces=self._study_editor(row)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return
        try:
            self.database.update_study(study_id,title.text(),*(x.toPlainText() for x in fields))
            selected={item.data(Qt.ItemDataRole.UserRole) for item in traces.selectedItems()}
            existing={relation["to_id"] for relation in self.database.relationships(study_id) if relation["type"] == "study_related" and relation["from_id"] == study_id}
            for trace_id in selected-existing: self.database.create_relationship(study_id,trace_id,"study_related")
            self._refresh_studies(); self.notify("Study saved")
        except DATA_ERRORS as error: self.show_error("Could not save the study",error)

    def _attach_study_image(self):
        study_id=self._selected_study()
        if not study_id: return
        path,_=QFileDialog.getOpenFileName(self,"Attach image or diagram","","Images (*.png *.jpg *.jpeg *.gif *.webp *.svg);;All files (*)")
        if not path: return
        try:
            self.database.attach_file(study_id,path); self.notify("Attachment saved")
        except DATA_ERRORS as error: self.show_error("Could not attach the image",error)

    def _attach_study_selection(self):
        study_id=self._selected_study()
        if not study_id:
            self.notify("Choose a study first")
            return
        if not self.selection:
            self.notify("Select Scripture in the reader first")
            return
        try:
            self.database.add_study_anchors(study_id, self.selection)
            self.notify("Scripture attached to study")
        except DATA_ERRORS as error: self.show_error("Could not attach Scripture",error)

    def _attach_study_trace(self):
        study_id=self._selected_study()
        if not study_id:
            self.notify("Choose a study first")
            return
        traces=self.database.traces()
        if not traces:
            self.notify("Create a Trace first")
            return
        labels=[row["title"] for row in traces]
        choice,ok=QInputDialog.getItem(self,"Attach Trace","Trace",labels,0,False)
        if not ok: return
        trace_id=traces[labels.index(choice)]["id"]
        try:
            self.database.create_relationship(study_id,trace_id,"study_related")
            self.notify("Trace attached to study")
        except DATA_ERRORS as error: self.show_error("Could not attach Trace",error)

    def _study_history(self):
        study_id=self._selected_study()
        if not study_id: return
        rows=self.database.note_revisions(study_id); text="\n\n".join(f"{r['created_at']}\n{r['title']}\n{r['interpretations']}\n{r['conclusions']}" for r in rows)
        QMessageBox.information(self,"Study history",text or "No saved revisions.")
