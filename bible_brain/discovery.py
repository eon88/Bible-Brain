from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QListWidget,QListWidgetItem
from PySide6.QtCore import Qt

class DiscoveryPanel(QWidget):
    def __init__(self,session,notify,show_error):
        super().__init__(); self.database=session.database; self.notify=notify; self.show_error=show_error; self.selection=[]; self.trace_id=None
        lay=QVBoxLayout(self); lay.addWidget(QLabel("Discover Connections")); self.status=QLabel("Deterministic offline retrieval"); lay.addWidget(self.status); self.results=QListWidget(); lay.addWidget(self.results,1)
        row=QHBoxLayout()
        for label,fn in (("Discover from Selection",self.discover),("Explore Trace",self.explore),("Challenge Pattern",self.challenge),("Keep",lambda:self.review('approved')),("Investigate",lambda:self.review('investigate')),("Park",lambda:self.review('parked')),("Reject",lambda:self.review('rejected'))):
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        lay.addLayout(row)
    def set_selection(self,anchors): self.selection=list(anchors)
    def set_trace(self,trace_id): self.trace_id=trace_id
    def discover(self): self._run(False)
    def explore(self): self._run(False)
    def challenge(self): self._run(True)
    def _run(self,challenge):
        try:
            rows=self.database.discover_connections(self.selection,self.trace_id,challenge=challenge); self.results.clear()
            for row in rows:
                pid=self.database.save_discovery(row); item=QListWidgetItem(f"{row['kind']}: {row['title']} [{row['confidence']}]\n{row['body']}\nLimitations: {row['limitations']}"); item.setData(Qt.ItemDataRole.UserRole,pid); self.results.addItem(item)
            self.status.setText(f"{len(rows)} candidates · nothing saved as approved")
        except Exception as e:self.show_error("Discovery unavailable",e)
    def review(self,status):
        item=self.results.currentItem()
        if not item:return
        try:self.database.review_discovery(item.data(Qt.ItemDataRole.UserRole),status); self.status.setText(f"Discovery marked {status}")
        except Exception as e:self.show_error("Could not review discovery",e)
