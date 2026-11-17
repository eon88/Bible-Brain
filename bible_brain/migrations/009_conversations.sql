CREATE TABLE conversations (
 id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE, title TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'local', source_date TEXT, body TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
CREATE TABLE conversation_messages (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, ordinal INTEGER NOT NULL CHECK(ordinal>=0), speaker TEXT NOT NULL, body TEXT NOT NULL, source_id TEXT NOT NULL, UNIQUE(conversation_id,ordinal)
) STRICT;
CREATE TABLE conversation_proposals (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE, message_id TEXT REFERENCES conversation_messages(id), kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, excerpt TEXT NOT NULL DEFAULT '', references_json TEXT NOT NULL DEFAULT '[]', extraction_method TEXT NOT NULL DEFAULT 'manual', model TEXT, status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','investigate','parked','rejected')), destination_folder_id TEXT REFERENCES folders(id), target_object_id TEXT REFERENCES knowledge_objects(id), fingerprint TEXT NOT NULL, UNIQUE(conversation_id,fingerprint)
) STRICT;
CREATE INDEX conversation_proposal_status ON conversation_proposals(status);
