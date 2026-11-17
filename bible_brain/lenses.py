from PySide6.QtCore import Signal
from PySide6.QtWidgets import QListWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QWidget, QInputDialog

class LensPanel(QWidget):
    lensChanged = Signal(object)
    def __init__(self, session, notify, show_error):
        super().__init__(); self.database=session.database; self.notify=notify; self.show_error=show_error
        layout=QVBoxLayout(self); layout.addWidget(QLabel("Lenses & Evidence")); self.list=QListWidget(); layout.addWidget(self.list,1)
        actions=QHBoxLayout()
        for label, fn in (("Create",self.create), ("Example",self.example), ("Duplicate",self.duplicate), ("Activate",self.activate), ("Archive",self.archive)):
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        layout.addLayout(actions); self.list.currentRowChanged.connect(lambda _: self.lensChanged.emit(self.current_id())); self.reload()
    def reload(self):
        self.list.clear()
        for row in self.database.lenses():
            item=f"{'● ' if row['active'] else ''}{row['title']} · {row['status']}"; self.list.addItem(item); self.list.item(self.list.count()-1).setData(32,row['id'])
    def current_id(self):
        return self.list.currentItem().data(32) if self.list.currentItem() else None
    def create(self):
        name,ok=QInputDialog.getText(self,"Create lens","Name")
        if ok and name.strip(): self.database.create_lens(name); self.reload()
    def example(self):
        try:
            lid=self.database.create_lens("Father, Son & Spirit — Delegated Authority", purpose="Examine delegated authority while preserving distinctions between persons.")
            for statement in ("The Father is the supreme source of authority.","The Son receives authority from the Father and rules on His behalf.","The Spirit is understood as the agency or means through which divine action is exercised."): self.database.create_lens_assumption(lid,statement)
            self.reload(); self.notify("Example lens created")
        except Exception as error: self.show_error("Could not create lens",error)
    def duplicate(self):
        if self.current_id(): self.database.duplicate_lens(self.current_id()); self.reload()
    def activate(self):
        if self.current_id(): self.database.set_lens_active(self.current_id(),True); self.reload()
    def archive(self):
        if self.current_id(): self.database.archive_lens(self.current_id()); self.reload()
