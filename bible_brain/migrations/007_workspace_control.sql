ALTER TABLE note_revisions ADD COLUMN summary TEXT NOT NULL DEFAULT '';
ALTER TABLE note_revisions ADD COLUMN observations TEXT NOT NULL DEFAULT '';
ALTER TABLE note_revisions ADD COLUMN questions TEXT NOT NULL DEFAULT '';
ALTER TABLE note_revisions ADD COLUMN interpretations TEXT NOT NULL DEFAULT '';
ALTER TABLE note_revisions ADD COLUMN conclusions TEXT NOT NULL DEFAULT '';
ALTER TABLE labels ADD COLUMN color TEXT NOT NULL DEFAULT '#8a402c';

CREATE TABLE attachments (
    id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL REFERENCES knowledge_objects(id),
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size INTEGER NOT NULL CHECK (size >= 0),
    sha256 TEXT NOT NULL,
    data BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(object_id, sha256)
) STRICT;
CREATE INDEX attachments_by_object ON attachments(object_id);
