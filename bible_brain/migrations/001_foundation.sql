CREATE TABLE translations (
    code TEXT PRIMARY KEY COLLATE NOCASE,
    name TEXT NOT NULL,
    language TEXT NOT NULL,
    license TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    sealed_at TEXT
) STRICT;

CREATE TABLE books (
    code TEXT PRIMARY KEY
) STRICT;

CREATE TABLE chapters (
    id TEXT PRIMARY KEY,
    book_code TEXT NOT NULL REFERENCES books(code),
    number INTEGER NOT NULL CHECK (number > 0),
    UNIQUE (book_code, number),
    CHECK (id = book_code || ':' || number)
) STRICT;

CREATE TABLE canonical_verses (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id),
    number INTEGER NOT NULL CHECK (number > 0),
    UNIQUE (chapter_id, number),
    CHECK (id = chapter_id || ':' || number)
) STRICT;

CREATE TABLE translation_books (
    translation_code TEXT NOT NULL COLLATE NOCASE REFERENCES translations(code),
    book_code TEXT NOT NULL REFERENCES books(code),
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL CHECK (sort_order > 0),
    PRIMARY KEY (translation_code, book_code),
    UNIQUE (translation_code, sort_order)
) STRICT;

CREATE TABLE scripture_texts (
    translation_code TEXT NOT NULL COLLATE NOCASE REFERENCES translations(code),
    verse_id TEXT NOT NULL REFERENCES canonical_verses(id),
    body TEXT NOT NULL,
    PRIMARY KEY (translation_code, verse_id)
) STRICT;

CREATE TRIGGER translation_insert_unsealed BEFORE INSERT ON translations
WHEN NEW.sealed_at IS NOT NULL OR EXISTS (SELECT 1 FROM translations WHERE code = NEW.code)
BEGIN SELECT RAISE(ABORT, 'Scripture translations can only be imported as new editions'); END;

CREATE TRIGGER translation_locked_update BEFORE UPDATE ON translations
WHEN OLD.sealed_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'Scripture translations are immutable'); END;

CREATE TRIGGER translation_locked_delete BEFORE DELETE ON translations
BEGIN SELECT RAISE(ABORT, 'Scripture translations are immutable'); END;

CREATE TRIGGER scripture_insert_open_edition BEFORE INSERT ON scripture_texts
WHEN NOT EXISTS (
    SELECT 1 FROM translations t
    JOIN translation_books tb ON tb.translation_code = t.code
    JOIN chapters c ON c.book_code = tb.book_code
    JOIN canonical_verses v ON v.chapter_id = c.id
    WHERE t.code = NEW.translation_code AND t.sealed_at IS NULL AND v.id = NEW.verse_id
)
BEGIN SELECT RAISE(ABORT, 'Scripture is immutable outside a new edition import'); END;

CREATE TRIGGER scripture_locked_update BEFORE UPDATE ON scripture_texts
BEGIN SELECT RAISE(ABORT, 'Scripture text is immutable'); END;

CREATE TRIGGER scripture_locked_delete BEFORE DELETE ON scripture_texts
BEGIN SELECT RAISE(ABORT, 'Scripture text is immutable'); END;

CREATE TRIGGER edition_book_insert_open_edition BEFORE INSERT ON translation_books
WHEN NOT EXISTS (SELECT 1 FROM translations WHERE code = NEW.translation_code AND sealed_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'Scripture books are immutable outside a new edition import'); END;

CREATE TRIGGER edition_book_locked_update BEFORE UPDATE ON translation_books
BEGIN SELECT RAISE(ABORT, 'Scripture books are immutable'); END;

CREATE TRIGGER edition_book_locked_delete BEFORE DELETE ON translation_books
BEGIN SELECT RAISE(ABORT, 'Scripture books are immutable'); END;

CREATE TRIGGER book_locked_update BEFORE UPDATE ON books
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TRIGGER book_locked_delete BEFORE DELETE ON books
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TRIGGER chapter_locked_update BEFORE UPDATE ON chapters
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TRIGGER chapter_locked_delete BEFORE DELETE ON chapters
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TRIGGER verse_locked_update BEFORE UPDATE ON canonical_verses
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TRIGGER verse_locked_delete BEFORE DELETE ON canonical_verses
BEGIN SELECT RAISE(ABORT, 'Scripture references are immutable'); END;

CREATE TABLE folders (
    id TEXT PRIMARY KEY,
    parent_id TEXT REFERENCES folders(id),
    name TEXT NOT NULL,
    name_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (id != parent_id)
) STRICT;

CREATE UNIQUE INDEX folder_name_scope ON folders(ifnull(parent_id, ''), name_key);

CREATE TRIGGER folders_block_cycle BEFORE UPDATE OF parent_id ON folders
WHEN NEW.parent_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'A folder cannot contain itself or an ancestor') WHERE EXISTS (
        WITH RECURSIVE lineage(id) AS (
            SELECT NEW.parent_id
            UNION
            SELECT f.parent_id FROM folders f JOIN lineage l ON l.id = f.id
            WHERE f.parent_id IS NOT NULL
        )
        SELECT 1 FROM lineage WHERE id = NEW.id
    );
END;

CREATE TABLE knowledge_objects (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('user', 'import', 'ai')),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'investigate', 'parked', 'rejected')),
    source_uri TEXT,
    source_detail TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (status = 'draft' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
) STRICT;

CREATE TRIGGER object_start_draft BEFORE INSERT ON knowledge_objects
WHEN NEW.status != 'draft' OR NEW.reviewed_by IS NOT NULL OR NEW.reviewed_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'Knowledge requires a separate user review decision'); END;

CREATE TABLE relationship_types (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL
) STRICT;

INSERT INTO relationship_types(code, label) VALUES
    ('scripture_reference', 'Scripture reference'),
    ('cross_reference', 'Cross-reference'),
    ('trace_member', 'Trace member'),
    ('study_citation', 'Study citation'),
    ('supports', 'Supports'),
    ('challenges', 'Challenges'),
    ('derived_from', 'Derived from'),
    ('attachment', 'Attachment');

CREATE TABLE knowledge_relationships (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL REFERENCES knowledge_objects(id),
    to_id TEXT NOT NULL REFERENCES knowledge_objects(id),
    type TEXT NOT NULL REFERENCES relationship_types(code),
    evidence TEXT NOT NULL DEFAULT '',
    source_uri TEXT,
    source_detail TEXT,
    origin TEXT NOT NULL CHECK (origin IN ('user', 'import', 'ai')),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'investigate', 'parked', 'rejected')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (from_id != to_id),
    CHECK (status = 'draft' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
    UNIQUE (from_id, type, to_id)
) STRICT;

CREATE INDEX relationships_inbound ON knowledge_relationships(to_id, type);

CREATE TRIGGER relationship_start_draft BEFORE INSERT ON knowledge_relationships
WHEN NEW.status != 'draft' OR NEW.reviewed_by IS NOT NULL OR NEW.reviewed_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'Knowledge requires a separate user review decision'); END;

CREATE TABLE knowledge_reviews (
    id TEXT PRIMARY KEY,
    object_id TEXT REFERENCES knowledge_objects(id),
    relationship_id TEXT REFERENCES knowledge_relationships(id),
    status TEXT NOT NULL CHECK (status IN ('approved', 'investigate', 'parked', 'rejected')),
    reviewer TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK ((object_id IS NOT NULL) != (relationship_id IS NOT NULL))
) STRICT;

CREATE INDEX reviews_by_object ON knowledge_reviews(object_id) WHERE object_id IS NOT NULL;
CREATE INDEX reviews_by_relationship ON knowledge_reviews(relationship_id) WHERE relationship_id IS NOT NULL;

CREATE TRIGGER object_review_required BEFORE UPDATE OF status, reviewed_by, reviewed_at ON knowledge_objects
WHEN NEW.status != 'draft' AND NOT EXISTS (
    SELECT 1 FROM knowledge_reviews WHERE object_id = NEW.id AND status = NEW.status
        AND reviewer = NEW.reviewed_by AND created_at = NEW.reviewed_at
)
BEGIN SELECT RAISE(ABORT, 'A research decision requires a user review record'); END;

CREATE TRIGGER relationship_review_required BEFORE UPDATE OF status, reviewed_by, reviewed_at ON knowledge_relationships
WHEN NEW.status != 'draft' AND NOT EXISTS (
    SELECT 1 FROM knowledge_reviews WHERE relationship_id = NEW.id AND status = NEW.status
        AND reviewer = NEW.reviewed_by AND created_at = NEW.reviewed_at
)
BEGIN SELECT RAISE(ABORT, 'A research decision requires a user review record'); END;

CREATE TRIGGER knowledge_reviews_apply AFTER INSERT ON knowledge_reviews
BEGIN
    UPDATE knowledge_objects
    SET status = NEW.status, reviewed_by = NEW.reviewer, reviewed_at = NEW.created_at, updated_at = NEW.created_at
    WHERE id = NEW.object_id;
    UPDATE knowledge_relationships
    SET status = NEW.status, reviewed_by = NEW.reviewer, reviewed_at = NEW.created_at, updated_at = NEW.created_at
    WHERE id = NEW.relationship_id;
END;

CREATE TRIGGER knowledge_reviews_locked_update BEFORE UPDATE ON knowledge_reviews
BEGIN SELECT RAISE(ABORT, 'Research decisions are preserved'); END;

CREATE TRIGGER knowledge_reviews_locked_delete BEFORE DELETE ON knowledge_reviews
BEGIN SELECT RAISE(ABORT, 'Research decisions are preserved'); END;

CREATE TABLE scripture_anchors (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    verse_id TEXT NOT NULL REFERENCES canonical_verses(id),
    translation_code TEXT COLLATE NOCASE,
    start_offset INTEGER,
    end_offset INTEGER,
    quote TEXT,
    FOREIGN KEY (translation_code, verse_id) REFERENCES scripture_texts(translation_code, verse_id),
    CHECK (
        (start_offset IS NULL AND end_offset IS NULL AND quote IS NULL)
        OR (translation_code IS NOT NULL AND start_offset IS NOT NULL AND end_offset IS NOT NULL
            AND start_offset >= 0 AND end_offset > start_offset AND quote IS NOT NULL
            AND length(quote) = end_offset - start_offset)
    )
) STRICT;

CREATE UNIQUE INDEX scripture_anchor_identity ON scripture_anchors(
    verse_id, ifnull(lower(translation_code), ''), ifnull(start_offset, -1), ifnull(end_offset, -1)
);

CREATE TRIGGER scripture_anchor_check_quote BEFORE INSERT ON scripture_anchors
WHEN NEW.start_offset IS NOT NULL AND NEW.quote != (
    SELECT substr(body, NEW.start_offset + 1, NEW.end_offset - NEW.start_offset)
    FROM scripture_texts WHERE translation_code = NEW.translation_code AND verse_id = NEW.verse_id
)
BEGIN SELECT RAISE(ABORT, 'Scripture selection must match its edition text'); END;

CREATE TRIGGER scripture_anchor_locked_update BEFORE UPDATE ON scripture_anchors
BEGIN SELECT RAISE(ABORT, 'A Scripture anchor is immutable'); END;

CREATE TRIGGER scripture_anchor_locked_delete BEFORE DELETE ON scripture_anchors
BEGIN SELECT RAISE(ABORT, 'A Scripture anchor is immutable'); END;

CREATE TABLE notes (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    folder_id TEXT REFERENCES folders(id)
) STRICT;

CREATE INDEX notes_by_folder ON notes(folder_id);

CREATE TABLE labels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE note_labels (
    note_id TEXT NOT NULL REFERENCES notes(object_id),
    label_id TEXT NOT NULL REFERENCES labels(id),
    PRIMARY KEY (note_id, label_id)
) STRICT;

CREATE TABLE note_revisions (
    id INTEGER PRIMARY KEY,
    note_id TEXT NOT NULL REFERENCES notes(object_id),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    folder_id TEXT,
    folder_name TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) STRICT;

CREATE INDEX revisions_by_note ON note_revisions(note_id, id DESC);

CREATE TABLE revision_anchors (
    revision_id INTEGER NOT NULL REFERENCES note_revisions(id),
    anchor_id TEXT NOT NULL REFERENCES scripture_anchors(object_id),
    position INTEGER NOT NULL CHECK (position >= 0),
    PRIMARY KEY (revision_id, anchor_id)
) STRICT;

CREATE TABLE revision_labels (
    revision_id INTEGER NOT NULL REFERENCES note_revisions(id),
    label_id TEXT NOT NULL REFERENCES labels(id),
    PRIMARY KEY (revision_id, label_id)
) STRICT;
