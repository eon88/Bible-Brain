import tempfile
import unittest
from pathlib import Path

from bible_brain.database import ScriptureAnchor
from bible_brain.meaning import MeaningEngine, MockProvider
from bible_brain.session import Session


class MeaningEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.session = Session(Path(self.temp.name)); self.addCleanup(self.session.close)

    def test_mock_investigation_retrieves_citations_and_saves_pending_proposal(self):
        engine = MeaningEngine(self.session.database, MockProvider())
        result = engine.investigate("How does the passage connect to restoration?", [ScriptureAnchor("REV", 2, 7, "WEBP")], model="mock-research")
        self.assertTrue(result.evidence)
        self.assertIn("hypothesis", result.interpretation)
        object_id = engine.save_proposal(result, status="investigate")
        row = self.session.database.knowledge_object(object_id)
        self.assertEqual((row["kind"], row["status"], row["origin"]), ("interpretation", "investigate", "ai"))

    def test_malformed_or_unverified_provider_output_is_not_saved(self):
        class BadProvider(MockProvider):
            def complete(self, prompt, model, timeout=60):
                return '{"answer":"bad","citations":["GEN 99:99"]}'
        engine = MeaningEngine(self.session.database, BadProvider())
        with self.assertRaisesRegex(RuntimeError, "unverified citation"):
            engine.investigate("Question", [ScriptureAnchor("REV", 2, 7, "WEBP")], model="mock-research")

