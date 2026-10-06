"""Bounded, selected local text/CSV documents, indexed per local project."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import uuid
from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
import memory
from document_extraction import ExtractRequest, extract_selected

router = APIRouter(prefix='/documents', tags=['Local documents'])
ProjectId = Annotated[str | None, Query(min_length=1, max_length=64, pattern=r'^[a-z0-9][a-z0-9_.-]*$')]
DocumentId = Annotated[str, Field(pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
MAX_DOCUMENTS = 30
MAX_CONTENT_CHARS = 100_000
MAX_CONTENT_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 512 * 1024

class DocumentBodyLimit:
    def __init__(self, app): self.app = app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in {'POST', 'PATCH'} or not scope.get('path','').startswith('/documents'):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            event = await receive()
            if event['type'] == 'http.disconnect': return
            chunk = event.get('body', b'')
            limit = 2*1024*1024 if scope.get('path','').rstrip('/') == '/documents/extract' else MAX_REQUEST_BYTES
            if len(body) + len(chunk) > limit:
                return await self.error(send, 413, 'document_request_too_large')
            body.extend(chunk)
            if not event.get('more_body', False): break
        try:
            json.loads(body, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite')))
        except (ValueError, UnicodeError, RecursionError):
            return await self.error(send, 422, 'invalid_document_json')
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type':'http.request', 'body':bytes(body), 'more_body':False}
            return await receive()
        await self.app(scope, replay, send)
    @staticmethod
    async def error(send, status, detail):
        await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json')]})
        await send({'type':'http.response.body','body':json.dumps({'detail':detail}).encode()})

class Review(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirmed: Literal[True]
    @field_validator('confirmed', mode='before')
    @classmethod
    def exact_confirmation(cls, value):
        if value is not True: raise ValueError('explicit_boolean_confirmation_required')
        return value

class Upload(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(min_length=1, max_length=120)
    kind: Literal['text','csv'] = 'text'
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)
    confirmed: Literal[True]
    validate_confirmation = field_validator('confirmed', mode='before')(Review.exact_confirmation.__func__)
    @field_validator('name')
    @classmethod
    def safe_name(cls, value):
        value = value.strip()
        if not value or any(char in value for char in '/\\\x00') or any(ord(char) < 32 for char in value):
            raise ValueError('display_filename_required_not_a_path')
        return value
    @field_validator('content')
    @classmethod
    def safe_text(cls, value):
        if not value.strip() or '\x00' in value or len(value.encode('utf-8')) > MAX_CONTENT_BYTES:
            raise ValueError('nonempty_bounded_utf8_text_required')
        return value

class Refresh(Upload):
    expected_revision: str = Field(pattern=r'^[0-9a-f]{64}$')

class Search(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str = Field(min_length=1, max_length=500)
    document_ids: list[DocumentId] = Field(min_length=1, max_length=5)
    limit: int = Field(default=5, ge=1, le=10)
    @field_validator('document_ids')
    @classmethod
    def unique(cls, value):
        if len({uuid.UUID(item) for item in value}) != len(value): raise ValueError('duplicate_document_id')
        return value

class Compare(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    document_ids: list[DocumentId] = Field(min_length=2, max_length=2)
    validate_unique = field_validator('document_ids')(Search.unique.__func__)


def ensure_document_schema():
    with memory.connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS local_documents (
                document_id UUID PRIMARY KEY, user_id UUID NOT NULL, name TEXT NOT NULL,
                kind TEXT NOT NULL, content TEXT NOT NULL, revision TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
            cur.execute('''CREATE TABLE IF NOT EXISTS local_document_chunks (
                document_id UUID NOT NULL REFERENCES local_documents(document_id) ON DELETE CASCADE,
                chunk_number INTEGER NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
                content TEXT NOT NULL, search_vector TSVECTOR NOT NULL,
                PRIMARY KEY (document_id, chunk_number))''')
            cur.execute('CREATE INDEX IF NOT EXISTS local_document_owner ON local_documents (user_id, updated_at DESC)')
            cur.execute('CREATE INDEX IF NOT EXISTS local_document_search ON local_document_chunks USING GIN (search_vector)')


def prepare(content: str, kind: str):
    # The original Unicode text is stored; CSV cells are only read, never evaluated.
    diagnostics = {'formula_like_cells':0}
    if kind == 'csv':
        try:
            rows = []
            for row in csv.reader(io.StringIO(content), strict=True):
                if len(rows) >= 1000 or len(row) > 50 or any(len(cell) > 4000 for cell in row):
                    raise ValueError('csv_limits_exceeded')
                diagnostics['formula_like_cells'] += sum(cell.lstrip().startswith(('=', '+', '-', '@')) for cell in row)
                rows.append(row)
            if not rows or not any(any(cell.strip() for cell in row) for row in rows): raise ValueError('empty_csv')
            diagnostics['rows'] = len(rows)
            diagnostics['max_columns'] = max(map(len, rows))
        except (csv.Error, ValueError):
            raise HTTPException(422, 'csv_must_be_valid_and_within_1000_rows_50_columns_4000_chars_per_cell') from None
    chunks = []
    offset = 0; line = 1
    while offset < len(content):
        end = min(offset + 1000, len(content))
        if end < len(content):
            candidate = content.rfind('\n', offset+200, end)
            if candidate < 0: candidate = content.rfind(' ', offset+200, end)
            if candidate >= 0: end = candidate + 1
        excerpt = content[offset:end]
        end_line = line + excerpt.count('\n')
        chunks.append((line, end_line, excerpt))
        line = end_line; offset = end
    if len(chunks) > 250: raise HTTPException(422, 'document_has_too_many_chunks')
    return chunks, diagnostics


def revision(document_id, upload):
    return hashlib.sha256(json.dumps([str(document_id),upload.name,upload.kind,upload.content], ensure_ascii=False).encode()).hexdigest()

def metadata(row):
    return {'id':str(row['document_id']), 'name':row['name'], 'kind':row['kind'],
            'revision':row['revision'], 'characters':len(row['content']),
            'created_at':row['created_at'].isoformat(), 'updated_at':row['updated_at'].isoformat()}

def index_chunks(cur, document_id, chunks):
    cur.executemany('''INSERT INTO local_document_chunks
        (document_id,chunk_number,start_line,end_line,content,search_vector)
        VALUES (%s,%s,%s,%s,%s,to_tsvector('simple',%s))''',
        [(document_id,number,start,end,text,text) for number,(start,end,text) in enumerate(chunks,1)])

def require_document(cur, document_id, owner, locked=False):
    cur.execute('SELECT * FROM local_documents WHERE document_id = %s AND user_id = %s' + (' FOR UPDATE' if locked else ''), (document_id,owner))
    row = cur.fetchone()
    if row is None: raise HTTPException(404, 'document_not_found_in_selected_project')
    return row

def unavailable(): return HTTPException(503, 'document_database_unavailable')

@router.get('')
def list_documents(project_id: ProjectId = None):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM local_documents WHERE user_id = %s ORDER BY updated_at DESC, document_id DESC LIMIT 30', (memory.local_memory_user(project_id),))
                rows = cur.fetchall()
        return {'documents':[metadata(row) for row in rows], 'project_id':project_id, 'authenticated':False}
    except Exception: raise unavailable() from None

@router.post('', status_code=201)
def upload_document(request: Upload, project_id: ProjectId = None):
    chunks, diagnostics = prepare(request.content, request.kind)
    owner = memory.local_memory_user(project_id); item = uuid.uuid4()
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('document-quota:' + str(owner),))
                cur.execute('SELECT count(*) AS count FROM local_documents WHERE user_id = %s', (owner,))
                if cur.fetchone()['count'] >= MAX_DOCUMENTS: raise HTTPException(409, 'project_document_limit_30')
                cur.execute('''INSERT INTO local_documents (document_id,user_id,name,kind,content,revision)
                    VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''', (item,owner,request.name,request.kind,request.content,revision(item,request)))
                row = cur.fetchone(); index_chunks(cur, item, chunks)
        return {'document':metadata(row), 'indexed_chunks':len(chunks), 'diagnostics':diagnostics}
    except HTTPException: raise
    except Exception: raise unavailable() from None

@router.post('/extract')
def extract_document(request: ExtractRequest, project_id: ProjectId = None):
    # Reading/extraction does not insert any row. The user reviews extracted text
    # and separately confirms its upload through the standard text controls.
    result = extract_selected(request)
    return {**result, 'project_id':project_id}

@router.post('/search')
def search_documents(request: Search, project_id: ProjectId = None):
    # Only indexed text in explicitly selected, owner-checked documents is searched.
    terms = list(dict.fromkeys(re.findall(r'[^\W_]+', request.query.lower())))[:20]
    terms = [term for term in terms if len(term)>1]
    if not terms: raise HTTPException(422, 'search_requires_word_or_number_keywords')
    query = ' | '.join("'" + term + "'" for term in terms)
    owner = memory.local_memory_user(project_id)
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                for item in request.document_ids: require_document(cur, uuid.UUID(item), owner)
                cur.execute('''SELECT d.document_id,d.name,d.revision,c.chunk_number,c.start_line,c.end_line,c.content,
                    ts_rank_cd(c.search_vector,to_tsquery('simple',%s)) AS score
                    FROM local_document_chunks c INNER JOIN local_documents d ON d.document_id=c.document_id
                    WHERE d.user_id=%s AND d.document_id=ANY(%s::uuid[]) AND c.search_vector @@ to_tsquery('simple',%s)
                    ORDER BY score DESC,d.document_id,c.chunk_number LIMIT %s''',
                    (query,owner,request.document_ids,query,request.limit))
                rows = cur.fetchall()
        return {'evidence':[{'document_id':str(row['document_id']), 'name':row['name'], 'revision':row['revision'],
            'chunk':row['chunk_number'], 'start_line':row['start_line'], 'end_line':row['end_line'],
            'excerpt':row['content'], 'score':float(row['score'])} for row in rows],
            'method':'local_keyword_search', 'selected_documents':request.document_ids}
    except HTTPException: raise
    except Exception: raise unavailable() from None

@router.post('/answer')
def extractive_answer(request: Search, project_id: ProjectId = None):
    result = search_documents(request, project_id)
    result['answer'] = '\n\n'.join(row['excerpt'] + f" [document:{row['document_id']}#chunk-{row['chunk']}]" for row in result['evidence'])
    result['answer_kind'] = 'verbatim_evidence_excerpts_not_generated_claims'
    result['found_evidence'] = bool(result['evidence'])
    return result

@router.post('/compare')
def compare_documents(request: Compare, project_id: ProjectId = None):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                rows = [require_document(cur,uuid.UUID(item),memory.local_memory_user(project_id)) for item in request.document_ids]
        # Literal line-set comparison, bounded output; no semantic equivalence claim.
        lines = [list(dict.fromkeys(row['content'].splitlines())) for row in rows]
        sets = [set(group) for group in lines]
        differences = [[{'line':number,'text':text[:500]} for number,text in enumerate(row['content'].splitlines(),1)
                        if text not in sets[1-index]][:30] for index,row in enumerate(rows)]
        return {'method':'literal_line_comparison', 'documents':[metadata(row) for row in rows],
                'common_unique_lines':len(sets[0] & sets[1]), 'unique_line_counts':[len(sets[0]-sets[1]),len(sets[1]-sets[0])],
                'differences':differences, 'difference_excerpt_limit':30, 'semantic_equivalence_checked':False}
    except HTTPException: raise
    except Exception: raise unavailable() from None

@router.get('/{document_id}')
def read_document(document_id: uuid.UUID, project_id: ProjectId = None):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur: row = require_document(cur, document_id, memory.local_memory_user(project_id))
        return {'document':metadata(row), 'content':row['content']}
    except HTTPException: raise
    except Exception: raise unavailable() from None

@router.patch('/{document_id}')
def refresh_document(document_id: uuid.UUID, request: Refresh, project_id: ProjectId = None):
    chunks, diagnostics = prepare(request.content, request.kind)
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                row = require_document(cur, document_id, memory.local_memory_user(project_id), True)
                if row['revision'] != request.expected_revision: raise HTTPException(409, 'document_changed_review_again')
                # UUID nonce prevents an old revision becoming valid after A -> B -> A refresh.
                new_revision = hashlib.sha256((revision(document_id,request) + uuid.uuid4().hex).encode()).hexdigest()
                cur.execute('''UPDATE local_documents SET name=%s,kind=%s,content=%s,revision=%s,updated_at=NOW()
                    WHERE document_id=%s RETURNING *''', (request.name,request.kind,request.content,new_revision,document_id))
                row = cur.fetchone()
                cur.execute('DELETE FROM local_document_chunks WHERE document_id=%s', (document_id,)); index_chunks(cur, document_id, chunks)
        return {'document':metadata(row), 'indexed_chunks':len(chunks), 'diagnostics':diagnostics}
    except HTTPException: raise
    except Exception: raise unavailable() from None

@router.post('/{document_id}/delete')
def delete_document(document_id: uuid.UUID, request: Review, project_id: ProjectId = None):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                row = require_document(cur, document_id, memory.local_memory_user(project_id), True)
                if row['revision'] != request.expected_revision: raise HTTPException(409, 'document_changed_review_again')
                cur.execute('DELETE FROM local_documents WHERE document_id=%s', (document_id,))
        return {'deleted':True, 'document_id':str(document_id), 'indexed_chunks_deleted':True}
    except HTTPException: raise
    except Exception: raise unavailable() from None
