"""Native text selection and Scripture addresses in the chapter reader."""

from dataclasses import dataclass
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from .database import ScriptureAnchor
from .typography import SANS_FALLBACK, SERIF_FALLBACK


@dataclass(frozen=True)
class VerseSpan:
    number: int
    block_start: int
    text_start: int
    text: str
    display_text: str
    book: str = ""
    chapter: int = 0

    @property
    def text_end(self):
        return self.text_start + len(self.display_text.encode("utf-16-le")) // 2

    def text_index(self, position):
        # Qt cursors count UTF-16 code units. Anchors count Unicode characters.
        distance = max(0, min(position, self.text_end) - self.text_start)
        index = len(self.display_text.encode("utf-16-le")[: distance * 2].decode(
            "utf-16-le", errors="ignore"
        ))
        for line_break in re.finditer(r"\r\n", self.text):
            if line_break.start() >= index:
                break
            index += 1
        return index

    def cursor_index(self, offset):
        return self.text_start + len(_render_breaks(self.text[:offset]).encode("utf-16-le")) // 2


def _render_breaks(text):
    # Keep wrapped and deliberately broken lines in the same verse block.
    return re.sub(r"\r\n|[\r\n\u2029]", "\u2028", text)


class ChapterReader(QTextBrowser):
    scriptureSelected = Signal(object)

    def __init__(self, serif=SERIF_FALLBACK, sans=SANS_FALLBACK):
        super().__init__()
        self.setObjectName("chapterReader")
        self.setAccessibleName("Scripture chapter")
        self.setOpenLinks(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.setDocumentTitle("Scripture chapter")
        self.spans = []
        self.book = ""
        self.chapter = 0
        self.translation = ""
        self.verse_highlight = "#ede7dc"
        self.serif = serif
        self.sans = sans
        self.line_spacing = 137
        self.reading_width = 650

    def show_message(self, title, description, colors):
        self.spans.clear()
        self.setExtraSelections([])
        self.document().clear()
        cursor = QTextCursor(self.document())
        self._write_header(cursor, title, description, colors)
        self._update_margins()

    def show_chapter(self, translation, book, chapter, title, edition, verses, size, colors):
        self.translation = translation
        self.book = book
        self.chapter = chapter
        self.verse_highlight = colors["selected"]
        self.spans.clear()
        self.setExtraSelections([])
        self.document().clear()
        cursor = QTextCursor(self.document())
        self._write_header(cursor, title, edition, colors)

        block = QTextBlockFormat()
        block.setLeftMargin(36)
        block.setTextIndent(-36)
        block.setBottomMargin(11)
        block.setLineHeight(self.line_spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        tab = QTextOption.Tab()
        tab.position = 36
        block.setTabPositions([tab])
        number_format = self._format(self.sans, 9, colors["soft"], QFont.Weight.DemiBold)
        verse_format = self._format(self.serif, size, colors["ink"])
        empty_format = self._format(self.sans, 10, colors["soft"])
        for verse in verses:
            text = verse["text"]
            cursor.insertBlock(block, verse_format)
            block_start = cursor.position()
            cursor.insertText(f"{verse['number']}\t", number_format)
            display_text = _render_breaks(text)
            self.spans.append(VerseSpan(verse["number"], block_start, cursor.position(), text, display_text, book, chapter))
            cursor.insertText(display_text or "—", verse_format if text else empty_format)
        self._update_margins()
        self.moveCursor(QTextCursor.MoveOperation.Start)
        self.verticalScrollBar().setValue(0)

    def append_chapter(self, book, chapter, title, verses, size, colors):
        """Append an adjacent chapter while preserving exact book/chapter spans."""
        if not verses:
            return
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        heading = QTextBlockFormat(); heading.setTopMargin(28); heading.setBottomMargin(12)
        cursor.insertBlock(heading)
        cursor.insertText(title, self._format(self.serif, 25, colors["ink"]))
        block = QTextBlockFormat()
        block.setLeftMargin(36); block.setTextIndent(-36); block.setBottomMargin(11)
        block.setLineHeight(self.line_spacing, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        tab = QTextOption.Tab(); tab.position = 36; block.setTabPositions([tab])
        number_format = self._format(self.sans, 9, colors["soft"], QFont.Weight.DemiBold)
        verse_format = self._format(self.serif, size, colors["ink"])
        empty_format = self._format(self.sans, 10, colors["soft"])
        for verse in verses:
            text = verse["text"]
            cursor.insertBlock(block, verse_format)
            block_start = cursor.position()
            cursor.insertText(f"{verse['number']}\t", number_format)
            display_text = _render_breaks(text)
            self.spans.append(VerseSpan(verse["number"], block_start, cursor.position(), text, display_text, book, chapter))
            cursor.insertText(display_text or "—", verse_format if text else empty_format)
        self._update_margins()

    def _write_header(self, cursor, title, edition, colors):
        title_block = QTextBlockFormat()
        title_block.setBottomMargin(7)
        cursor.setBlockFormat(title_block)
        cursor.insertText(title, self._format(self.serif, 32, colors["ink"]))
        subtitle = QTextBlockFormat()
        subtitle.setBottomMargin(31)
        cursor.insertBlock(subtitle)
        cursor.insertText(edition, self._format(self.sans, 10, colors["soft"]))

    @staticmethod
    def _format(family, points, color, weight=QFont.Weight.Normal):
        char_format = QTextCharFormat()
        char_format.setFontFamilies([family])
        char_format.setFontPointSize(points)
        char_format.setForeground(QColor(color))
        char_format.setFontWeight(weight)
        return char_format

    def _update_margins(self):
        frame = self.document().rootFrame()
        frame_format = frame.frameFormat()
        side = max(18, (self.viewport().width() - self.reading_width) // 2)
        frame_format.setLeftMargin(side)
        frame_format.setRightMargin(side)
        frame_format.setTopMargin(38)
        frame_format.setBottomMargin(35)
        frame.setFrameFormat(frame_format)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_margins()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.publish_selection()

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)
        if event.key() in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
            Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp,
            Qt.Key.Key_A,
        ):
            self.publish_selection()

    def publish_selection(self):
        if not self.spans:
            return
        cursor = self.textCursor()
        self.setExtraSelections([])
        if cursor.hasSelection():
            anchors = self._phrase_anchors(cursor.selectionStart(), cursor.selectionEnd())
        else:
            anchors = self._verse_anchor(cursor)
        self.scriptureSelected.emit(anchors)

    def highlight_verses(self, verses, color=None):
        selections = []
        wanted = set(verses)
        for span in self.spans:
            if span.number in wanted:
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(self.document())
                selection.cursor.setPosition(span.block_start)
                selection.cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                selection.format.setBackground(QColor(color or self.verse_highlight))
                selections.append(selection)
        self.setExtraSelections(selections)

    def select_anchor(self, anchor):
        span = next((span for span in self.spans if span.number == anchor.verse and span.book == anchor.book and span.chapter == anchor.chapter), None)
        if span is None:
            return
        cursor = self.textCursor()
        cursor.setPosition(span.text_start)
        if anchor.start is not None and anchor.end is not None:
            cursor.setPosition(span.cursor_index(anchor.start))
            cursor.setPosition(span.cursor_index(anchor.end), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.publish_selection()

    def _phrase_anchors(self, start, end):
        anchors = []
        for span in self.spans:
            if span.text_start >= end:
                break
            if span.text_end <= start:
                continue
            first = span.text_index(start)
            last = span.text_index(end)
            while first < last and span.text[first].isspace():
                first += 1
            while last > first and span.text[last - 1].isspace():
                last -= 1
            if first < last:
                anchors.append(ScriptureAnchor(
                    span.book or self.book, span.chapter or self.chapter, span.number, self.translation, first, last
                ))
        return anchors

    def _verse_anchor(self, cursor):
        block_start = cursor.block().position()
        span = next((span for span in self.spans if span.block_start == block_start), None)
        if span is None:
            return []
        highlight = QTextEdit.ExtraSelection()
        highlight.cursor = QTextCursor(cursor)
        highlight.cursor.clearSelection()
        highlight.format.setBackground(QColor(self.verse_highlight))
        highlight.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        self.setExtraSelections([highlight])
        return [ScriptureAnchor(span.book or self.book, span.chapter or self.chapter, span.number)]
