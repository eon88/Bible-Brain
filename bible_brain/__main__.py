"""Launch the application without starting any network services."""

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication, QMessageBox

from bible_brain import __version__
from bible_brain.session import Session, default_data_dir

logger = logging.getLogger("bible_brain")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="Bible Brain", description=__doc__)
    parser.add_argument("--version", action="version", version=f"Bible Brain {__version__}")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir(), help="Use an alternate local profile.")
    options = parser.parse_args(argv)

    app = QApplication([sys.argv[0]])
    app.setApplicationName("Bible Brain")
    app.setApplicationVersion(__version__)
    directory = options.data_dir.expanduser().resolve()
    lock = None
    session = None
    handler = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(directory / "application.lock"))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            QMessageBox.warning(None, "Bible Brain", "This Bible Brain profile is already open or unavailable.")
            return 1

        handler = RotatingFileHandler(directory / "bible-brain.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        from bible_brain.window import MainWindow

        session = Session(directory)
        window = MainWindow(session)
        window.show()
        return app.exec()
    except Exception as error:
        logger.exception("Bible Brain could not start")
        QMessageBox.critical(None, "Bible Brain", f"Bible Brain could not start.\n\n{error}")
        return 1
    finally:
        if session is not None:
            session.close()
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()
        if lock is not None and lock.isLocked():
            lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
