INSERT OR IGNORE INTO relationship_types(code, label) VALUES
    ('repeated_expression', 'Repeated word or expression'),
    ('direct_quotation', 'Direct quotation'),
    ('shared_symbol', 'Shared symbol'),
    ('thematic_parallel', 'Thematic parallel'),
    ('structural_parallel', 'Structural parallel'),
    ('possible_allusion', 'Possible allusion'),
    ('study_related', 'Related study');

CREATE TABLE traces (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    description TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#8a402c',
    position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0)
) STRICT;

CREATE TABLE studies (
    object_id TEXT PRIMARY KEY REFERENCES knowledge_objects(id),
    summary TEXT NOT NULL DEFAULT '',
    observations TEXT NOT NULL DEFAULT '',
    questions TEXT NOT NULL DEFAULT '',
    interpretations TEXT NOT NULL DEFAULT '',
    conclusions TEXT NOT NULL DEFAULT ''
) STRICT;
