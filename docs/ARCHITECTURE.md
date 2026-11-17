# Bible Brain architecture

## Bundle 01

## Bundle 03: Knowledge graph

Cross-references reuse `knowledge_relationships` between stable Scripture-anchor
objects. The relationship type records the user's classification and `evidence`,
`source_uri` and `source_detail` preserve the basis for the connection. A unique
`(from_id, type, to_id)` constraint plus the application-level idempotent insert
prevents accidental duplicates. Review decisions remain journaled in
`knowledge_reviews`; Keep maps to `approved`, while Investigate and Park remain
explicitly non-confirmatory states.

Traces are `knowledge_objects(kind='trace')` with a `traces` metadata row and ordered
`trace_member` edges. A trace can contain Scripture anchors, studies or any future
knowledge object, and a member may belong to multiple traces. The reader's Trace mode
uses the stable anchor IDs to highlight members in the active chapter; disabling the
mode removes those highlights.

Studies are `knowledge_objects(kind='study')` with a `studies` row containing summary,
observations, questions, interpretations and conclusions. They also use the existing
folder, label, anchor, revision and relationship infrastructure. Manual editing is
implemented; automated conversation processing and AI discovery are intentionally
deferred.

## Bundle 05: Meaning Engine

`meaning.py` separates retrieval from generation. `ContextRetriever` returns bounded,
source-ID-bearing evidence from Scripture, connections, traces, studies, notes and
original-language tokens. `OllamaProvider` is the initial local adapter and
`MockProvider` provides deterministic tests. Provider citations must match retrieved
IDs or verified Scripture references. An investigation remains an in-memory result
until the user explicitly saves it as an interpretation proposal; saving uses the
existing review workflow and never auto-approves content.

The Windows app runs a single Qt Widgets process. `window` and `reader` handle presentation. `session` manages local preferences, the active database, import and recovery. `datasets` validates the translation interchange envelope. `database` and its SQL migrations depend on the Python standard library and have no dependency on Qt. SQLite is the source of truth for Scripture and research. The application opens files directly and starts no HTTP server.

SQLite stores Scripture addresses as USFM book codes, `BOOK:chapter` chapter IDs and `BOOK:chapter:verse` verse IDs. An edition links its code to the shared verse address and its own immutable text. The import validates the whole translation, installs it atomically and seals the edition. A reimport of the same edition is idempotent. A different edition requires its own identifier. The same-address model supports Bundle 01 datasets with compatible verse numbering. A future versification mapping will be needed to align differently numbered, split or merged verses.

A note is a `knowledge_objects` record with a workspace row for folder membership. A Scripture link uses a reusable graph endpoint with an optional edition and half-open Unicode character offsets. The quoted text must match the immutable edition. The reader converts Qt's UTF-16 cursor positions to Unicode offsets. Folder names and paths are organizational metadata. Note, relationship and anchor IDs remain stable as folders move or are renamed. Revisions preserve note content and associated references so earlier work can be recovered.

The shared graph has typed relationships with evidence, source details, origin, review status and timestamps. Objects and relationships begin as drafts. An explicit review operation records the decision separately. Scripture text has its own immutable tables, while an interpretation and the evidence it cites use graph records. Bundle 01 exposes note editing, Scripture linking and revision recovery through the desktop UI.

Migrations are numbered SQL files. Database ownership and version are checked at open. SQLite enforces foreign keys and Scripture immutability. Backup uses SQLite's snapshot API, and restore validates a candidate before replacing the live contents. Restore first saves the current database as a recovery snapshot. Preferences and diagnostic logs live alongside the default database outside the executable and source repository. The database, including any backups you create, is readable by users with filesystem access to those files.

## Extension contracts

| Area | Proposed interface and storage |
| --- | --- |
| Original languages | A versioned local resource importer yields lexeme IDs, tokens, morphology and provenance. Attach tokens to `(edition, verse_id, ordinal)` and persist lexical/alignment tables referencing verse IDs. Edition-specific character spans remain available for alignment to translations. |
| Cross-references and Trace | Extend relationship types for quotation, allusion, motif and thematic links. Scripture anchors, trace objects, observations and evidence share endpoints. Edge position can order trace members. |
| Conversation capture and studies | Import a conversation as a sourced graph object. A capture adapter proposes study objects and edges carrying stable source references. Review records record each user decision. |
| Theological lenses and contradictions | Model lenses as collections of versioned assumption objects. Link claims to supporting, challenging or tension evidence with separate review state and review history. |
| Meaning Engine and retrieval | A retriever accepts passage IDs, optional lens IDs and explicit review filters, and returns cited evidence. A provider accepts that evidence and returns structured proposals with source IDs. Provider access is read-only. A local application service validates anchors and persists proposals as drafts through the graph API. Add FTS5 and semantic indexes as derived data. |
| Diagrams and media | A media repository returns content hashes and filesystem-relative blob keys. Link the resulting attachment object to a study and include managed files in a future backup format. |
| Android and sync | Reuse schema, migrations, dataset format and stable local IDs. Evaluate a touch-oriented Qt Quick client or an Android-native shell. Introduce a change journal with per-device IDs, tombstones and explicit conflict resolution before enabling sync. Qt's Python Android deployment tooling currently uses a Unix build host. [Qt for Python Android deployment](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-android-deploy.html) |
