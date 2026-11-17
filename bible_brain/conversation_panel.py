from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QPlainTextEdit,QListWidget,QFileDialog,QInputDialog
from PySide6.QtCore import Qt
from .conversation import import_file, manual_extract
import hashlib

class ConversationPanel(QWidget):
    def __init__(self,session,notify,show_error):
        super().__init__(); self.database=session.database; self.notify=notify; self.show_error=show_error; self.current=None
        lay=QVBoxLayout(self); lay.addWidget(QLabel("Process Conversation")); self.text=QPlainTextEdit(); self.text.setPlaceholderText("Paste a Bible-study conversation here…"); lay.addWidget(self.text,2)
        row=QHBoxLayout()
        for label,fn in (("Import TXT/MD/JSON…",self.open_file),("Process",self.process),("Clear",self.clear)):
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        lay.addLayout(row); self.status=QLabel("Import → Process → Review → Save"); lay.addWidget(self.status); self.proposals=QListWidget(); lay.addWidget(self.proposals,1)
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
