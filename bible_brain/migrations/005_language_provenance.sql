ALTER TABLE language_resources ADD COLUMN source_revision TEXT NOT NULL DEFAULT '';
ALTER TABLE language_resources ADD COLUMN source_manifest TEXT NOT NULL DEFAULT '[]';
