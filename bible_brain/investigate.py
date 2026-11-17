from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
from .meaning import MeaningEngine, OllamaProvider

class InvestigatePanel(QWidget):
    navigateRequested = Signal(object)
    def __init__(self, session, notify, show_error):
        super().__init__(); self.session=session; self.notify=notify; self.show_error=show_error; self.selection=[]; self.investigation=None; self.engine=MeaningEngine(session.database)
        layout=QVBoxLayout(self); head=QHBoxLayout(); head.addWidget(QLabel("Investigate"),1); self.model=QComboBox(); self.model.setObjectName("aiModel"); head.addWidget(self.model); self.refresh_models(); layout.addLayout(head)
        self.question=QPlainTextEdit(); self.question.setObjectName("investigationQuestion"); self.question.setPlaceholderText("Ask a question about the selected Scripture or trace…"); self.question.setMaximumHeight(85); layout.addWidget(self.question)
        actions=QHBoxLayout(); actions.addWidget(self._button("Investigate selection",self._investigate)); actions.addWidget(self._button("Challenge",self._challenge)); actions.addWidget(self._button("Refresh models",self.refresh_models)); layout.addLayout(actions)
        self.status=QLabel("Ready"); layout.addWidget(self.status)
        self.answer=QPlainTextEdit(); self.answer.setObjectName("investigationAnswer"); self.answer.setReadOnly(True); layout.addWidget(self.answer,2)
        self.evidence=QListWidget(); self.evidence.setObjectName("investigationEvidence"); self.evidence.itemDoubleClicked.connect(self._open_evidence); layout.addWidget(self.evidence,1)
        decisions=QHBoxLayout();
        for label,status in (("Keep","approved"),("Investigate","investigate"),("Park","parked"),("Reject","rejected")): decisions.addWidget(self._button(label,lambda checked=False,s=status:self._save(s)))
        layout.addLayout(decisions)
    def _button(self,text,action):
        b=QPushButton(text); b.clicked.connect(action); return b
    @property
    def database(self): return self.session.database
    def set_selection(self,anchors): self.selection=list(anchors)
    def refresh_models(self):
        current=self.model.currentText() if hasattr(self,'model') else ""; self.model.clear(); models=OllamaProvider().models() if hasattr(self,'model') else []
        self.model.addItems(models or ["No local models available"])
        if current and self.model.findText(current)>=0: self.model.setCurrentText(current)
    def _investigate(self):
        try:
            self.status.setText("Retrieving evidence and asking the local model…"); self.answer.clear(); self.evidence.clear(); model=self.model.currentText()
            if model == "No local models available": model=""
            self.investigation=self.engine.investigate(self.question.toPlainText(),self.selection,model=model)
            self.answer.setPlainText("Answer\n"+self.investigation.answer+"\n\nObservations\n"+self.investigation.observations+"\n\nInterpretation (provisional)\n"+self.investigation.interpretation+"\n\nChallenges\n"+self.investigation.challenges+"\n\nUnresolved\n"+self.investigation.unresolved)
            for item in self.investigation.evidence:
                row=QListWidgetItem(f"{item.reference or item.title} · {item.kind} · {item.status}"); row.setData(Qt.ItemDataRole.UserRole,item); self.evidence.addItem(row)
            self.status.setText(f"Evidence retrieved: {len(self.investigation.evidence)} · not saved")
        except (ValueError,RuntimeError) as error: self.status.setText(str(error)); self.show_error("Investigation unavailable",error)
    def _challenge(self):
        current=self.question.toPlainText().strip(); self.question.setPlainText((current+"\n\nChallenge this interpretation and identify counterevidence.").strip()); self._investigate()
    def _save(self,status):
        if not self.investigation: return
        try: self.engine.save_proposal(self.investigation,status=status); self.notify("AI proposal saved for user review"); self.status.setText("Saved as "+status)
        except (ValueError,RuntimeError) as error: self.show_error("Could not save proposal",error)
    def _open_evidence(self,item):
        evidence=item.data(Qt.ItemDataRole.UserRole)
        if evidence and evidence.reference and re_reference(evidence.reference): self.navigateRequested.emit(re_reference(evidence.reference))

def re_reference(reference):
    try:
        book, chapter, verse = reference.replace(':',' ').split(); from .database import ScriptureAnchor; return ScriptureAnchor(book,int(chapter),int(verse))
    except (ValueError,TypeError): return None
