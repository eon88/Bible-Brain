"""Read the offline translation interchange format shared by imports and bundled data."""

import gzip
import json
from pathlib import Path
import zlib

from .database import Database

_MAX_BYTES = 64 * 1024 * 1024
_STRING_FIELDS = ("code", "name", "language", "license", "source_url")
BUNDLED_WEB = Path(__file__).parent / "data" / "web.json.gz"


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
