ALTER TABLE original_tokens RENAME TO original_tokens_v3;
DROP INDEX original_tokens_by_verse;
CREATE TABLE original_tokens (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL REFERENCES language_resources(id),
    verse_id TEXT NOT NULL REFERENCES canonical_verses(id),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    surface TEXT NOT NULL,
    lexeme_id TEXT NOT NULL REFERENCES lexemes(id),
    morphology_code TEXT,
    textual_variant TEXT NOT NULL DEFAULT '',
    UNIQUE(resource_id, verse_id, ordinal, textual_variant)
) STRICT;
INSERT INTO original_tokens(id, resource_id, verse_id, ordinal, surface, lexeme_id, morphology_code, textual_variant)
SELECT id, resource_id, verse_id, ordinal, surface, lexeme_id, morphology_code, textual_variant FROM original_tokens_v3;
DROP TABLE original_tokens_v3;
CREATE INDEX original_tokens_by_verse ON original_tokens(verse_id, ordinal);
