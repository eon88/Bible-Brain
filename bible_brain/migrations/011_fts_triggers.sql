INSERT INTO research_fts(object_id,kind,title,body) SELECT id,kind,title,body FROM knowledge_objects WHERE id NOT IN (SELECT object_id FROM research_fts);
CREATE TRIGGER knowledge_fts_insert AFTER INSERT ON knowledge_objects BEGIN INSERT INTO research_fts(object_id,kind,title,body) VALUES (NEW.id,NEW.kind,NEW.title,NEW.body); END;
CREATE TRIGGER knowledge_fts_update AFTER UPDATE OF kind,title,body ON knowledge_objects BEGIN DELETE FROM research_fts WHERE object_id=OLD.id; INSERT INTO research_fts(object_id,kind,title,body) VALUES (NEW.id,NEW.kind,NEW.title,NEW.body); END;
CREATE TRIGGER knowledge_fts_delete AFTER DELETE ON knowledge_objects BEGIN DELETE FROM research_fts WHERE object_id=OLD.id; END;
