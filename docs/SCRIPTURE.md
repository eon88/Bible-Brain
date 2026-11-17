# Scripture datasets

## Bundled World English Bible

Bible Brain includes the American English **World English Bible, Protestant Edition** (WEBP, publisher identifier `engwebp`). The publisher identifies this as the 2020 stable text edition. It contains 66 books, 1,189 chapters and 31,103 numbered verse records. [Publisher edition and downloads](https://ebible.org/find/show.php?id=engwebp)

The translation is in the public domain. “World English Bible” is a trademark of eBible.org. Use that name for unchanged World English Bible verse text and give any modified text a different name. [Publisher rights statement](https://ebible.org/study/content/texts/engwebp/about.html)

The archive’s XML provides the standard USFM book codes and verse addresses. The preparation script removes the XML’s single trailing separator space from each nonempty record and verifies the text against the archive’s plain-text export. Bible Brain preserves the publisher’s five empty records for Luke 17:36, Acts 8:37, 15:34 and 24:7, and Romans 16:25. Footnotes, paragraph formatting and headings require a richer source such as the publisher’s USFX export. [Official VPL archive](https://www.ebible.org/Scriptures/engwebp_vpl.zip)

## Reproducing the bundled file

Download `engwebp_vpl.zip` from eBible.org, then run the script from the repository root. [Official download](https://www.ebible.org/Scriptures/engwebp_vpl.zip)

```powershell
python scripts/prepare_web.py 'C:\path\to\engwebp_vpl.zip'
```

| File | SHA-256 |
| --- | --- |
| Official `engwebp_vpl.zip` | `65793d2d56b0ba4cf54021fde3acfc4cfbd85bef25482727bcf9c55b4ec68924` |
| `engwebp_vpl.xml` in the archive | `c61f0e46973b2c8a247c172a2c5e619cbaee022ae3647481360c452e908ca5e3` |
| `engwebp_vpl.txt` in the archive | `2d22ee66db074c801210dcd7091c8345e900faea52862c0022f2eff63b32bdda` |
| Generated `bible_brain/data/web.json.gz` | `c653e25b567f267e5021e9ddd8b1b345227d6ca64de611889f909ae591000cca` |

The archive URL may serve a newer publisher revision in the future. The script requires the pinned digest so a newer release cannot silently change the bundled text.

## Preparing a local import

Use a UTF-8 JSON or gzip-compressed JSON dataset that you have permission to use. The file and its expanded contents must each be at most 64 MiB. Include a format version, a stable translation code, a display name, a language code, licence information and a source URL. Each entry in `verses` contains the USFM book code, display name, book position, chapter number, verse number and publisher-supplied verse text.

```json
{
  "format": 1,
  "code": "WEBP",
  "name": "World English Bible (Protestant Edition)",
  "language": "en",
  "license": "Public domain",
  "source_url": "https://ebible.org/find/show.php?id=engwebp",
  "verses": [
    ["GEN", "Genesis", 1, 1, 1, "In the beginning, God created the heavens and the earth."]
  ]
}
```

The example illustrates a single record. Import the complete edition for ordinary reading. Use a distinct code for each edition so existing research anchors continue to resolve to their original verse text.
