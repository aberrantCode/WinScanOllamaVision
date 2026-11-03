import threading

from PyQt6.QtCore import QCoreApplication, QObject, QThread, QTimer, pyqtSignal

app = QCoreApplication([])
main_tid = threading.get_ident()
print("main thread:", main_tid)


class W(QThread):
    done = pyqtSignal(int)

    def run(self):
        print("worker run thread:", threading.get_ident())
        self.done.emit(1)


results = {}


def closure_slot(n):
    results["closure"] = threading.get_ident()


class Recv(QObject):
    def slot(self, n):
        results["bound"] = threading.get_ident()


recv = Recv()
w = W()
w.done.connect(closure_slot)  # plain closure (like main.py)
w.done.connect(recv.slot)  # bound QObject method (like import_panel.py)
w.finished.connect(app.quit)
w.start()
QTimer.singleShot(3000, app.quit)
app.exec()
print("closure ran on main thread?", results.get("closure") == main_tid)
print("bound   ran on main thread?", results.get("bound") == main_tid)
