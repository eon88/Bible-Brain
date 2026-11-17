# Original languages

Bundle 02 stores original-language resources beside (not inside) translation text.
Each resource is sealed after an atomic import and records its source URL, licence and
content hash. Tokens point to stable canonical verse IDs plus a source ordinal. No
English character offsets or word-for-word alignment are stored.

## Licensed source evaluation

The primary source evaluated for Bundle 02 is [STEPBible-Data](https://github.com/STEPBible/STEPBible-Data),
curated by STEPBible and originally created at Tyndale House Cambridge. Its published
lexicons (TBESG Greek and TBESH Hebrew/Aramaic), morphology code tables (TEGMC and
TEHMC), and tagged Greek/Hebrew texts are available under CC BY 4.0. Bible Brain keeps
the source URL and attribution in every imported resource. The resource is not silently
downloaded; users import a verified file they have obtained from the publisher.

STEPBible's tagged files include multiple textual traditions and variants. A future
converter can normalize them into the Bible Brain envelope without treating a variant
as an English alignment. Aramaic is represented by the `arc` language code and may use
the relevant STEPBible Hebrew/Aramaic lexicon entries.

## Import envelope

Import a UTF-8 JSON/JSON.gz file or a streamed `.bb-lang` package from Settings → Import original-language resource. `.bb-lang` packages contain a manifest plus line-oriented lexeme, morphology and token files, so full STEPBible exports do not need to be represented as one oversized JSON document.

Convert a STEPBible export with:

```powershell
& .\.venv\Scripts\python.exe scripts\stepbible_convert.py `
  --code STEP-TAGNT-ACT-REV --language el `
  --name "STEPBible TAGNT Acts-Revelation" --license "CC BY 4.0" `
  --source-url "https://github.com/STEPBible/STEPBible-Data" `
  --lexicon .\TBESG.txt --morphology .\TEGMC.txt `
  --tagged .\TAGNT-Act-Rev.txt --output .\STEP-TAGNT-ACT-REV.bb-lang
```

The converter records SHA-256 checksums for every source file, a source revision,
counts, and any references omitted because the active Bible versification has no
matching canonical verse. Those omissions are reported in the package manifest rather
than merged into another textual tradition.

The Windows build bundles the verified Greek, Hebrew and Aramaic packages. A new
default local profile installs them on first launch, so original-language lookup is
available immediately after installation. Custom databases can install the same
packages from Settings.

```json
{
  "format": 1,
  "code": "STEP-TAGNT",
  "language": "el",
  "name": "STEP Bible tagged Greek",
  "license": "CC BY 4.0",
  "source_url": "https://github.com/STEPBible/STEPBible-Data",
  "morphologies": [{"code":"V","label":"Verb","description":"Verb form"}],
  "lexemes": [{"strongs":"G3056","lemma":"λόγος","transliteration":"logos","definition":"word; account"}],
  "tokens": [{"book":"JHN","chapter":1,"verse":1,"ordinal":0,"surface":"Λόγος","strongs":"G3056","morphology":"N"}]
}
```

Accepted languages are `he` (Hebrew), `el` (Greek) and `arc` (biblical Aramaic).
Strong's identifiers, lemma, transliteration, dictionary definition, morphology and
occurrence references are shown together when a selected verse has imported tokens.
Dictionary definitions are explicitly labelled; contextual conclusions belong in the
existing Research workspace and are never inferred or promoted automatically.
