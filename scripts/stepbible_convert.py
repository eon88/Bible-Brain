"""Convert STEPBible tagged TSV/text exports into streamed .bb-lang packages.

The converter never combines editions: one invocation produces one resource code.
"""
from __future__ import annotations

import argparse, hashlib, json, re, zipfile
import gzip
from pathlib import Path

BOOKS = {"Gen":"GEN","Exo":"EXO","Lev":"LEV","Num":"NUM","Deu":"DEU","Jos":"JOS","Jdg":"JDG","Rut":"RUT","1Sa":"1SA","2Sa":"2SA","1Ki":"1KI","2Ki":"2KI","1Ch":"1CH","2Ch":"2CH","Ezr":"EZR","Neh":"NEH","Est":"EST","Job":"JOB","Psa":"PSA","Pro":"PRO","Ecc":"ECC","Sng":"SNG","Isa":"ISA","Jer":"JER","Lam":"LAM","Eze":"EZK","Dan":"DAN","Hos":"HOS","Joe":"JOL","Amo":"AMO","Oba":"OBA","Jon":"JON","Mic":"MIC","Nah":"NAM","Hab":"HAB","Zep":"ZEP","Hag":"HAG","Zec":"ZEC","Mal":"MAL","Mat":"MAT","Mar":"MRK","Luk":"LUK","Jhn":"JHN","Act":"ACT","Rom":"ROM","1Co":"1CO","2Co":"2CO","Gal":"GAL","Eph":"EPH","Php":"PHP","Col":"COL","1Th":"1TH","2Th":"2TH","1Ti":"1TI","2Ti":"2TI","Tit":"TIT","Phm":"PHM","Heb":"HEB","Jas":"JAS","1Pe":"1PE","2Pe":"2PE","1Jn":"1JN","2Jn":"2JN","3Jn":"3JN","Jud":"JUD","Rev":"REV"}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def lexemes(path: Path, language: str):
    with path.open(encoding='utf-8-sig', errors='strict') as f:
        for line in f:
            if not line.startswith(('G','H')): continue
            fields=line.rstrip('\n\r').split('\t')
            if len(fields)<8: continue
            strongs=fields[0].strip()
            if not re.fullmatch(r'[GH][0-9]{4}[A-Z]?', strongs): continue
            lemma=fields[3].strip()
            if not lemma: continue
            yield {'strongs':strongs, 'lemma':lemma, 'transliteration':fields[4].strip(), 'definition':re.sub('<[^>]+>',' ',fields[7]).strip()}

def morphologies(path: Path, language: str):
    with path.open(encoding='utf-8-sig', errors='strict') as f:
        for line in f:
            fields=line.rstrip('\n\r').split('\t')
            if len(fields)>=3 and fields[0].strip() and not fields[0].startswith('='):
                code=fields[0].strip()
                if ':' in code: yield {'code':code, 'label':fields[1].strip(), 'description':fields[2].strip()}

def tokens(paths, language: str):
    current=None; words=None
    for path in paths:
        with path.open(encoding='utf-8-sig', errors='strict') as f:
            for line in f:
                if line.startswith('# ') or line.startswith('#\t'):
                    ref=line[1:].strip().split('\t',1)[0]
                    m=re.match(r'([A-Za-z0-9]+)\.(\d+)\.(\d+)', ref)
                    if m:
                        current=(BOOKS.get(m.group(1)), int(m.group(2)), int(m.group(3)))
                        words=line.rstrip('\n\r').split('\t')[1:]
                    continue
                if not (line.startswith('#_Word=Grammar') or line.startswith('#_Word+Grammar')) or current is None: continue
                grammar=line.rstrip('\n\r').split('\t')[1:]
                if words is None: continue
                for ordinal,(surface,tag) in enumerate(zip(words,grammar)):
                    surface=surface.strip(); tag=tag.strip()
                    if not surface or not tag or '=' not in tag: continue
                    if language == 'arc' and not (current[0] == 'DAN' and ((current[1] == 2 and current[2] >= 4) or 3 <= current[1] <= 7)):
                        continue
                    strongs,morph=tag.split('=',1)
                    candidates=re.findall(r'[GH][0-9]{4}[A-Z]?', strongs)
                    strongs=next((x for x in reversed(candidates) if not x.startswith(('H900','G900'))), (candidates[-1] if candidates else None))
                    if not strongs: continue
                    yield {'book':current[0], 'chapter':current[1], 'verse':current[2], 'ordinal':ordinal, 'surface':surface, 'strongs':strongs, 'morphology':morph, 'variant':tag if ',' in tag or '/' in tag else ''}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--code', required=True); p.add_argument('--language', choices=['he','el','arc'], required=True); p.add_argument('--source-revision', default='STEPBible-Data@master')
    p.add_argument('--name', required=True); p.add_argument('--license', required=True); p.add_argument('--source-url', required=True)
    p.add_argument('--lexicon', action='append', type=Path, required=True); p.add_argument('--morphology', action='append', type=Path, default=[])
    p.add_argument('--tagged', action='append', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a=p.parse_args(); a.output.parent.mkdir(parents=True, exist_ok=True)
    lex=list({x['strongs']:x for f in a.lexicon for x in lexemes(f,a.language)}.values())
    strongs={x['strongs'] for x in lex}; toks=[]; skipped=[]
    bundled=Path(__file__).resolve().parents[1]/'bible_brain'/'data'/'web.json.gz'
    with gzip.open(bundled,'rt',encoding='utf-8') as f:
        canonical={f'{r[0]}:{r[3]}:{r[4]}' for r in json.load(f)['verses']}
    addresses={}
    for t in tokens(a.tagged,a.language):
        if t['book'] and t['strongs'] in strongs:
            key=(t['book'],t['chapter'],t['verse'],t['ordinal'])
            count=addresses.get(key,0); addresses[key]=count+1
            if count:
                t['variant']=(t['variant']+'|' if t['variant'] else '')+f"amalgamated-variant-{count+1}"
            if f"{t['book']}:{t['chapter']}:{t['verse']}" not in canonical:
                skipped.append({'book':t['book'],'chapter':t['chapter'],'verse':t['verse'],'reason':'not in bundled WEB versification'})
            else: toks.append(t)
    used={t['strongs'] for t in toks}; lex=[x for x in lex if x['strongs'] in used]
    if not lex or not toks: raise SystemExit('No valid lexemes or tokens found')
    manifest={'format':1,'code':a.code,'language':a.language,'name':a.name,'license':a.license,'source_url':a.source_url,'source_revision':a.source_revision,'source_files':[{'path':str(f),'sha256':sha256(f)} for f in [*a.lexicon,*a.morphology,*a.tagged]],'counts':{'lexemes':len(lex),'tokens':len(toks),'skipped_tokens':len(skipped)},'skipped_references':skipped}
    with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with z.open('lexemes.jsonl','w') as out:
            for row in lex: out.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
        with z.open('tokens.jsonl','w') as out:
            for row in toks: out.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
        with z.open('morphologies.jsonl','w') as out:
            for f in a.morphology:
                for row in morphologies(f,a.language): out.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
    print(a.output)

if __name__=='__main__': main()
