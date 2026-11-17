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

Import a UTF-8 JSON or JSON.gz file from Settings → Import original-language resource:

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
