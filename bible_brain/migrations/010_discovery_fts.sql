CREATE VIRTUAL TABLE research_fts USING fts5(object_id UNINDEXED, kind, title, body, tokenize='unicode61 remove_diacritics 0');
CREATE TABLE discovery_proposals (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, source_ids TEXT NOT NULL, limitations TEXT NOT NULL DEFAULT '', confidence TEXT NOT NULL DEFAULT 'unrated', status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','investigate','parked','rejected')), target_object_id TEXT REFERENCES knowledge_objects(id), fingerprint TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
