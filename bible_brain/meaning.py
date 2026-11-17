"""Local-first Meaning Engine: retrieval, provider adapters and proposal safety."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Protocol
from urllib import request, error

from .database import ScriptureAnchor


@dataclass(frozen=True)
class EvidenceItem:
    source_id: str
    kind: str
    title: str
    text: str
    status: str = "source"
    reference: str | None = None


@dataclass(frozen=True)
class Investigation:
    question: str
    answer: str
    observations: str
    interpretation: str
    challenges: str
    unresolved: str
    evidence: tuple[EvidenceItem, ...]
    model: str


class AIProvider(Protocol):
    name: str
    def models(self) -> list[str]: ...
    def complete(self, prompt: str, model: str, timeout: float = 60) -> str: ...


class OllamaProvider:
    name = "Ollama"
    def __init__(self, base_url="http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")

    def models(self) -> list[str]:
        try:
            with request.urlopen(request.Request(self.base_url + "/api/tags"), timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [row["name"] for row in payload.get("models", []) if isinstance(row, dict) and row.get("name")]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def complete(self, prompt: str, model: str, timeout: float = 60) -> str:
        body = json.dumps({
            "model": model,
            "stream": False,
            "messages": [{"role": "system", "content": "You are a careful Bible research assistant. Never invent Scripture or citations. Return JSON only."}, {"role": "user", "content": prompt}],
            "options": {"temperature": 0.2},
        }).encode("utf-8")
        try:
            with request.urlopen(request.Request(self.base_url + "/api/chat", data=body, headers={"Content-Type": "application/json"}), timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload["message"]["content"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("Ollama is unavailable or returned an invalid response.") from exc


class MockProvider:
    name = "Deterministic test provider"
    def models(self): return ["mock-research"]
    def complete(self, prompt: str, model: str, timeout: float = 60) -> str:
        refs = re.findall(r"\b[A-Z0-9]{3} \d+:\d+\b", prompt)
        refs = list(dict.fromkeys(refs))[:4]
        return json.dumps({
            "answer": "The retrieved passages should be compared as a provisional research pattern, not as a settled conclusion.",
            "observations": "The selected passage and its retrieved sources are listed below.",
            "interpretation": "A possible connection is present, but it remains a hypothesis requiring user review.",
            "challenges": "The retrieved evidence may reflect different literary settings or textual traditions.",
            "unresolved": "What additional context or original-language evidence would strengthen the claim?",
            "citations": refs,
        })


class ContextRetriever:
    def __init__(self, database):
        self.database = database

    def retrieve(self, anchors=(), trace_id=None, query="", limit=24) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        seen: set[str] = set()
        def add(item):
            if item.source_id not in seen and len(evidence) < limit:
                evidence.append(item); seen.add(item.source_id)
        for anchor in anchors:
            rows = self.database.verses(anchor.translation or "WEBP", anchor.book, anchor.chapter)
            for row in rows:
                if row["number"] == anchor.verse:
                    add(EvidenceItem(row["id"], "scripture", row["id"], row["text"], "scripture", f"{anchor.book} {anchor.chapter}:{anchor.verse}"))
            for token in self.database.original_tokens(anchor.book, anchor.chapter, anchor.verse):
                add(EvidenceItem(token["id"], "original_language", token["strongs"], f"{token['surface']} · {token['lemma']} · {token['dictionary_definition']}", "lexical", f"{anchor.book} {anchor.chapter}:{anchor.verse}"))
            try:
                anchor_id = self.database.scripture_anchor(anchor)
                for rel in self.database.knowledge_connections(anchor_id):
                    if rel["status"] in {"rejected", "parked"}: continue
                    other = rel["to_verse"] if rel["from_id"] == anchor_id else rel["from_verse"]
                    add(EvidenceItem(rel["id"], "connection", rel["type"], rel["evidence"] or rel["type"], rel["status"], other))
            except Exception:
                pass
        if trace_id:
            for row in self.database.trace_members(trace_id):
                if row["status"] in {"rejected", "parked"}: continue
                add(EvidenceItem(row["id"], "trace_member", row["title"], row["verse_id"] or row["title"], row["status"], row["verse_id"]))
        if query.strip():
            for row in self.database.search_research(query):
                if row["status"] in {"rejected", "parked"}: continue
                add(EvidenceItem(row["id"], row["kind"], row["title"], row["body"], row["status"], None))
        return evidence[:limit]


class MeaningEngine:
    def __init__(self, database, provider: AIProvider | None = None):
        self.database = database
        self.provider = provider or OllamaProvider()
        self.retriever = ContextRetriever(database)

    def investigate(self, question: str, anchors=(), trace_id=None, model="", timeout=60) -> Investigation:
        question = question.strip()
        if not question: raise ValueError("Ask a research question first.")
        evidence = self.retriever.retrieve(anchors, trace_id, question)
        if not model:
            models = self.provider.models()
            if not models: raise RuntimeError("No local AI model is available. Research retrieval remains available offline.")
            model = models[0]
        context = "\n".join(f"[{i.source_id}] {i.kind} {i.reference or ''}: {i.text} (status={i.status})" for i in evidence)
        prompt = f"Question: {question}\n\nEvidence:\n{context}\n\nReturn JSON keys answer, observations, interpretation, challenges, unresolved, citations. Citations must use only source IDs or references in the evidence."
        raw = self.provider.complete(prompt, model, timeout)
        try: payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc: raise RuntimeError("The AI returned malformed JSON; no research was saved.") from exc
        citations = payload.get("citations", [])
        allowed = {item.source_id for item in evidence} | {item.reference for item in evidence if item.reference}
        if not isinstance(citations, list) or any(citation not in allowed for citation in citations):
            raise RuntimeError("The AI returned an unverified citation; no research was saved.")
        return Investigation(question, str(payload.get("answer", "")), str(payload.get("observations", "")), str(payload.get("interpretation", "")), str(payload.get("challenges", "")), str(payload.get("unresolved", "")), tuple(evidence), model)

    def save_proposal(self, investigation: Investigation, *, status="investigate", folder_id=None) -> str:
        body = "\n\n".join(("Observations\n" + investigation.observations, "Interpretation\n" + investigation.interpretation, "Challenges\n" + investigation.challenges, "Unresolved\n" + investigation.unresolved))
        object_id = self.database.create_knowledge_object("interpretation", investigation.question, body, origin="ai", source_detail=json.dumps({"model": investigation.model, "evidence": [item.source_id for item in investigation.evidence]}))
        if status != "draft": self.database.review_knowledge(object_id, status, "User", "User decision from Meaning Engine")
        return object_id
