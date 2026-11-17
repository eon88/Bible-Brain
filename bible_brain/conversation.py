"""Local conversation import and bounded, provenance-preserving extraction."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json, re
from pathlib import Path

BOOKS={"genesis":"GEN","exodus":"EXO","leviticus":"LEV","numbers":"NUM","deuteronomy":"DEU","joshua":"JOS","judges":"JDG","ruth":"RUT","isaiah":"ISA","jeremiah":"JER","ezekiel":"EZK","daniel":"DAN","matthew":"MAT","mark":"MRK","luke":"LUK","john":"JHN","acts":"ACT","romans":"ROM","revelation":"REV","galatians":"GAL","ephesians":"EPH","hebrews":"HEB","psalms":"PSA","proverbs":"PRO","gen":"GEN","rev":"REV","matt":"MAT","jn":"JHN"}
REF_RE=re.compile(r"\b([1-3]?\s?[A-Za-z][A-Za-z ]{1,18})\s+(\d{1,3}):(\d{1,3}(?:[-–]\d{1,3})?)")

@dataclass(frozen=True)
class ImportedConversation:
    title: str
    body: str
    messages: tuple[dict,...]
    source: str
    source_date: str|None
    metadata: dict
    fingerprint: str

def _messages_from_json(data):
    if isinstance(data, dict) and isinstance(data.get("mapping"), dict):
        rows=[]
        for node in data["mapping"].values():
            msg=node.get("message") or {}; content=msg.get("content") or {}; parts=content.get("parts") or []
            text="\n".join(str(p) for p in parts if isinstance(p,(str,int,float))).strip()
            if text: rows.append((msg.get("create_time") or 0, {"speaker":(msg.get("author") or {}).get("role","unknown"),"body":text,"source_id":node.get("id",str(len(rows)))}))
        return [r[1] for r in sorted(rows,key=lambda x:x[0])]
    raw=data.get("messages") if isinstance(data,dict) else data
    if isinstance(raw,list):
        out=[]
        for i,row in enumerate(raw):
            if isinstance(row,str): out.append({"speaker":"unknown","body":row,"source_id":str(i)})
            elif isinstance(row,dict):
                body=row.get("body",row.get("content",row.get("text",""))); speaker=row.get("speaker",row.get("role",(row.get("author") or {}).get("role","unknown")))
                if isinstance(body,list): body="\n".join(str(x) for x in body)
                if body: out.append({"speaker":str(speaker),"body":str(body),"source_id":str(row.get("id",i))})
        return out
    return []

def import_file(path: str|Path) -> ImportedConversation:
    path=Path(path); raw=path.read_text(encoding="utf-8-sig"); title=path.stem; metadata={}; source_date=None
    if path.suffix.lower()==".json":
        data=json.loads(raw); title=str(data.get("title") or data.get("name") or title) if isinstance(data,dict) else title; source_date=data.get("create_time") if isinstance(data,dict) else None; metadata={"format":"json"}; messages=_messages_from_json(data)
    else:
        metadata={"format":path.suffix.lower().lstrip(".") or "txt"}; messages=[]
        blocks=re.split(r"\n(?=(?:user|assistant|system|human)\s*:\s*)",raw,flags=re.I)
        for i,block in enumerate(blocks):
            m=re.match(r"\s*([\w -]+)\s*:\s*(.*)",block,re.S); messages.append({"speaker":m.group(1) if m else "unknown","body":m.group(2).strip() if m else block.strip(),"source_id":str(i)})
        if not any(m["body"] for m in messages): messages=[{"speaker":"unknown","body":raw,"source_id":"0"}]
    body="\n\n".join(f"{m['speaker']}: {m['body']}" for m in messages); fingerprint=sha256(body.encode("utf-8")).hexdigest()
    return ImportedConversation(title,body,tuple(messages),"local",source_date,metadata,fingerprint)

def extract_references(text, database=None):
    found=[]
    for match in REF_RE.finditer(text):
        name=re.sub(r"\s+"," ",match.group(1)).strip().lower(); code=BOOKS.get(name)
        if not code: continue
        chapter=int(match.group(2)); verse_text=match.group(3); verse=int(re.split("[-–]",verse_text)[0]); ref=f"{code} {chapter}:{verse}"
        valid=database is None or database._connection.execute("SELECT 1 FROM canonical_verses WHERE id=?",(f"{code}:{chapter}:{verse}",)).fetchone() is not None
        found.append({"reference":ref,"valid":valid,"raw":match.group(0)})
    return list({x["reference"]:x for x in found}.values())

def manual_extract(conversation, database):
    proposals=[]
    for message in conversation.messages:
        refs=extract_references(message["body"],database); body=message["body"].strip()
        if not body: continue
        kind="observation" if message["speaker"].lower() in {"user","human"} else "interpretation"
        proposals.append({"message_id":message["source_id"],"kind":kind,"title":body[:120],"body":body,"excerpt":body,"references":[x["reference"] for x in refs if x["valid"]],"extraction_method":"manual"})
    return proposals

def parse_ai_extraction(raw, conversation, database, model=""):
    payload=json.loads(raw)
    rows=payload.get("proposals",[]) if isinstance(payload,dict) else []
    out=[]
    for row in rows:
        if not isinstance(row,dict): continue
        refs=[]
        for ref in row.get("references",[]):
            refs.extend(x["reference"] for x in extract_references(str(ref),database) if x["valid"])
        out.append({"message_id":str(row.get("message_id","")),"kind":str(row.get("kind","observation")),"title":str(row.get("title","Untitled proposal"))[:200],"body":str(row.get("body","")),"excerpt":str(row.get("excerpt","")),"references":list(dict.fromkeys(refs)),"extraction_method":"ollama","model":model})
    return out

def analyze_conversation(conversation, database, provider, model, timeout=60, max_chars=18000):
    """Ask a local provider for bounded JSON proposals; caller persists only after review."""
    text=conversation.body[:max_chars]
    prompt=("Extract Bible-study proposals from this untrusted conversation. Preserve speaker distinctions and "
            "use only references actually present. Return JSON {proposals:[{message_id,kind,title,body,excerpt,references}]}. "
            "Kinds: observation, question, interpretation, conclusion, concept. Do not approve anything.\n\n"+text)
    raw=provider.complete(prompt,model,timeout)
    return parse_ai_extraction(raw,conversation,database,model)
