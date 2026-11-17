"""SQLite repositories for the Scripture tree and its shared research graph."""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from hashlib import sha256
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
from tempfile import mkstemp
from time import monotonic
import unicodedata
from uuid import uuid4


log = logging.getLogger(__name__)

APPLICATION_ID = 0x4242524E  # BBRN
SCHEMA_VERSION = 9
MIGRATIONS = ("001_foundation.sql", "002_original_languages.sql", "003_original_token_variants.sql", "004_original_variant_identity.sql", "005_language_provenance.sql", "006_knowledge_graph.sql", "007_workspace_control.sql", "008_lenses_contradictions.sql", "009_conversations.sql")
BACKUP_BUSY_SECONDS = 5
NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
KEEP_FOLDER = object()
CODE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
BOOK_PATTERN = re.compile(r"[A-Z0-9]{3}")
REVIEW_STATUSES = {"approved", "investigate", "parked", "rejected"}

def _media_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


@dataclass(frozen=True, slots=True)
class ScriptureAnchor:
    book: str
    chapter: int
    verse: int
    translation: str | None = None
    start: int | None = None
    end: int | None = None


def _run_migration(connection: sqlite3.Connection, name: str) -> None:
    path = Path(__file__).with_name("migrations") / name
    statement = ""
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError(f"Incomplete SQL statement in {name}.")


def _schema(connection: sqlite3.Connection) -> tuple:
    rows = connection.execute(
        """SELECT type, name, sql FROM sqlite_master
           WHERE sql IS NOT NULL AND name NOT GLOB 'sqlite_*' ORDER BY type, name"""
    )
    return tuple(tuple(row) for row in rows)


@cache
def _expected_schema(version: int) -> tuple:
    with closing(sqlite3.connect(":memory:")) as memory:
        for migration in MIGRATIONS[:version]:
            _run_migration(memory, migration)
        return _schema(memory)


@contextmanager
def _transaction(connection: sqlite3.Connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


@contextmanager
def _temporary_database(directory: Path):
    fd, name = mkstemp(prefix=".bible-brain-", suffix=".sqlite3", dir=directory)
    os.close(fd)
    path = Path(name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def _configure(connection: sqlite3.Connection) -> None:
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA trusted_schema = OFF")
    connection.execute("PRAGMA recursive_triggers = ON")


@contextmanager
def _database_ownership(path: Path):
    """Keep one Bible Brain instance responsible for an active database path."""
    message = "This database is already open in another Bible Brain instance."
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        path_hash = sha256(os.path.normcase(str(path)).encode("utf-8")).hexdigest()
        ctypes.set_last_error(0)
        handle = kernel.CreateMutexW(None, False, f"Local\\BibleBrain-{path_hash}")
        error = ctypes.get_last_error()
        if not handle:
            raise ctypes.WinError(error)
        try:
            if error == 183:  # ERROR_ALREADY_EXISTS
                raise ValueError(message)
            yield
        finally:
            kernel.CloseHandle(handle)
    else:
        import fcntl

        marker = path.with_name(f".{path.name}.bible-brain.lock")
        with marker.open("ab") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(message) from error
            yield


def _require_name(value: str, label: str, limit: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"Enter a {label.lower()}.")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{label} must be {limit} characters or fewer.")
    return value


def _name_key(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold()


def _require_text(value: str, label: str) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError(f"{label} must be valid text.")
    return value


def _require_integer(value: int, label: str, minimum: int = 1) -> int:
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        raise ValueError(f"{label} must be an integer of at least {minimum}.")
    return value


def _verify_database(connection: sqlite3.Connection) -> None:
    application_id = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if application_id != APPLICATION_ID:
        raise ValueError("This file is not a Bible Brain database.")
    if version != SCHEMA_VERSION:
        raise ValueError(f"This database uses schema version {version}. This app expects {SCHEMA_VERSION}.")
    if _schema(connection) != _expected_schema(version):
        raise ValueError("The Bible Brain database schema has been changed or is incomplete.")
    results = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    if results != ["ok"] or connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("The Bible Brain database failed its SQLite integrity check.")
    if connection.execute("SELECT 1 FROM translations WHERE sealed_at IS NULL LIMIT 1").fetchone():
        raise ValueError("The database contains an unfinished Scripture import.")
    if connection.execute("SELECT 1 FROM language_resources WHERE sealed_at IS NULL LIMIT 1").fetchone():
        raise ValueError("The database contains an unfinished original-language import.")


class Database:
    """A local library connection owned by the application thread."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ownership = _database_ownership(self.path)
        self._ownership.__enter__()
        self._connection = None
        try:
            self._connection = sqlite3.connect(self.path, isolation_level=None, timeout=5)
            _configure(self._connection)
            self._migrate()
            self.check_integrity()
        except BaseException:
            self.close()
            raise
        log.info("Opened and verified local database (schema %s)", SCHEMA_VERSION)

    def close(self) -> None:
        try:
            if self._connection is not None:
                self._connection.close()
        finally:
            self._ownership.__exit__(None, None, None)

    def _migrate(self) -> None:
        connection = self._connection
        with _transaction(connection):
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if application_id == 0 and version == 0 and not _schema(connection):
                connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            elif application_id != APPLICATION_ID:
                raise ValueError("This file is not a Bible Brain database.")
            elif version < 0:
                raise ValueError("The Bible Brain database has an invalid schema version.")
            elif version > SCHEMA_VERSION:
                raise ValueError(f"This database requires a newer Bible Brain version (schema {version}).")
            if _schema(connection) != _expected_schema(version):
                raise ValueError("The Bible Brain database schema has been changed or is incomplete.")
            for number, name in enumerate(MIGRATIONS[version:], start=version + 1):
                _run_migration(connection, name)
                connection.execute(f"PRAGMA user_version = {number}")

    def check_integrity(self) -> None:
        _verify_database(self._connection)

    def import_translation(self, *, code, name, language, license, source_url, verses) -> int:
        """Install a sealed edition from validated verse tuples in a single transaction."""
        if not isinstance(code, str) or CODE_PATTERN.fullmatch(code) is None:
            raise ValueError("Translation code must use 1–32 letters, digits, dots, underscores or hyphens.")
        metadata = (
            _require_name(name, "Translation title"),
            _require_name(language, "Language", 35),
            _require_name(license, "Licence", 2_000),
            _require_name(source_url, "Source", 2_000),
        )
        books = {}
        book_order = {}
        references = set()
        records = []
        for book, book_name, order, chapter, verse, text in verses:
            if not isinstance(book, str) or BOOK_PATTERN.fullmatch(book) is None:
                raise ValueError(f"Invalid three-character USFM book code {book!r}.")
            book_name = _require_name(book_name, "Book name")
            _require_integer(order, "Book order")
            _require_integer(chapter, "Chapter number")
            _require_integer(verse, "Verse number")
            if books.setdefault(book, (book_name, order)) != (book_name, order):
                raise ValueError(f"Inconsistent name or order for book {book}.")
            if book_order.setdefault(order, book) != book:
                raise ValueError(f"Multiple books use order {order}.")
            reference = (book, chapter, verse)
            if reference in references:
                raise ValueError(f"Duplicate verse {book} {chapter}:{verse}.")
            references.add(reference)
            records.append((order, book, chapter, verse, _require_text(text, "Verse text")))
        if not records:
            raise ValueError("The Scripture dataset contains no verses.")
        records.sort()
        digest = sha256()
        digest.update(json.dumps([metadata, sorted(books.items())], ensure_ascii=False).encode("utf-8"))
        for record in records:
            digest.update(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        content_hash = digest.hexdigest()
        connection = self._connection
        with _transaction(connection):
            existing = connection.execute("SELECT content_hash FROM translations WHERE code = ?", (code,)).fetchone()
            if existing is not None:
                if existing["content_hash"] != content_hash:
                    raise ValueError(f"Translation {code} is already installed. Use a new code for a different edition.")
                return 0
            connection.execute(
                """INSERT INTO translations(code, name, language, license, source_url, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""", (code, *metadata, content_hash),
            )
            connection.executemany("INSERT OR IGNORE INTO books(code) VALUES (?)", ((book,) for book in books))
            connection.executemany(
                "INSERT INTO translation_books(translation_code, book_code, name, sort_order) VALUES (?, ?, ?, ?)",
                ((code, book, *details) for book, details in books.items()),
            )
            chapters = {(book, chapter) for book, chapter, _ in references}
            connection.executemany(
                "INSERT OR IGNORE INTO chapters(id, book_code, number) VALUES (?, ?, ?)",
                ((f"{book}:{chapter}", book, chapter) for book, chapter in sorted(chapters)),
            )
            connection.executemany(
                "INSERT OR IGNORE INTO canonical_verses(id, chapter_id, number) VALUES (?, ?, ?)",
                ((f"{book}:{chapter}:{verse}", f"{book}:{chapter}", verse) for _, book, chapter, verse, _ in records),
            )
            connection.executemany(
                "INSERT INTO scripture_texts(translation_code, verse_id, body) VALUES (?, ?, ?)",
                ((code, f"{book}:{chapter}:{verse}", text) for _, book, chapter, verse, text in records),
            )
            connection.execute(f"UPDATE translations SET sealed_at = {NOW} WHERE code = ?", (code,))
        log.info("Imported Scripture edition %s (%s verse addresses)", code, len(records))
        return len(records)

    def translations(self) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT code, name, language, license, source_url FROM translations
               WHERE sealed_at IS NOT NULL ORDER BY name COLLATE NOCASE, code"""
        ).fetchall()

    def import_original_language(self, *, code, language, name, license, source_url,
                                 lexemes, tokens, morphologies=(), source_revision="", source_manifest=()) -> int:
        """Atomically import a verifiable lexicon and verse token map.

        Tokens deliberately point to canonical verse IDs, never to translation text
        offsets; alignment is therefore an explicit future layer rather than an
        assumption made by this importer.
        """
        if not isinstance(code, str) or CODE_PATTERN.fullmatch(code) is None:
            raise ValueError("Original-language resource code is invalid.")
        if language not in {"he", "el", "arc"}:
            raise ValueError("Language must be Hebrew (he), Greek (el), or Aramaic (arc).")
        metadata = (_require_name(name, "Resource title"), _require_name(license, "Licence", 2_000),
                    _require_name(source_url, "Source", 2_000))
        if not isinstance(lexemes, list) or not lexemes:
            raise ValueError("The resource must contain lexemes.")
        if not isinstance(tokens, list) or not tokens:
            raise ValueError("The resource must contain verse tokens.")
        lexeme_rows = {}
        for row in lexemes:
            if not isinstance(row, dict):
                raise ValueError("Each lexeme must be an object.")
            strongs = _require_name(row.get("strongs"), "Strong's identifier", 40)
            lemma = _require_name(row.get("lemma"), "Lemma", 300)
            lexeme_rows[strongs] = (lemma, _require_text(row.get("transliteration", ""), "Transliteration"),
                                    _require_text(row.get("definition", ""), "Dictionary definition"))
        morphology_rows = []
        for row in morphologies:
            if not isinstance(row, dict):
                raise ValueError("Each morphology must be an object.")
            morphology_rows.append((_require_name(row.get("code"), "Morphology code", 80),
                                    _require_name(row.get("label"), "Morphology label", 300),
                                    _require_text(row.get("description", ""), "Morphology description")))
        token_rows = []
        seen = set()
        for row in tokens:
            if not isinstance(row, dict):
                raise ValueError("Each token must be an object.")
            book = row.get("book"); chapter = row.get("chapter"); verse = row.get("verse")
            ordinal = row.get("ordinal"); strongs = row.get("strongs")
            if not isinstance(book, str) or BOOK_PATTERN.fullmatch(book) is None:
                raise ValueError("Token book must be a USFM code.")
            _require_integer(chapter, "Token chapter"); _require_integer(verse, "Token verse")
            _require_integer(ordinal, "Token ordinal", 0)
            if strongs not in lexeme_rows:
                raise ValueError(f"Token refers to missing lexeme {strongs!r}.")
            if self._connection.execute("SELECT 1 FROM canonical_verses WHERE id = ?", (f"{book}:{chapter}:{verse}",)).fetchone() is None:
                raise ValueError(f"Token refers to unavailable Scripture address {book} {chapter}:{verse}.")
            surface = _require_name(row.get("surface"), "Token surface", 500)
            variant = _require_text(row.get("variant", ""), "Textual variant")
            key = (book, chapter, verse, ordinal, variant)
            if key in seen: raise ValueError("Duplicate original-language token address.")
            seen.add(key)
            token_rows.append((book, chapter, verse, ordinal, surface, strongs, row.get("morphology"), variant))
        digest = sha256(json.dumps([code, language, metadata, lexemes, tokens, list(morphologies)], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with _transaction(self._connection):
            existing = self._connection.execute("SELECT content_hash FROM language_resources WHERE code = ?", (code,)).fetchone()
            if existing:
                if existing["content_hash"] != digest:
                    raise ValueError(f"Original-language resource {code} is already installed with different content.")
                return 0
            resource_id = uuid4().hex
            manifest_json = json.dumps(list(source_manifest), ensure_ascii=False, sort_keys=True)
            self._connection.execute("INSERT INTO language_resources(id, code, language, name, license, source_url, content_hash, source_revision, source_manifest) VALUES (?,?,?,?,?,?,?,?,?)", (resource_id, code, language, *metadata, digest, _require_text(source_revision, "Source revision"), manifest_json))
            for morph in morphology_rows:
                self._connection.execute("INSERT OR IGNORE INTO morphologies(language, code, label, description) VALUES (?,?,?,?)", (language, *morph))
            for strongs, (lemma, transliteration, definition) in lexeme_rows.items():
                self._connection.execute("INSERT INTO lexemes(id, resource_id, strongs, language, lemma, transliteration, dictionary_definition) VALUES (?,?,?,?,?,?,?)", (uuid4().hex, resource_id, strongs, language, lemma, transliteration, definition))
            for book, chapter, verse, ordinal, surface, strongs, morphology, variant in token_rows:
                lexeme_id = self._connection.execute("SELECT id FROM lexemes WHERE resource_id=? AND strongs=?", (resource_id, strongs)).fetchone()[0]
                self._connection.execute("INSERT INTO original_tokens(id, resource_id, verse_id, ordinal, surface, lexeme_id, morphology_code, textual_variant) VALUES (?,?,?,?,?,?,?,?)", (uuid4().hex, resource_id, f"{book}:{chapter}:{verse}", ordinal, surface, lexeme_id, morphology, variant))
            self._connection.execute(f"UPDATE language_resources SET sealed_at = {NOW} WHERE id = ?", (resource_id,))
        return len(token_rows)

    def language_resources(self):
        return self._connection.execute("SELECT code, language, name, license, source_url FROM language_resources WHERE sealed_at IS NOT NULL ORDER BY name").fetchall()

    def original_tokens(self, book, chapter, verse):
        return self._connection.execute("""SELECT ot.*, l.strongs, l.lemma, l.transliteration, l.dictionary_definition,
            m.label AS morphology_label, m.description AS morphology_description
            FROM original_tokens ot JOIN lexemes l ON l.id=ot.lexeme_id
            LEFT JOIN morphologies m ON m.language=l.language AND m.code=ot.morphology_code
            WHERE ot.verse_id=? ORDER BY ot.ordinal""", (f"{book}:{chapter}:{verse}",)).fetchall()

    def lexeme_occurrences(self, strongs):
        return self._connection.execute("SELECT ot.verse_id, ot.ordinal, ot.surface, lr.code AS resource_code FROM original_tokens ot JOIN lexemes l ON l.id=ot.lexeme_id JOIN language_resources lr ON lr.id=ot.resource_id WHERE l.strongs=? ORDER BY ot.verse_id, ot.ordinal", (strongs,)).fetchall()

    def books(self, translation: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT book_code AS code, name, sort_order FROM translation_books
               WHERE translation_code = ? COLLATE NOCASE ORDER BY sort_order""", (translation,)
        ).fetchall()

    def chapters(self, translation: str, book: str) -> list[int]:
        rows = self._connection.execute(
            """SELECT c.number FROM chapters c WHERE c.book_code = ? AND EXISTS (
                   SELECT 1 FROM canonical_verses v JOIN scripture_texts st ON st.verse_id = v.id
                   WHERE v.chapter_id = c.id AND st.translation_code = ? COLLATE NOCASE
               ) ORDER BY c.number""", (book, translation),
        )
        return [row["number"] for row in rows]

    def verses(self, translation: str, book: str, chapter: int) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT v.id, v.number, st.body AS text FROM chapters c
               JOIN canonical_verses v ON v.chapter_id = c.id
               JOIN scripture_texts st ON st.verse_id = v.id
               WHERE c.book_code = ? AND c.number = ? AND st.translation_code = ? COLLATE NOCASE
               ORDER BY v.number""", (book, chapter, translation),
        ).fetchall()

    def next_chapter(self, translation: str, book: str, chapter: int, step: int) -> tuple[str, int] | None:
        if step not in (-1, 1):
            raise ValueError("Chapter direction must be -1 or 1.")
        books = [entry["code"] for entry in self.books(translation)]
        if book not in books:
            return None
        chapters = self.chapters(translation, book)
        if chapter not in chapters:
            return None
        index = chapters.index(chapter) + step
        if 0 <= index < len(chapters):
            return book, chapters[index]
        book_index = books.index(book) + step
        if not 0 <= book_index < len(books):
            return None
        adjacent_book = books[book_index]
        adjacent_chapters = self.chapters(translation, adjacent_book)
        return adjacent_book, adjacent_chapters[0 if step > 0 else -1]

    def folders(self) -> list[sqlite3.Row]:
        return self._connection.execute(
            "SELECT id, name, parent_id FROM folders ORDER BY name_key, id"
        ).fetchall()

    def _require_folder(self, folder_id: str | None) -> None:
        if folder_id is None:
            return
        if self._connection.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone() is None:
            raise ValueError("The research folder no longer exists.")

    def _folder_slot_available(self, parent_id, name, except_id=None) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM folders WHERE parent_id IS ? AND name_key = ? AND id IS NOT ?",
            (parent_id, _name_key(name), except_id),
        ).fetchone() is None

    def create_folder(self, name: str, parent_id: str | None = None) -> str:
        name = _require_name(name, "Folder name")
        folder_id = uuid4().hex
        with _transaction(self._connection):
            self._require_folder(parent_id)
            if not self._folder_slot_available(parent_id, name):
                raise ValueError("A folder with that name already exists here.")
            self._connection.execute(
                "INSERT INTO folders(id, parent_id, name, name_key) VALUES (?, ?, ?, ?)",
                (folder_id, parent_id, name, _name_key(name)),
            )
        return folder_id

    def rename_folder(self, folder_id: str, name: str) -> None:
        name = _require_name(name, "Folder name")
        with _transaction(self._connection):
            self._require_folder(_require_name(folder_id, "Folder identifier"))
            folder = self._connection.execute("SELECT parent_id FROM folders WHERE id = ?", (folder_id,)).fetchone()
            if not self._folder_slot_available(folder["parent_id"], name, folder_id):
                raise ValueError("A folder with that name already exists here.")
            self._connection.execute(
                f"UPDATE folders SET name = ?, name_key = ?, updated_at = {NOW} WHERE id = ?",
                (name, _name_key(name), folder_id),
            )

    def move_folder(self, folder_id: str, parent_id: str | None) -> None:
        with _transaction(self._connection):
            self._require_folder(_require_name(folder_id, "Folder identifier"))
            self._require_folder(parent_id)
            folder = self._connection.execute("SELECT name FROM folders WHERE id = ?", (folder_id,)).fetchone()
            if not self._folder_slot_available(parent_id, folder["name"], folder_id):
                raise ValueError("A folder with that name already exists at the destination.")
            self._connection.execute(
                f"UPDATE folders SET parent_id = ?, updated_at = {NOW} WHERE id = ?", (parent_id, folder_id)
            )

    def delete_folder(self, folder_id: str) -> None:
        """Rehome children and notes to the enclosing folder before removing the folder."""
        connection = self._connection
        with _transaction(connection):
            self._require_folder(_require_name(folder_id, "Folder identifier"))
            parent_id = connection.execute("SELECT parent_id FROM folders WHERE id = ?", (folder_id,)).fetchone()[0]
            # Vacate this folder's name while keeping its ID available to its dependents.
            connection.execute("UPDATE folders SET name_key = ? WHERE id = ?", (f"\x00{folder_id}", folder_id))
            children = connection.execute("SELECT id, name FROM folders WHERE parent_id = ? ORDER BY id", (folder_id,)).fetchall()
            for child in children:
                name = child["name"]
                suffix_number = 2
                while not self._folder_slot_available(parent_id, name):
                    suffix = f" ({suffix_number})"
                    name = child["name"][:200 - len(suffix)] + suffix
                    suffix_number += 1
                connection.execute(
                    f"UPDATE folders SET parent_id = ?, name = ?, name_key = ?, updated_at = {NOW} WHERE id = ?",
                    (parent_id, name, _name_key(name), child["id"]),
                )
            note_ids = [row[0] for row in connection.execute("SELECT object_id FROM notes WHERE folder_id = ?", (folder_id,))]
            for note_id in note_ids:
                connection.execute("UPDATE notes SET folder_id = ? WHERE object_id = ?", (parent_id, note_id))
                self._touch_note(note_id)
                self._snapshot_note(note_id)
            connection.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

    def _insert_object(self, kind, title, body, origin="user", source_uri=None, source_detail=None) -> str:
        object_id = uuid4().hex
        self._connection.execute(
            """INSERT INTO knowledge_objects(id, kind, title, body, origin, source_uri, source_detail)
               VALUES (?, ?, ?, ?, ?, ?, ?)""", (object_id, kind, title, body, origin, source_uri, source_detail)
        )
        return object_id

    def create_knowledge_object(self, kind, title, body="", *, origin="user", source_uri=None, source_detail=None) -> str:
        kind = _require_name(kind, "Knowledge object type", 80)
        if kind in {"note", "scripture_anchor"}:
            raise ValueError("Use the note or Scripture anchor API for this object type.")
        title = _require_name(title, "Knowledge title")
        body = _require_text(body, "Knowledge text")
        with _transaction(self._connection):
            return self._insert_object(kind, title, body, origin, source_uri, source_detail)

    def knowledge_object(self, object_id) -> sqlite3.Row:
        item = self._connection.execute("SELECT * FROM knowledge_objects WHERE id = ?", (object_id,)).fetchone()
        if item is None:
            raise ValueError("The knowledge object no longer exists.")
        return item

    def _insert_relationship(self, from_id, to_id, kind, evidence="", origin="user", source_uri=None,
                             source_detail=None, position=0) -> str:
        relationship_id = uuid4().hex
        self._connection.execute(
            """INSERT INTO knowledge_relationships(
                   id, from_id, to_id, type, evidence, origin, source_uri, source_detail, position
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (relationship_id, from_id, to_id, kind, evidence, origin, source_uri, source_detail, position),
        )
        return relationship_id

    def create_relationship(self, from_id, to_id, kind, *, evidence="", origin="user", source_uri=None,
                            source_detail=None, position=0) -> str:
        if kind == "scripture_reference":
            raise ValueError("Use the note API to manage note attachments.")
        evidence = _require_text(evidence, "Relationship evidence")
        with _transaction(self._connection):
            existing = self._connection.execute("SELECT id FROM knowledge_relationships WHERE from_id=? AND type=? AND to_id=?", (from_id, kind, to_id)).fetchone()
            if existing is not None:
                return existing["id"]
            return self._insert_relationship(from_id, to_id, kind, evidence, origin, source_uri, source_detail, position)

    def relationships(self, object_id: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT * FROM knowledge_relationships WHERE from_id = ? OR to_id = ?
               ORDER BY created_at, id""", (object_id, object_id)
        ).fetchall()

    def update_relationship(self, relationship_id, *, kind=None, evidence=None, source_uri=None, source_detail=None) -> None:
        relationship_id = _require_name(relationship_id, "Relationship identifier")
        with _transaction(self._connection):
            row = self._connection.execute("SELECT * FROM knowledge_relationships WHERE id = ?", (relationship_id,)).fetchone()
            if row is None:
                raise ValueError("The connection no longer exists.")
            kind = row["type"] if kind is None else _require_name(kind, "Connection type", 80)
            if kind == "scripture_reference":
                raise ValueError("Scripture note attachments are managed by note history.")
            if self._connection.execute("SELECT 1 FROM relationship_types WHERE code = ?", (kind,)).fetchone() is None:
                raise ValueError("Unknown connection type.")
            evidence = row["evidence"] if evidence is None else _require_text(evidence, "Relationship evidence")
            material = (kind, evidence, source_uri, source_detail) != (row["type"], row["evidence"], row["source_uri"], row["source_detail"])
            self._connection.execute(f"UPDATE knowledge_relationships SET type=?, evidence=?, source_uri=?, source_detail=?, status=CASE WHEN ? THEN 'draft' ELSE status END, reviewed_by=CASE WHEN ? THEN NULL ELSE reviewed_by END, reviewed_at=CASE WHEN ? THEN NULL ELSE reviewed_at END, updated_at={NOW} WHERE id=?", (kind, evidence, source_uri, source_detail, material, material, material, relationship_id))

    def knowledge_connections(self, object_id: str) -> list[sqlite3.Row]:
        return self._connection.execute("""SELECT r.*, a1.verse_id AS from_verse, a2.verse_id AS to_verse,
            k1.title AS from_title, k2.title AS to_title
            FROM knowledge_relationships r
            JOIN knowledge_objects k1 ON k1.id=r.from_id JOIN knowledge_objects k2 ON k2.id=r.to_id
            LEFT JOIN scripture_anchors a1 ON a1.object_id=r.from_id LEFT JOIN scripture_anchors a2 ON a2.object_id=r.to_id
            WHERE r.from_id=? OR r.to_id=? ORDER BY r.created_at, r.id""", (object_id, object_id)).fetchall()

    def create_trace(self, title, description="", color="#8a402c", position=0) -> str:
        title = _require_name(title, "Trace name")
        description = _require_text(description, "Trace description")
        color = _require_name(color, "Trace colour", 20)
        _require_integer(position, "Trace position", 0)
        with _transaction(self._connection):
            object_id = self._insert_object("trace", title, description)
            self._connection.execute("INSERT INTO traces(object_id, description, color, position) VALUES (?,?,?,?)", (object_id, description, color, position))
            return object_id

    def traces(self):
        return self._connection.execute("SELECT k.id, k.title, t.description, t.color, t.position, k.status FROM traces t JOIN knowledge_objects k ON k.id=t.object_id ORDER BY t.position, k.title COLLATE NOCASE, k.id").fetchall()

    def update_trace(self, trace_id, title, description, color, position=0) -> None:
        title = _require_name(title, "Trace name"); description = _require_text(description, "Trace description"); color = _require_name(color, "Trace colour", 20); _require_integer(position, "Trace position", 0)
        with _transaction(self._connection):
            if self._connection.execute("SELECT 1 FROM traces WHERE object_id=?", (trace_id,)).fetchone() is None: raise ValueError("The trace no longer exists.")
            self._connection.execute(f"UPDATE knowledge_objects SET title=?, body=?, updated_at={NOW} WHERE id=?", (title, description, trace_id))
            self._connection.execute("UPDATE traces SET description=?, color=?, position=? WHERE object_id=?", (description, color, position, trace_id))

    def add_trace_member(self, trace_id, member_id, position=0) -> str:
        _require_integer(position, "Trace member position", 0)
        if self.knowledge_object(trace_id)["kind"] != "trace": raise ValueError("The source object is not a trace.")
        if self._connection.execute("SELECT 1 FROM knowledge_objects WHERE id=?", (member_id,)).fetchone() is None: raise ValueError("The trace member no longer exists.")
        return self.create_relationship(trace_id, member_id, "trace_member", position=position)

    def trace_members(self, trace_id):
        return self._connection.execute("""SELECT r.id AS relationship_id, r.position, r.status, k.id, k.kind, k.title,
            a.verse_id FROM knowledge_relationships r JOIN knowledge_objects k ON k.id=r.to_id
            LEFT JOIN scripture_anchors a ON a.object_id=k.id WHERE r.from_id=? AND r.type='trace_member' ORDER BY r.position, r.created_at""", (trace_id,)).fetchall()

    def create_study(self, title, summary="", observations="", questions="", interpretations="", conclusions="", folder_id=None, anchors=(), trace_ids=(), label_ids=None) -> str:
        title = _require_name(title, "Study title")
        fields = [_require_text(x, label) for x, label in ((summary,"Summary"),(observations,"Observations"),(questions,"Questions"),(interpretations,"Interpretations"),(conclusions,"Conclusions"))]
        label_ids = [] if label_ids is None else list(label_ids)
        with _transaction(self._connection):
            self._require_folder(folder_id)
            object_id = self._insert_object("study", title, "\n\n".join(x for x in fields if x))
            self._connection.execute("INSERT INTO notes(object_id, folder_id) VALUES (?,?)", (object_id, folder_id))
            self._connection.execute("INSERT INTO studies(object_id, summary, observations, questions, interpretations, conclusions) VALUES (?,?,?,?,?,?)", (object_id, *fields))
            anchor_ids = [self._anchor_id(anchor) for anchor in anchors]
            self._replace_note_anchors(object_id, anchor_ids)
            for trace_id in trace_ids: self._insert_relationship(object_id, trace_id, "study_related")
            self._replace_note_labels(object_id, label_ids)
            self._snapshot_note(object_id)
            return object_id

    def studies(self, folder_id=None):
        return self._connection.execute("""SELECT k.id, k.title, s.summary, n.folder_id, k.status, k.created_at, k.updated_at
            FROM studies s JOIN knowledge_objects k ON k.id=s.object_id JOIN notes n ON n.object_id=s.object_id
            WHERE n.folder_id IS ? ORDER BY k.updated_at DESC, k.title COLLATE NOCASE""", (folder_id,)).fetchall()

    def study(self, study_id):
        row = self._connection.execute("SELECT k.id,k.title,n.folder_id,k.status,k.created_at,k.updated_at,s.* FROM studies s JOIN knowledge_objects k ON k.id=s.object_id JOIN notes n ON n.object_id=s.object_id WHERE s.object_id=?", (study_id,)).fetchone()
        if row is None: raise ValueError("The study no longer exists.")
        return row

    def attach_file(self, object_id, path: str | Path) -> str:
        path = Path(path)
        if not path.is_file(): raise ValueError("The attachment file does not exist.")
        data = path.read_bytes(); digest = sha256(data).hexdigest()
        if self._connection.execute("SELECT 1 FROM knowledge_objects WHERE id=?", (object_id,)).fetchone() is None: raise ValueError("The research item no longer exists.")
        with _transaction(self._connection):
            existing = self._connection.execute("SELECT id FROM attachments WHERE object_id=? AND sha256=?", (object_id, digest)).fetchone()
            if existing: return existing["id"]
            attachment_id = uuid4().hex
            self._connection.execute("INSERT INTO attachments(id, object_id, filename, media_type, size, sha256, data) VALUES (?,?,?,?,?,?,?)", (attachment_id, object_id, path.name, _media_type(path), len(data), digest, data))
            return attachment_id

    def attachments(self, object_id):
        return self._connection.execute("SELECT id, object_id, filename, media_type, size, sha256, created_at FROM attachments WHERE object_id=? ORDER BY created_at, id", (object_id,)).fetchall()

    def attachment_data(self, attachment_id):
        row = self._connection.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
        if row is None: raise ValueError("The attachment no longer exists.")
        return row

    def delete_attachment(self, attachment_id):
        with _transaction(self._connection):
            self._connection.execute("DELETE FROM attachments WHERE id=?", (attachment_id,))

    def search_research(self, query, *, folder_id=None, label_id=None, status=None, kind=None):
        query = _require_text(query, "Search text").strip()
        like = f"%{query}%"
        return self._connection.execute("""SELECT DISTINCT k.id,k.kind,k.title,k.body,k.status,n.folder_id
            FROM knowledge_objects k LEFT JOIN notes n ON n.object_id=k.id
            LEFT JOIN note_labels nl ON nl.note_id=k.id
            WHERE (?='' OR k.title LIKE ? OR k.body LIKE ?)
              AND (? IS NULL OR n.folder_id IS ?)
              AND (? IS NULL OR nl.label_id IS ?)
              AND (? IS NULL OR k.status = ?)
              AND (? IS NULL OR k.kind = ?)
            ORDER BY k.updated_at DESC,k.title COLLATE NOCASE""", (query,like,like,folder_id,folder_id,label_id,label_id,status,status,kind,kind)).fetchall()

    def update_study(self, study_id, title, summary="", observations="", questions="", interpretations="", conclusions="") -> None:
        title = _require_name(title, "Study title")
        fields = [_require_text(x, label) for x, label in ((summary,"Summary"),(observations,"Observations"),(questions,"Questions"),(interpretations,"Interpretations"),(conclusions,"Conclusions"))]
        with _transaction(self._connection):
            current = self._connection.execute("SELECT k.title,k.status,s.* FROM studies s JOIN knowledge_objects k ON k.id=s.object_id WHERE s.object_id=?", (study_id,)).fetchone()
            if current is None: raise ValueError("The study no longer exists.")
            body = "\n\n".join(x for x in fields if x)
            material = (title, *fields) != (current["title"], current["summary"], current["observations"], current["questions"], current["interpretations"], current["conclusions"])
            self._connection.execute(f"UPDATE knowledge_objects SET title=?, body=?, status=CASE WHEN ? THEN 'draft' ELSE status END, reviewed_by=CASE WHEN ? THEN NULL ELSE reviewed_by END, reviewed_at=CASE WHEN ? THEN NULL ELSE reviewed_at END, updated_at={NOW} WHERE id=?", (title, body, material, material, material, study_id))
            self._connection.execute("UPDATE studies SET summary=?, observations=?, questions=?, interpretations=?, conclusions=? WHERE object_id=?", (*fields, study_id))
            self._snapshot_note(study_id)

    def review_knowledge(self, item_id, status, reviewer, reason, *, relationship=False) -> None:
        """Record an explicit user decision and apply it atomically to the item."""
        if status not in REVIEW_STATUSES:
            raise ValueError("Invalid research decision.")
        reviewer = _require_name(reviewer, "Reviewer")
        reason = _require_name(reason, "Research decision reason", 16_000)
        table = "knowledge_relationships" if relationship else "knowledge_objects"
        connection = self._connection
        with _transaction(connection):
            item = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
            if item is None:
                raise ValueError("The item to review no longer exists.")
            if relationship and item["type"] == "scripture_reference":
                raise ValueError("Scripture note attachments are managed by note revision history.")
            object_id, relationship_id = (None, item_id) if relationship else (item_id, None)
            connection.execute(
                """INSERT INTO knowledge_reviews(id, object_id, relationship_id, status, reviewer, reason)
                   VALUES (?, ?, ?, ?, ?, ?)""", (uuid4().hex, object_id, relationship_id, status, reviewer, reason)
            )

    # Bundle 06: explicit, user-controlled lenses, claims and contradiction records.
    def create_lens(self, name, description="", purpose=""):
        name = _require_name(name, "Lens name"); description = _require_text(description, "Lens description"); purpose = _require_text(purpose, "Lens purpose")
        with _transaction(self._connection):
            oid = self._insert_object("lens", name, description)
            self._connection.execute("INSERT INTO lenses(object_id,purpose) VALUES(?,?)", (oid, purpose))
            return oid

    def lenses(self, include_archived=False):
        return self._connection.execute("SELECT k.id,k.title,k.body,k.status,l.purpose,l.active,l.archived,k.created_at,k.updated_at FROM lenses l JOIN knowledge_objects k ON k.id=l.object_id WHERE (? OR l.archived=0) ORDER BY l.archived,l.active DESC,k.title COLLATE NOCASE", (include_archived,)).fetchall()

    def lens(self, lens_id):
        row = self._connection.execute("SELECT k.*,l.purpose,l.active,l.archived FROM lenses l JOIN knowledge_objects k ON k.id=l.object_id WHERE l.object_id=?", (lens_id,)).fetchone()
        if row is None: raise ValueError("The lens no longer exists.")
        return row

    def update_lens(self, lens_id, name, description="", purpose=""):
        name = _require_name(name, "Lens name"); description = _require_text(description, "Lens description"); purpose = _require_text(purpose, "Lens purpose")
        with _transaction(self._connection):
            old = self.lens(lens_id)
            material = (name, description, purpose) != (old["title"], old["body"], old["purpose"])
            self._connection.execute(f"UPDATE knowledge_objects SET title=?,body=?,status=CASE WHEN ? THEN 'draft' ELSE status END,reviewed_by=CASE WHEN ? THEN NULL ELSE reviewed_by END,reviewed_at=CASE WHEN ? THEN NULL ELSE reviewed_at END,updated_at={NOW} WHERE id=?", (name,description,material,material,material,lens_id))
            self._connection.execute("UPDATE lenses SET purpose=? WHERE object_id=?", (purpose,lens_id))

    def set_lens_active(self, lens_id, active=True):
        self.lens(lens_id)
        with _transaction(self._connection): self._connection.execute("UPDATE lenses SET active=? WHERE object_id=?", (int(bool(active)),lens_id))

    def archive_lens(self, lens_id, archived=True):
        self.lens(lens_id)
        with _transaction(self._connection): self._connection.execute("UPDATE lenses SET archived=?,active=CASE WHEN ? THEN 0 ELSE active END WHERE object_id=?", (int(bool(archived)),bool(archived),lens_id))

    def duplicate_lens(self, lens_id, name=None):
        source = self.lens(lens_id); new_id = self.create_lens(name or f"{source['title']} (copy)", source["body"], source["purpose"])
        for row in self.lens_assumptions(lens_id): self.create_lens_assumption(new_id, row["statement"], row["position"])
        return new_id

    def create_lens_assumption(self, lens_id, statement, position=0):
        self.lens(lens_id); statement = _require_name(statement, "Lens assumption", 4000); _require_integer(position, "Assumption position", 0)
        with _transaction(self._connection):
            aid = self._insert_object("lens_assumption", statement[:200], statement)
            self._connection.execute("INSERT INTO lens_assumptions(id,lens_id,statement,position) VALUES(?,?,?,?)", (aid,lens_id,statement,position))
            self._insert_relationship(lens_id, aid, "lens_assumption", position=position)
            return aid

    def lens_assumptions(self, lens_id):
        return self._connection.execute("SELECT la.*,k.status FROM lens_assumptions la JOIN knowledge_objects k ON k.id=la.id WHERE la.lens_id=? ORDER BY la.position,la.created_at", (lens_id,)).fetchall()

    def update_lens_assumption(self, assumption_id, statement):
        statement = _require_name(statement, "Lens assumption", 4000)
        with _transaction(self._connection):
            old = self._connection.execute("SELECT * FROM lens_assumptions WHERE id=?", (assumption_id,)).fetchone()
            if old is None: raise ValueError("The lens assumption no longer exists.")
            self._connection.execute("INSERT INTO lens_assumption_revisions(assumption_id,statement) VALUES(?,?)", (assumption_id,old["statement"]))
            self._connection.execute(f"UPDATE lens_assumptions SET statement=?,updated_at={NOW} WHERE id=?", (statement,assumption_id))
            self._connection.execute(f"UPDATE knowledge_objects SET title=?,body=?,status='draft',reviewed_by=NULL,reviewed_at=NULL,updated_at={NOW} WHERE id=?", (statement[:200],statement,assumption_id))

    def create_claim(self, statement, *, title=None, origin="user", source_detail=None):
        statement = _require_name(statement, "Claim", 8000)
        return self.create_knowledge_object("claim", title or statement[:200], statement, origin=origin, source_detail=source_detail)

    def claims(self):
        return self._connection.execute("SELECT * FROM knowledge_objects WHERE kind='claim' ORDER BY updated_at DESC").fetchall()

    def create_contradiction(self, claim_a_id, claim_b_id, classification, reasoning="", alternatives=""):
        allowed = {'supporting_evidence','challenging_evidence','interpretive_tension','possible_contradiction','demonstrated_incompatibility','unresolved_question','resolved_issue'}
        if classification not in allowed: raise ValueError("Invalid contradiction classification.")
        if claim_a_id == claim_b_id: raise ValueError("A claim cannot contradict itself.")
        for a,b in ((claim_a_id,claim_b_id),(claim_b_id,claim_a_id)):
            row=self._connection.execute("SELECT object_id FROM contradiction_records WHERE claim_a_id=? AND claim_b_id=?",(a,b)).fetchone()
            if row: return row["object_id"]
        self.knowledge_object(claim_a_id); self.knowledge_object(claim_b_id); reasoning=_require_text(reasoning,"Contradiction reasoning"); alternatives=_require_text(alternatives,"Alternatives")
        with _transaction(self._connection):
            oid=self._insert_object("contradiction", classification, reasoning)
            self._connection.execute("INSERT INTO contradiction_records(object_id,claim_a_id,claim_b_id,classification,alternatives) VALUES(?,?,?,?,?)",(oid,claim_a_id,claim_b_id,classification,alternatives))
            self._insert_relationship(claim_a_id,claim_b_id,"claim_conflict",reasoning)
            self._connection.execute("INSERT INTO contradiction_revisions(contradiction_id,classification,reasoning,alternatives) VALUES(?,?,?,?)",(oid,classification,reasoning,alternatives))
            return oid

    def contradictions(self):
        return self._connection.execute("SELECT c.*,k.title,k.body,k.status FROM contradiction_records c JOIN knowledge_objects k ON k.id=c.object_id ORDER BY k.updated_at DESC").fetchall()

    def update_contradiction(self, contradiction_id, classification, reasoning, alternatives=""):
        row=self._connection.execute("SELECT * FROM contradiction_records WHERE object_id=?",(contradiction_id,)).fetchone()
        if row is None: raise ValueError("The contradiction record no longer exists.")
        if classification not in {'supporting_evidence','challenging_evidence','interpretive_tension','possible_contradiction','demonstrated_incompatibility','unresolved_question','resolved_issue'}: raise ValueError("Invalid contradiction classification.")
        reasoning=_require_text(reasoning,"Contradiction reasoning"); alternatives=_require_text(alternatives,"Alternatives")
        with _transaction(self._connection):
            self._connection.execute("INSERT INTO contradiction_revisions(contradiction_id,classification,reasoning,alternatives) VALUES(?,?,?,?)",(contradiction_id,classification,reasoning,alternatives))
            self._connection.execute(f"UPDATE contradiction_records SET classification=?,alternatives=? WHERE object_id=?",(classification,alternatives,contradiction_id))
            self._connection.execute(f"UPDATE knowledge_objects SET title=?,body=?,status='draft',reviewed_by=NULL,reviewed_at=NULL,updated_at={NOW} WHERE id=?",(classification,reasoning,contradiction_id))

    def import_conversation(self, *, fingerprint, title, body, messages, source="local", source_date=None, metadata=None):
        fingerprint = _require_name(fingerprint, "Conversation fingerprint", 128); title = _require_text(title or "", "Conversation title"); body = _require_text(body, "Conversation text")
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with _transaction(self._connection):
            existing = self._connection.execute("SELECT id FROM conversations WHERE fingerprint=?", (fingerprint,)).fetchone()
            if existing: return existing["id"], False
            cid=uuid4().hex; self._connection.execute("INSERT INTO conversations(id,fingerprint,title,source,source_date,body,metadata) VALUES(?,?,?,?,?,?,?)",(cid,fingerprint,title,source,source_date,body,metadata_json))
            for ordinal, message in enumerate(messages):
                self._connection.execute("INSERT INTO conversation_messages(id,conversation_id,ordinal,speaker,body,source_id) VALUES(?,?,?,?,?,?)",(uuid4().hex,cid,ordinal,_require_name(message.get('speaker','unknown'), 'Speaker', 80),_require_text(message.get('body',''),'Message text'),_require_name(message.get('source_id',str(ordinal)), 'Message source', 200)))
            return cid, True

    def conversations(self):
        return self._connection.execute("SELECT * FROM conversations ORDER BY created_at DESC").fetchall()

    def conversation(self, conversation_id):
        row=self._connection.execute("SELECT * FROM conversations WHERE id=?",(conversation_id,)).fetchone()
        if row is None: raise ValueError("The conversation no longer exists.")
        return row

    def conversation_messages(self, conversation_id):
        return self._connection.execute("SELECT * FROM conversation_messages WHERE conversation_id=? ORDER BY ordinal",(conversation_id,)).fetchall()

    def create_conversation_proposal(self, *, conversation_id, message_id=None, kind, title, body, excerpt="", references=(), extraction_method="manual", model=None, status="draft", destination_folder_id=None):
        self.conversation(conversation_id); title=_require_name(title,"Proposal title"); body=_require_text(body,"Proposal text"); excerpt=_require_text(excerpt,"Proposal excerpt")
        if message_id:
            resolved=self._connection.execute("SELECT id FROM conversation_messages WHERE conversation_id=? AND (id=? OR source_id=?)",(conversation_id,message_id,message_id)).fetchone()
            message_id=resolved["id"] if resolved else None
        refs_json=json.dumps(list(references),ensure_ascii=False,sort_keys=True); fingerprint=sha256(json.dumps([kind,title,body,excerpt,list(references)],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        with _transaction(self._connection):
            existing=self._connection.execute("SELECT id FROM conversation_proposals WHERE conversation_id=? AND fingerprint=?",(conversation_id,fingerprint)).fetchone()
            if existing: return existing["id"]
            pid=uuid4().hex; self._connection.execute("INSERT INTO conversation_proposals(id,conversation_id,message_id,kind,title,body,excerpt,references_json,extraction_method,model,status,destination_folder_id,fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,conversation_id,message_id,kind,title,body,excerpt,refs_json,extraction_method,model,status,destination_folder_id,fingerprint)); return pid

    def conversation_proposals(self, conversation_id, status=None):
        if status is None: return self._connection.execute("SELECT * FROM conversation_proposals WHERE conversation_id=? ORDER BY rowid",(conversation_id,)).fetchall()
        return self._connection.execute("SELECT * FROM conversation_proposals WHERE conversation_id=? AND status=? ORDER BY rowid",(conversation_id,status)).fetchall()

    def review_conversation_proposal(self, proposal_id, status, reviewer="User", reason="Conversation review", *, title=None, body=None, folder_id=None):
        if status not in REVIEW_STATUSES: raise ValueError("Invalid research decision.")
        with _transaction(self._connection):
            row=self._connection.execute("SELECT * FROM conversation_proposals WHERE id=?",(proposal_id,)).fetchone()
            if row is None: raise ValueError("The conversation proposal no longer exists.")
            self._connection.execute("UPDATE conversation_proposals SET status=?,title=COALESCE(?,title),body=COALESCE(?,body),destination_folder_id=COALESCE(?,destination_folder_id) WHERE id=?",(status,title,body,folder_id,proposal_id))
            if status == "approved" and row["target_object_id"] is None:
                oid=self._insert_object(row["kind"] if row["kind"] in {"observation","question","interpretation","conclusion","concept"} else "observation", title or row["title"], body or row["body"], "ai", source_detail=json.dumps({"conversation_id":row["conversation_id"],"proposal_id":proposal_id,"excerpt":row["excerpt"]}))
                self._connection.execute("UPDATE conversation_proposals SET target_object_id=? WHERE id=?",(oid,proposal_id)); self._connection.execute("INSERT INTO knowledge_reviews(id,object_id,status,reviewer,reason) VALUES(?,?,?,?,?)",(uuid4().hex,oid,status,reviewer,reason))
            elif row["target_object_id"]:
                self._connection.execute("INSERT INTO knowledge_reviews(id,object_id,status,reviewer,reason) VALUES(?,?,?,?,?)",(uuid4().hex,row["target_object_id"],status,reviewer,reason))

    def scripture_anchor(self, anchor: ScriptureAnchor) -> str:
        """Return the reusable graph object ID for a Scripture reference or phrase."""
        with _transaction(self._connection):
            return self._anchor_id(anchor)

    def _anchor_id(self, anchor: ScriptureAnchor) -> str:
        if not isinstance(anchor, ScriptureAnchor) or not isinstance(anchor.book, str) or not BOOK_PATTERN.fullmatch(anchor.book):
            raise ValueError("Invalid Scripture anchor.")
        _require_integer(anchor.chapter, "Chapter number")
        _require_integer(anchor.verse, "Verse number")
        verse_id = f"{anchor.book}:{anchor.chapter}:{anchor.verse}"
        connection = self._connection
        if connection.execute("SELECT 1 FROM canonical_verses WHERE id = ?", (verse_id,)).fetchone() is None:
            raise ValueError(f"Scripture reference {anchor.book} {anchor.chapter}:{anchor.verse} is unavailable.")
        translation = None
        quote = None
        if anchor.translation is not None:
            edition_verse = connection.execute(
                """SELECT st.body, t.code FROM scripture_texts st JOIN translations t ON t.code = st.translation_code
                   WHERE t.code = ? AND st.verse_id = ? AND t.sealed_at IS NOT NULL""", (anchor.translation, verse_id)
            ).fetchone()
            if edition_verse is None:
                raise ValueError("The requested verse is unavailable in that translation.")
            translation = edition_verse["code"]
        if anchor.start is not None or anchor.end is not None:
            if translation is None:
                raise ValueError("A text selection must specify its Scripture translation.")
            start = _require_integer(anchor.start, "Selection start", 0)
            end = _require_integer(anchor.end, "Selection end")
            if start >= end or end > len(edition_verse["body"]):
                raise ValueError("The selection is outside the verse text.")
            quote = edition_verse["body"][start:end]
        existing = connection.execute(
            """SELECT object_id FROM scripture_anchors WHERE verse_id = ? AND translation_code IS ?
               AND start_offset IS ? AND end_offset IS ?""", (verse_id, translation, anchor.start, anchor.end)
        ).fetchone()
        if existing:
            return existing["object_id"]
        object_id = self._insert_object("scripture_anchor", f"{anchor.book} {anchor.chapter}:{anchor.verse}", "", "import")
        connection.execute(
            """INSERT INTO scripture_anchors(object_id, verse_id, translation_code, start_offset, end_offset, quote)
               VALUES (?, ?, ?, ?, ?, ?)""", (object_id, verse_id, translation, anchor.start, anchor.end, quote)
        )
        return object_id

    def notes(self, folder_id: str | None = None) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT k.id, k.title, k.body, n.folder_id, k.status, k.created_at, k.updated_at
               FROM notes n JOIN knowledge_objects k ON k.id = n.object_id
               WHERE n.folder_id IS ? ORDER BY k.updated_at DESC, k.title COLLATE NOCASE, k.id""", (folder_id,)
        ).fetchall()

    def note(self, note_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            """SELECT k.id, k.title, k.body, n.folder_id, k.status, k.created_at, k.updated_at
               FROM notes n JOIN knowledge_objects k ON k.id = n.object_id WHERE n.object_id = ?""", (note_id,)
        ).fetchone()
        if row is None:
            raise ValueError("The research note no longer exists.")
        return row

    def note_anchors(self, note_id: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT c.book_code AS book, c.number AS chapter, v.number AS verse,
                      a.translation_code AS translation, a.start_offset AS start, a.end_offset AS end, a.quote
               FROM knowledge_relationships r JOIN scripture_anchors a ON a.object_id = r.to_id
               JOIN canonical_verses v ON v.id = a.verse_id JOIN chapters c ON c.id = v.chapter_id
               WHERE r.from_id = ? AND r.type = 'scripture_reference' ORDER BY r.position""", (note_id,)
        ).fetchall()

    def _note_anchor_ids(self, note_id):
        rows = self._connection.execute(
            """SELECT to_id FROM knowledge_relationships
               WHERE from_id = ? AND type = 'scripture_reference' ORDER BY position""", (note_id,)
        )
        return [row[0] for row in rows]

    def _replace_note_anchors(self, note_id, anchor_ids) -> None:
        connection = self._connection
        existing = set(self._note_anchor_ids(note_id))
        connection.executemany(
            "DELETE FROM knowledge_relationships WHERE from_id = ? AND to_id = ? AND type = 'scripture_reference'",
            ((note_id, anchor_id) for anchor_id in existing.difference(anchor_ids)),
        )
        for position, anchor_id in enumerate(anchor_ids):
            if anchor_id in existing:
                connection.execute(
                    f"""UPDATE knowledge_relationships SET position = ?, updated_at = {NOW}
                        WHERE from_id = ? AND to_id = ? AND type = 'scripture_reference' AND position != ?""",
                    (position, note_id, anchor_id, position),
                )
            else:
                self._insert_relationship(note_id, anchor_id, "scripture_reference", position=position)

    def labels(self) -> list[sqlite3.Row]:
        return self._connection.execute("SELECT id, name, color FROM labels ORDER BY name_key, id").fetchall()

    def create_label(self, name: str, color="#8a402c") -> str:
        name = _require_name(name, "Label name", 80)
        key = _name_key(name)
        with _transaction(self._connection):
            existing = self._connection.execute("SELECT id FROM labels WHERE name_key = ?", (key,)).fetchone()
            if existing:
                return existing["id"]
            label_id = uuid4().hex
            self._connection.execute("INSERT INTO labels(id, name, name_key, color) VALUES (?, ?, ?, ?)", (label_id, name, key, _require_name(color, "Label colour", 20)))
            return label_id

    def update_label(self, label_id, name, color="#8a402c") -> None:
        name = _require_name(name, "Label name", 80); color = _require_name(color, "Label colour", 20)
        with _transaction(self._connection):
            if self._connection.execute("SELECT 1 FROM labels WHERE id=?", (label_id,)).fetchone() is None:
                raise ValueError("The label no longer exists.")
            self._connection.execute("UPDATE labels SET name=?, name_key=?, color=? WHERE id=?", (name, _name_key(name), color, label_id))

    def note_labels(self, note_id: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT l.id, l.name FROM note_labels nl JOIN labels l ON l.id = nl.label_id
               WHERE nl.note_id = ? ORDER BY l.name_key, l.id""", (note_id,)
        ).fetchall()

    def _replace_note_labels(self, note_id, label_ids) -> None:
        connection = self._connection
        connection.execute("DELETE FROM note_labels WHERE note_id = ?", (note_id,))
        connection.executemany(
            "INSERT INTO note_labels(note_id, label_id) VALUES (?, ?)", ((note_id, label_id) for label_id in label_ids)
        )

    def set_note_labels(self, note_id: str, label_ids) -> None:
        with _transaction(self._connection):
            current = self.note(note_id)
            self._update_note(current, current["title"], current["body"], current["folder_id"], None, set(label_ids))

    def _snapshot_note(self, note_id: str) -> None:
        connection = self._connection
        result = connection.execute(
            """INSERT INTO note_revisions(note_id, title, body, folder_id, folder_name, summary, observations, questions, interpretations, conclusions)
               SELECT n.object_id, k.title, k.body, n.folder_id, f.name,
                      COALESCE(s.summary,''), COALESCE(s.observations,''), COALESCE(s.questions,''),
                      COALESCE(s.interpretations,''), COALESCE(s.conclusions,'')
               FROM notes n JOIN knowledge_objects k ON k.id = n.object_id
               LEFT JOIN folders f ON f.id = n.folder_id LEFT JOIN studies s ON s.object_id = n.object_id WHERE n.object_id = ?""", (note_id,)
        )
        connection.execute(
            """INSERT INTO revision_anchors(revision_id, anchor_id, position)
               SELECT ?, to_id, position FROM knowledge_relationships
               WHERE from_id = ? AND type = 'scripture_reference'""", (result.lastrowid, note_id)
        )
        connection.execute(
            """INSERT INTO revision_labels(revision_id, label_id)
               SELECT ?, label_id FROM note_labels WHERE note_id = ?""", (result.lastrowid, note_id)
        )

    def _touch_note(self, note_id):
        self._connection.execute(f"UPDATE knowledge_objects SET updated_at = {NOW} WHERE id = ?", (note_id,))

    def create_note(self, title: str, body: str, folder_id: str | None = None, anchors=(), *, label_ids=None) -> str:
        title = _require_name(title, "Note title")
        body = _require_text(body, "Note body")
        connection = self._connection
        with _transaction(connection):
            self._require_folder(folder_id)
            note_id = self._insert_object("note", title, body)
            connection.execute("INSERT INTO notes(object_id, folder_id) VALUES (?, ?)", (note_id, folder_id))
            self._replace_note_anchors(note_id, list(dict.fromkeys(self._anchor_id(anchor) for anchor in anchors)))
            if label_ids is not None:
                self._replace_note_labels(note_id, set(label_ids))
            self._snapshot_note(note_id)
        return note_id

    def _update_note(self, current, title, body, folder_id, anchor_ids, label_ids) -> None:
        note_id = current["id"]
        content_changed = (title, body) != (current["title"], current["body"])
        folder_changed = folder_id != current["folder_id"]
        anchors_changed = anchor_ids is not None and anchor_ids != self._note_anchor_ids(note_id)
        labels_changed = label_ids is not None and label_ids != {label["id"] for label in self.note_labels(note_id)}
        if not (content_changed or anchors_changed or labels_changed or folder_changed):
            return
        if content_changed or anchors_changed:
            # The review journal retains its decisions when a note is revised into a draft.
            self._connection.execute(
                f"""UPDATE knowledge_objects SET title = ?, body = ?, updated_at = {NOW},
                        status = 'draft', reviewed_by = NULL, reviewed_at = NULL WHERE id = ?""", (title, body, note_id)
            )
        else:
            self._touch_note(note_id)
        if folder_changed:
            self._connection.execute("UPDATE notes SET folder_id = ? WHERE object_id = ?", (folder_id, note_id))
        if anchors_changed:
            self._replace_note_anchors(note_id, anchor_ids)
        if labels_changed:
            self._replace_note_labels(note_id, label_ids)
        self._snapshot_note(note_id)

    def update_note(self, note_id: str, title: str, body: str, folder_id=KEEP_FOLDER, anchors=None, *, label_ids=None) -> str:
        title = _require_name(title, "Note title")
        body = _require_text(body, "Note body")
        with _transaction(self._connection):
            current = self.note(note_id)
            if folder_id is KEEP_FOLDER:
                folder_id = current["folder_id"]
            self._require_folder(folder_id)
            anchor_ids = None if anchors is None else list(dict.fromkeys(self._anchor_id(anchor) for anchor in anchors))
            self._update_note(current, title, body, folder_id, anchor_ids, None if label_ids is None else set(label_ids))
        return note_id

    def note_revisions(self, note_id: str) -> list[sqlite3.Row]:
        return self._connection.execute(
            """SELECT id, title, body, folder_id, folder_name, summary, observations, questions, interpretations, conclusions, created_at FROM note_revisions
               WHERE note_id = ? ORDER BY id DESC""", (note_id,)
        ).fetchall()

    def restore_note_revision(self, note_id: str, revision_id: int) -> None:
        connection = self._connection
        with _transaction(connection):
            current = self.note(note_id)
            revision = connection.execute(
                "SELECT * FROM note_revisions WHERE id = ? AND note_id = ?", (revision_id, note_id)
            ).fetchone()
            if revision is None:
                raise ValueError("The requested note version does not exist.")
            folder_id = revision["folder_id"]
            if not connection.execute("SELECT 1 FROM folders WHERE id = ?", (folder_id,)).fetchone():
                folder_id = None
            anchor_ids = [row[0] for row in connection.execute(
                "SELECT anchor_id FROM revision_anchors WHERE revision_id = ? ORDER BY position", (revision_id,)
            )]
            label_ids = {row[0] for row in connection.execute(
                "SELECT label_id FROM revision_labels WHERE revision_id = ?", (revision_id,)
            )}
            if connection.execute("SELECT 1 FROM studies WHERE object_id=?", (note_id,)).fetchone():
                connection.execute("UPDATE studies SET summary=?, observations=?, questions=?, interpretations=?, conclusions=? WHERE object_id=?", (revision["summary"], revision["observations"], revision["questions"], revision["interpretations"], revision["conclusions"], note_id))
            self._update_note(current, revision["title"], revision["body"], folder_id, anchor_ids, label_ids)

    def _other_database_path(self, path) -> Path:
        path = Path(path).expanduser().resolve()
        if path == self.path or (path.exists() and path.samefile(self.path)):
            raise ValueError("Choose a different file from the active Bible Brain database.")
        if path in self._sqlite_sidecars(self.path):
            raise ValueError("Choose a different file from the active database's SQLite journals.")
        return path

    @staticmethod
    def _sqlite_sidecars(path: Path) -> tuple[Path, ...]:
        return tuple(path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal"))

    @staticmethod
    def _copy_database(source: sqlite3.Connection, destination: sqlite3.Connection) -> None:
        first_busy_at = None

        def monitor(status, _remaining, _total):
            nonlocal first_busy_at
            if status not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                first_busy_at = None
                return
            current_time = monotonic()
            if first_busy_at is None:
                first_busy_at = current_time
            if current_time - first_busy_at >= BACKUP_BUSY_SECONDS:
                raise ValueError("SQLite is busy. Close other tools using the database and try again.")

        source.backup(destination, pages=256, progress=monitor)

    @classmethod
    def _snapshot_database(cls, source: sqlite3.Connection, path: Path) -> None:
        with closing(sqlite3.connect(path, isolation_level=None)) as destination:
            _configure(destination)
            cls._copy_database(source, destination)
            _verify_database(destination)

    def backup_to(self, path: str | Path) -> Path:
        """Write and verify a standalone snapshot before replacing the chosen destination."""
        path = self._other_database_path(path)
        with _database_ownership(path), _temporary_database(path.parent) as temporary:
            if any(journal.exists() for journal in self._sqlite_sidecars(path)):
                raise ValueError("The backup destination has SQLite journal files. Choose another file.")
            self._snapshot_database(self._connection, temporary)
            os.replace(temporary, path)
        log.info("Created a verified database backup")
        return path

    def restore_from(self, path: str | Path) -> Path:
        """Verify a selected snapshot and replace the contents over the live SQLite connection."""
        source = self._other_database_path(path)
        if not source.is_file():
            raise ValueError("The backup file does not exist.")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        previous = self.path.with_name(f"{self.path.stem}.before-restore-{timestamp}-{uuid4().hex[:8]}.sqlite3")
        with _temporary_database(self.path.parent) as staged:
            with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, isolation_level=None)) as original:
                _configure(original)
                self._snapshot_database(original, staged)
            self.backup_to(previous)
            with closing(sqlite3.connect(staged, isolation_level=None)) as replacement:
                self._copy_database(replacement, self._connection)
        self.check_integrity()
        log.info("Restored verified database; retained the previous database as a backup")
        return previous
