INSERT OR IGNORE INTO relationship_types(code, label) VALUES
 ('lens_assumption','Lens assumption'),('lens_supports','Lens supporting evidence'),
 ('lens_challenges','Lens challenging evidence'),('claim_supports','Claim supporting evidence'),
 ('claim_challenges','Claim challenging evidence'),('claim_conflict','Conflicting claims'),
 ('lens_related','Related lens');

CREATE TABLE lenses (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    purpose TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0,1)),
    archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0,1))
) STRICT;

CREATE TABLE lens_assumptions (
    id TEXT PRIMARY KEY,
    lens_id TEXT NOT NULL REFERENCES lenses(object_id),
    statement TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
CREATE TABLE lens_assumption_revisions (
    id INTEGER PRIMARY KEY,
    assumption_id TEXT NOT NULL REFERENCES lens_assumptions(id),
    statement TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;

CREATE TABLE contradiction_records (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    claim_a_id TEXT NOT NULL REFERENCES knowledge_objects(id),
    claim_b_id TEXT NOT NULL REFERENCES knowledge_objects(id),
    classification TEXT NOT NULL CHECK (classification IN ('supporting_evidence','challenging_evidence','interpretive_tension','possible_contradiction','demonstrated_incompatibility','unresolved_question','resolved_issue')),
    alternatives TEXT NOT NULL DEFAULT '',
    UNIQUE(claim_a_id, claim_b_id)
) STRICT;
CREATE TABLE contradiction_revisions (
    id INTEGER PRIMARY KEY,
    contradiction_id TEXT NOT NULL REFERENCES contradiction_records(object_id),
    classification TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    alternatives TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
) STRICT;
