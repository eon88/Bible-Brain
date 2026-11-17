"""Read the offline translation interchange format shared by imports and bundled data."""

import gzip
import json
from pathlib import Path
import zipfile
import zlib

from .database import Database

_MAX_BYTES = 64 * 1024 * 1024
_STRING_FIELDS = ("code", "name", "language", "license", "source_url")
BUNDLED_WEB = Path(__file__).parent / "data" / "web.json.gz"
_LANGUAGE_FIELDS = ("code", "language", "name", "license", "source_url")


def import_dataset(database: Database, path: Path) -> int:
    path = Path(path)
    if path.name.lower().endswith(".json.gz"):
        opener = gzip.open
    elif path.suffix.lower() == ".json":
        opener = open
    else:
        raise ValueError("Choose a Bible Brain JSON or JSON.gz translation file.")

    if path.stat().st_size > _MAX_BYTES:
        raise ValueError("The translation file exceeds 64 MiB.")
    try:
        with opener(path, "rb") as stream:
            content = stream.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise ValueError("The expanded translation file exceeds 64 MiB.")
        dataset = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError, gzip.BadGzipFile, EOFError, RecursionError, zlib.error) as error:
        raise ValueError("The translation file must contain valid UTF-8 JSON.") from error

    if not isinstance(dataset, dict) or type(dataset.get("format")) is not int or dataset["format"] != 1:
        raise ValueError("The translation file must use Bible Brain format version 1.")
    for field in _STRING_FIELDS:
        value = dataset.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"The translation file requires a non-empty '{field}' field.")

    verses = dataset.get("verses")
    if not isinstance(verses, list) or not verses:
        raise ValueError("The translation file requires a non-empty 'verses' list.")
    for index, verse in enumerate(verses, start=1):
        if (
            not isinstance(verse, list) or len(verse) != 6
            or not all(isinstance(verse[i], str) for i in (0, 1, 5))
            or not all(type(verse[i]) is int for i in (2, 3, 4))
        ):
            raise ValueError(f"Verse record {index} must specify book, name, order, chapter, verse and text.")

    return database.import_translation(
        **{field: dataset[field] for field in _STRING_FIELDS}, verses=verses,
    )


def import_original_language(database: Database, path: Path) -> int:
    """Import the versioned Bible Brain original-language JSON envelope.

    The envelope is intentionally independent from translation alignment. A token
    identifies a canonical verse and ordinal in its source-language edition; it
    never stores an English character offset.
    """
    path = Path(path)
    if path.suffix.lower() == ".bb-lang":
        try:
            with zipfile.ZipFile(path) as archive:
                resource = json.loads(archive.read("manifest.json").decode("utf-8"))
                resource["lexemes"] = [json.loads(line) for line in archive.read("lexemes.jsonl").decode("utf-8").splitlines() if line]
                resource["tokens"] = [json.loads(line) for line in archive.read("tokens.jsonl").decode("utf-8").splitlines() if line]
                resource["morphologies"] = [json.loads(line) for line in archive.read("morphologies.jsonl").decode("utf-8").splitlines() if line]
        except (OSError, KeyError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("The .bb-lang package is incomplete or invalid.") from error
        return _import_original_resource(database, resource)
    if path.suffix.lower() == ".gz" or path.name.lower().endswith(".json.gz"):
        opener = gzip.open
    elif path.suffix.lower() == ".json":
        opener = open
    else:
        raise ValueError("Choose a Bible Brain .bb-lang, JSON or JSON.gz original-language file.")
    try:
        with opener(path, "rb") as stream:
            content = stream.read(_MAX_BYTES + 1)
        if len(content) > _MAX_BYTES:
            raise ValueError("The original-language file exceeds 64 MiB expanded.")
        resource = json.loads(content.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError, gzip.BadGzipFile, EOFError, zlib.error) as error:
        raise ValueError("The original-language file must contain valid UTF-8 JSON.") from error
    return _import_original_resource(database, resource)


def _import_original_resource(database: Database, resource: dict) -> int:
    if not isinstance(resource, dict) or resource.get("format") != 1:
        raise ValueError("The original-language file must use format version 1.")
    for field in _LANGUAGE_FIELDS:
        if not isinstance(resource.get(field), str) or not resource[field].strip():
            raise ValueError(f"The original-language file requires '{field}'.")
    if resource["language"] not in {"he", "el", "arc"}:
        raise ValueError("Language must be he, el or arc.")
    for key in ("lexemes", "tokens"):
        if not isinstance(resource.get(key), list) or not resource[key]:
            raise ValueError(f"The original-language file requires a non-empty '{key}' list.")
    return database.import_original_language(
        **{field: resource[field] for field in _LANGUAGE_FIELDS},
        lexemes=resource["lexemes"], tokens=resource["tokens"],
        morphologies=resource.get("morphologies", []),
        source_revision=resource.get("source_revision", ""),
        source_manifest=resource.get("source_files", []),
    )
