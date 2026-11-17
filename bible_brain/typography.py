"""Register the typefaces shipped with the offline application."""

import logging
from pathlib import Path

from PySide6.QtGui import QFontDatabase

SERIF = "Crimson Text"
SANS = "Source Sans 3"
SERIF_FALLBACK = "Georgia"
SANS_FALLBACK = "Segoe UI"
FONT_DIR = Path(__file__).resolve().with_name("fonts")


def load_fonts():
    if SERIF not in QFontDatabase.families():
        _register("CrimsonText-Regular.ttf")
    if SANS not in QFontDatabase.families():
        _register("SourceSans3-Regular.otf")
        _register("SourceSans3-Semibold.otf")
    available = QFontDatabase.families()
    return (
        SERIF if SERIF in available else SERIF_FALLBACK,
        SANS if SANS in available else SANS_FALLBACK,
    )


def _register(filename):
    if QFontDatabase.addApplicationFont(str(FONT_DIR / filename)) == -1:
        logging.getLogger(__name__).warning("Could not load bundled font %s", filename)
