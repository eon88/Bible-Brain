from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget
from .meaning import MeaningEngine, OllamaProvider

class InvestigationWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    progress = Signal(int, str)
    def __init__(self, provider, prompt, model, timeout):
        super().__init__(); self.provider=provider; self.prompt=prompt; self.model=model; self.timeout=timeout
    def run(self):
        try:
            self.progress.emit(20, "Calling local model…")
            raw=self.provider.complete(self.prompt, self.model, self.timeout)
            self.progress.emit(100, "Model response received")
            self.finished.emit(raw)
        except Exception as error:
            self.failed.emit(str(error))

class InvestigatePanel(QWidget):
    navigateRequested = Signal(object)
    def __init__(self, session, notify, show_error):
        super().__init__(); self.session=session; self.notify=notify; self.show_error=show_error; self.selection=[]; self.investigation=None; self.engine=MeaningEngine(session.database)
        layout=QVBoxLayout(self); head=QHBoxLayout(); head.addWidget(QLabel("Investigate"),1); self.lens=QComboBox(); self.lens.setObjectName("investigationLens"); self.lens.addItem("No theological lens",None); [self.lens.addItem(row["title"],row["id"]) for row in session.database.lenses()]; head.addWidget(self.lens); self.model=QComboBox(); self.model.setObjectName("aiModel"); head.addWidget(self.model); self.refresh_models(); layout.addLayout(head); self.mode="interpret"
        self.question=QPlainTextEdit(); self.question.setObjectName("investigationQuestion"); self.question.setPlaceholderText("Ask a question about the selected Scripture or trace…"); self.question.setMaximumHeight(85); layout.addWidget(self.question)
        actions=QHBoxLayout(); actions.addWidget(self._button("Interpret Through Lens",lambda:self._run_mode("interpret"))); actions.addWidget(self._button("Test Lens",lambda:self._run_mode("test"))); actions.addWidget(self._button("Investigate selection",self._investigate)); actions.addWidget(self._button("Challenge",self._challenge)); actions.addWidget(self._button("Refresh models",self.refresh_models)); layout.addLayout(actions)
        self.status=QLabel("Ready"); layout.addWidget(self.status); self._thread=None; self._worker=None
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
    def _run_mode(self, mode): self.mode=mode; self._investigate()
    def refresh_models(self):
        current=self.model.currentText() if hasattr(self,'model') else ""; self.model.clear(); models=OllamaProvider().models() if hasattr(self,'model') else []
        self.model.addItems(models or ["No local models available"])
        if current and self.model.findText(current)>=0: self.model.setCurrentText(current)
    def _investigate(self):
        try:
            if self._thread is not None and self._thread.isRunning():
                self.status.setText("An investigation is already running."); return
            self.status.setText("Retrieving evidence…"); self.answer.clear(); self.evidence.clear(); model=self.model.currentText()
            if model == "No local models available": model=""
            question=self.question.toPlainText().strip()
            if not question: raise ValueError("Ask a research question first.")
            evidence=self.engine.retriever.retrieve(self.selection, query=question)
            if not model:
                models=self.engine.provider.models()
                if not models: raise RuntimeError("No local AI model is available. Research retrieval remains available offline.")
                model=models[0]
            context="\n".join(f"[{i.source_id}] {i.kind} {i.reference or ''}: {i.text} (status={i.status})" for i in evidence)
            lens_id=self.lens.currentData(); evidence=self.engine.retriever.retrieve(self.selection, query=question, lens_id=lens_id)
            context="\n".join(f"[{i.source_id}] {i.kind} {i.reference or ''}: {i.text} (status={i.status})" for i in evidence)
            instruction="Interpret the evidence through the selected lens assumptions." if self.mode == "interpret" else "Test the lens assumptions and seek counterevidence and alternatives."
            prompt=f"Question: {question}\nMode: {self.mode}. {instruction}\n\nEvidence:\n{context}\n\nReturn JSON keys answer, observations, interpretation, challenges, unresolved, citations. Citations must use only source IDs or references in the evidence."
            self._pending=(question,evidence,model); self._thread=QThread(self); self._worker=InvestigationWorker(self.engine.provider,prompt,model,60); self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run); self._worker.progress.connect(lambda _,message:self.status.setText(message)); self._worker.finished.connect(self._worker_finished); self._worker.failed.connect(self._worker_failed); self._worker.finished.connect(self._thread.quit); self._worker.failed.connect(self._thread.quit); self._thread.finished.connect(self._thread_done); self._thread.start(); return
        except (ValueError,RuntimeError) as error: self.status.setText(str(error)); self.show_error("Investigation unavailable",error)
    def _worker_finished(self, raw):
        try:
            question,evidence,model=self._pending; self.investigation=self.engine.parse_response(question,evidence,raw,model)
            self.answer.setPlainText("Answer\n"+self.investigation.answer+"\n\nObservations\n"+self.investigation.observations+"\n\nInterpretation (provisional)\n"+self.investigation.interpretation+"\n\nChallenges\n"+self.investigation.challenges+"\n\nUnresolved\n"+self.investigation.unresolved)
            for item in self.investigation.evidence:
                row=QListWidgetItem(f"{item.reference or item.title} · {item.kind} · {item.status}"); row.setData(Qt.ItemDataRole.UserRole,item); self.evidence.addItem(row)
            self.status.setText(f"Evidence retrieved: {len(self.investigation.evidence)} · not saved")
        except (ValueError,RuntimeError) as error: self._worker_failed(str(error))
    def _worker_failed(self, message):
        self.status.setText(message); self.show_error("Investigation unavailable", RuntimeError(message))
    def _thread_done(self):
        self._worker=None; self._thread.deleteLater(); self._thread=None
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
