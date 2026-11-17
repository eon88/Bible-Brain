CREATE TABLE language_resources (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    language TEXT NOT NULL CHECK (language IN ('he','el','arc')),
    name TEXT NOT NULL,
    license TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    sealed_at TEXT
) STRICT;

CREATE TABLE morphologies (
    language TEXT NOT NULL CHECK (language IN ('he','el','arc')),
    code TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    PRIMARY KEY (language, code)
) STRICT;

CREATE TABLE lexemes (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES language_resources(id),
    strongs TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('he','el','arc')),
    lemma TEXT NOT NULL,
    transliteration TEXT NOT NULL,
    dictionary_definition TEXT NOT NULL,
    UNIQUE(resource_id, strongs)
) STRICT;

CREATE TABLE original_tokens (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES language_resources(id),
    verse_id TEXT NOT NULL REFERENCES canonical_verses(id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    surface TEXT NOT NULL,
    lexeme_id TEXT NOT NULL REFERENCES lexemes(id),
    morphology_code TEXT,
    UNIQUE(resource_id, verse_id, ordinal)
) STRICT;

CREATE INDEX original_tokens_by_verse ON original_tokens(verse_id, ordinal);
CREATE INDEX lexemes_by_strongs ON lexemes(strongs);

CREATE TRIGGER language_resource_locked_update BEFORE UPDATE ON language_resources
WHEN OLD.sealed_at IS NOT NULL BEGIN SELECT RAISE(ABORT, 'Original-language resources are immutable'); END;
CREATE TRIGGER language_resource_locked_delete BEFORE DELETE ON language_resources
BEGIN SELECT RAISE(ABORT, 'Original-language resources are immutable'); END;
CREATE TRIGGER lexeme_locked_update BEFORE UPDATE ON lexemes
BEGIN SELECT RAISE(ABORT, 'Lexemes are immutable'); END;
CREATE TRIGGER lexeme_locked_delete BEFORE DELETE ON lexemes
BEGIN SELECT RAISE(ABORT, 'Lexemes are immutable'); END;
CREATE TRIGGER token_locked_update BEFORE UPDATE ON original_tokens
BEGIN SELECT RAISE(ABORT, 'Original-language tokens are immutable'); END;
CREATE TRIGGER token_locked_delete BEFORE DELETE ON original_tokens
BEGIN SELECT RAISE(ABORT, 'Original-language tokens are immutable'); END;
