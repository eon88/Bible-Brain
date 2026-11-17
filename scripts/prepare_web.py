"""Convert the verified eBible.org WEBP archive into Bible Brain's seed file."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


ARCHIVE_SHA256 = "65793d2d56b0ba4cf54021fde3acfc4cfbd85bef25482727bcf9c55b4ec68924"
SOURCE_URL = "https://ebible.org/find/show.php?id=engwebp"
OUTPUT = Path(__file__).resolve().parents[1] / "bible_brain" / "data" / "web.json.gz"
BOOK_NAMES = {
    "GEN": "Genesis",
    "EXO": "Exodus",
    "LEV": "Leviticus",
    "NUM": "Numbers",
    "DEU": "Deuteronomy",
    "JOS": "Joshua",
    "JDG": "Judges",
    "RUT": "Ruth",
    "1SA": "1 Samuel",
    "2SA": "2 Samuel",
    "1KI": "1 Kings",
    "2KI": "2 Kings",
    "1CH": "1 Chronicles",
    "2CH": "2 Chronicles",
    "EZR": "Ezra",
    "NEH": "Nehemiah",
    "EST": "Esther",
    "JOB": "Job",
    "PSA": "Psalms",
    "PRO": "Proverbs",
    "ECC": "Ecclesiastes",
    "SNG": "Song of Solomon",
    "ISA": "Isaiah",
    "JER": "Jeremiah",
    "LAM": "Lamentations",
    "EZK": "Ezekiel",
    "DAN": "Daniel",
    "HOS": "Hosea",
    "JOL": "Joel",
    "AMO": "Amos",
    "OBA": "Obadiah",
    "JON": "Jonah",
    "MIC": "Micah",
    "NAM": "Nahum",
    "HAB": "Habakkuk",
    "ZEP": "Zephaniah",
    "HAG": "Haggai",
    "ZEC": "Zechariah",
    "MAL": "Malachi",
    "MAT": "Matthew",
    "MRK": "Mark",
    "LUK": "Luke",
    "JHN": "John",
    "ACT": "Acts",
    "ROM": "Romans",
    "1CO": "1 Corinthians",
    "2CO": "2 Corinthians",
    "GAL": "Galatians",
    "EPH": "Ephesians",
    "PHP": "Philippians",
    "COL": "Colossians",
    "1TH": "1 Thessalonians",
    "2TH": "2 Thessalonians",
    "1TI": "1 Timothy",
    "2TI": "2 Timothy",
    "TIT": "Titus",
    "PHM": "Philemon",
    "HEB": "Hebrews",
    "JAS": "James",
    "1PE": "1 Peter",
    "2PE": "2 Peter",
    "1JN": "1 John",
    "2JN": "2 John",
    "3JN": "3 John",
    "JUD": "Jude",
    "REV": "Revelation",
}
BOOK_ORDER = {code: position for position, code in enumerate(BOOK_NAMES, start=1)}


def read_verses(archive_data):
    digest = hashlib.sha256(archive_data).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"The supplied source is not the pinned WEBP archive (SHA-256 {digest}).")

    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        root = ET.fromstring(archive.read("engwebp_vpl.xml"))
        lines = archive.read("engwebp_vpl.txt").decode("utf-8-sig").splitlines()

    if root.tag != "verseFile":
        raise ValueError("Unexpected WEBP XML root element.")

    rows = []
    chapters = set()
    empty_references = set()
    previous_address = (0, 0, 0)
    for verse, line in zip(root, lines, strict=True):
        if verse.tag != "v" or len(verse) or set(verse.attrib) != {"b", "c", "v"}:
            raise ValueError("Unexpected WEBP verse element.")
        code = verse.attrib["b"]
        chapter = int(verse.attrib["c"])
        number = int(verse.attrib["v"])
        address = (BOOK_ORDER[code], chapter, number)
        if chapter < 1 or number < 1 or address <= previous_address:
            raise ValueError(f"Invalid or unsorted verse address for {code} {chapter}:{number}.")
        previous_address = address

        # The XML export uses USFM book codes and appends a separator space.
        # Verify its text against the plain-text export before writing a row.
        text = (verse.text or "").removesuffix(" ")
        _, reference, plain_text = line.split(" ", 2)
        if reference != f"{chapter}:{number}" or plain_text != text:
            raise ValueError(f"The source exports disagree at {code} {chapter}:{number}.")

        if not text:
            empty_references.add((code, chapter, number))
        chapters.add((code, chapter))
        rows.append([code, BOOK_NAMES[code], BOOK_ORDER[code], chapter, number, text])

    expected_empty = {("LUK", 17, 36), ("ACT", 8, 37), ("ACT", 15, 34), ("ACT", 24, 7), ("ROM", 16, 25)}
    if len({row[0] for row in rows}) != 66 or len(chapters) != 1189 or len(rows) != 31103:
        raise ValueError("Unexpected WEBP canon counts.")
    if empty_references != expected_empty:
        raise ValueError("Unexpected WEBP empty verse records.")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Local engwebp_vpl.zip from eBible.org")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    try:
        dataset = {
            "format": 1,
            "code": "WEBP",
            "name": "World English Bible (Protestant Edition)",
            "language": "en",
            "license": "Public domain",
            "source_url": SOURCE_URL,
            "verses": read_verses(args.archive.read_bytes()),
        }
        content = json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as target:
            with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
                compressed.write(content)
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        parser.exit(1, f"Could not prepare WEBP dataset. {error}\n")
    print(f"Wrote {len(dataset['verses']):,} verse records to {args.output}")


if __name__ == "__main__":
    main()
