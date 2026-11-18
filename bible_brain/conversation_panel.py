from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QPlainTextEdit,QListWidget,QFileDialog,QInputDialog,QComboBox
from PySide6.QtCore import Qt
from .conversation import import_file, manual_extract, analyze_conversation
from .meaning import OllamaProvider
import hashlib

class ConversationPanel(QWidget):
    def __init__(self,session,notify,show_error):
        super().__init__(); self.database=session.database; self.notify=notify; self.show_error=show_error; self.current=None
        lay=QVBoxLayout(self); lay.addWidget(QLabel("Process Conversation")); self.text=QPlainTextEdit(); self.text.setPlaceholderText("Paste a Bible-study conversation here…"); lay.addWidget(self.text,2)
        row=QHBoxLayout()
        for label,fn in (("Import TXT/MD/JSON…",self.open_file),("Process",self.process),("Analyze with Ollama",self.analyze),("Clear",self.clear)):
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        lay.addLayout(row); self.status=QLabel("Import → Process → Review → Save"); lay.addWidget(self.status); self.proposals=QListWidget(); lay.addWidget(self.proposals,1)
        self.source=QPlainTextEdit(); self.source.setReadOnly(True); self.source.setMaximumHeight(120); lay.addWidget(self.source)
        review=QHBoxLayout()
        for label,status in (("Keep","approved"),("Investigate","investigate"),("Park","parked"),("Reject","rejected")): 
            b=QPushButton(label); b.clicked.connect(lambda checked=False,s=status:self.review(s)); review.addWidget(b)
        lay.addLayout(review); self.proposals.currentItemChanged.connect(self.show_source)
    def clear(self): self.text.clear(); self.proposals.clear(); self.current=None
    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Import conversation","","Conversation (*.txt *.md *.json)")
        if not path:return
        try: self.current=import_file(path); self.text.setPlainText(self.current.body); self.status.setText(f"Loaded {len(self.current.messages)} messages from {self.current.title}")
        except Exception as e:self.show_error("Could not import conversation",e)
    def process(self):
        try:
            if not self.current:
                body=self.text.toPlainText().strip()
                if not body: raise ValueError("Paste or import a conversation first.")
                title,ok=QInputDialog.getText(self,"Conversation title","Title",text="Imported conversation")
                if not ok:return
                parts=[x.strip() for x in body.split("\n\n") if x.strip()]; msgs=tuple({"speaker":"unknown","body":p,"source_id":str(i)} for i,p in enumerate(parts))
                self.current=type("Conversation",(),{"title":title,"body":body,"source":"local","source_date":None,"metadata":{},"fingerprint":hashlib.sha256(body.encode()).hexdigest(),"messages":msgs})()
            cid,created=self.database.import_conversation(fingerprint=self.current.fingerprint,title=self.current.title,body=self.current.body,messages=self.current.messages,source=self.current.source,source_date=self.current.source_date,metadata=self.current.metadata)
            rows=manual_extract(self.current,self.database); self.proposals.clear()
            for row in rows:
                pid=self.database.create_conversation_proposal(conversation_id=cid,**row); self.proposals.addItem(f"{row['kind']}: {row['title']}"); self.proposals.item(self.proposals.count()-1).setData(Qt.ItemDataRole.UserRole,pid)
            self.status.setText(f"{len(rows)} proposals ready for individual review (conversation {'new' if created else 'already imported'})")
        except Exception as e:self.show_error("Could not process conversation",e)
    def show_source(self,current,previous=None):
        if not current:return
        try:
            row=self.database._connection.execute("SELECT p.*,m.speaker,m.body AS message_body FROM conversation_proposals p LEFT JOIN conversation_messages m ON m.id=p.message_id WHERE p.id=?",(current.data(Qt.ItemDataRole.UserRole),)).fetchone()
            self.source.setPlainText(f"{row['speaker'] or 'unknown'}:\n{row['excerpt'] or row['message_body'] or ''}")
        except Exception: pass
    def review(self,status):
        item=self.proposals.currentItem()
        if item:
            self.database.review_conversation_proposal(item.data(Qt.ItemDataRole.UserRole),status); self.status.setText(f"Proposal marked {status}")
    def analyze(self):
        try:
            if not self.current: self.process()
            if not self.current:return
            models=OllamaProvider().models()
            if not models: raise RuntimeError("No local Ollama models are available; use Process for offline extraction.")
            rows=analyze_conversation(self.current,self.database,OllamaProvider(),models[0],timeout=60)
            cid,_=self.database.import_conversation(fingerprint=self.current.fingerprint,title=self.current.title,body=self.current.body,messages=self.current.messages,source=self.current.source,source_date=self.current.source_date,metadata=self.current.metadata)
            for row in rows: self.database.create_conversation_proposal(conversation_id=cid,**row)
            self.status.setText(f"Ollama proposed {len(rows)} items for review"); self.process()
        except Exception as e:self.show_error("Ollama analysis unavailable",e)
