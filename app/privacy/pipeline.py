import hashlib, re, io, zipfile
from cryptography.fernet import Fernet
from app.config import settings
from app.domain.contracts import Span

EMAIL=re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
PHONE=re.compile(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)')
URL=re.compile(r'https?://\S+|www\.\S+', re.I)
SENSITIVE=re.compile(r'\b(name|address|gender|religion|caste|date of birth|marital|nationality|passport|aadhaar)\s*:',re.I)

def cipher():
    if not settings().identity_key: raise ValueError('IDENTITY_KEY_REQUIRED')
    return Fernet(settings().identity_key.encode())

def extract(data: bytes, filename: str):
    if len(data)>2_000_000: raise ValueError('DOCUMENT_TOO_LARGE')
    ext=filename.rsplit('.',1)[-1].lower()
    if ext=='txt': value=data.decode('utf-8-sig')
    elif ext=='pdf' and data.startswith(b'%PDF'):
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages)>20: raise ValueError('PDF_UNSUPPORTED')
        value='\n'.join(p.extract_text() or '' for p in reader.pages)
    elif ext=='docx' and data.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(x.file_size for x in z.infolist())>10_000_000: raise ValueError('DOCX_TOO_LARGE')
        from docx import Document
        doc=Document(io.BytesIO(data))
        value='\n'.join([p.text for p in doc.paragraphs]+[c.text for t in doc.tables for r in t.rows for c in r.cells])
    else: raise ValueError('UNSUPPORTED_DOCUMENT')
    if len(value.strip())<20: raise ValueError('OCR_OR_MANUAL_TRANSCRIPTION_REQUIRED')
    if len(value)>50000: raise ValueError('EXTRACTED_TEXT_TOO_LARGE')
    return value

def preview(text):
    lines=[]
    for line in text.splitlines():
        if SENSITIVE.search(line): continue
        lines.append(URL.sub('[URL]',PHONE.sub('[PHONE]',EMAIL.sub('[EMAIL]',line))))
    return '\n'.join(lines)

def ensure_safe(text):
    if EMAIL.search(text) or PHONE.search(text) or URL.search(text) or SENSITIVE.search(text):
        raise ValueError('PII_REQUIRES_REDACTION')
    return text

def document(text):
    ensure_safe(text)
    text=text.replace('\r\n','\n')
    spans=[]
    for m in re.finditer(r'[^\n]+',text):
        if m.group().strip():
            spans.append(Span(id=f'E{len(spans)+1}',start=m.start(),end=m.end(),excerpt=m.group(),sha256=hashlib.sha256(m.group().encode()).hexdigest()).model_dump())
    if len(spans)>200: raise ValueError('TOO_MANY_SPANS')
    return {'text':text,'revision':1,'sha256':hashlib.sha256(text.encode()).hexdigest(),'spans':spans}

def validate_refs(ids, doc):
    spans={s['id']:s for s in doc['spans']}
    for id in ids:
        if id not in spans: raise ValueError('UNGROUNDED_EVIDENCE')
        s=spans[id]
        if doc['text'][s['start']:s['end']]!=s['excerpt'] or hashlib.sha256(s['excerpt'].encode()).hexdigest()!=s['sha256']:
            raise ValueError('EVIDENCE_HASH_MISMATCH')
