'use client';

import React, { useEffect, useId, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';

type Document = { id:string; name:string; kind:'text'|'csv'; revision:string; characters:number };
type Evidence = { document_id:string; name:string; revision:string; chunk:number; start_line:number; end_line:number; excerpt:string };
type FileDraft = { name:string; kind:'text'|'csv'; content:string };
type Review = { action:'refresh'|'delete'; document:Document } | null;
function parseDocument(value: unknown): Document {
  const item = value as Partial<Document> | null;
  if (!item || typeof item.id !== 'string' || !/^[0-9a-f-]{36}$/i.test(item.id)
      || typeof item.name !== 'string' || !['text','csv'].includes(item.kind ?? '')
      || typeof item.revision !== 'string' || !/^[0-9a-f]{64}$/.test(item.revision)
      || typeof item.characters !== 'number') throw new Error('Invalid document record.');
  return item as Document;
}

function parseEvidence(value: unknown): Evidence {
  const item = value as Partial<Evidence> | null;
  if (!item || typeof item.document_id !== 'string' || !/^[0-9a-f-]{36}$/i.test(item.document_id)
      || typeof item.name !== 'string' || typeof item.revision !== 'string' || !/^[0-9a-f]{64}$/.test(item.revision)
      || !Number.isInteger(item.chunk) || (item.chunk ?? 0) < 1 || (item.chunk ?? 0) > 250
      || !Number.isInteger(item.start_line) || (item.start_line ?? 0) < 1
      || !Number.isInteger(item.end_line) || (item.end_line ?? 0) < (item.start_line ?? 0)
      || typeof item.excerpt !== 'string' || item.excerpt.length > 2000) throw new Error('Invalid source evidence.');
  return item as Evidence;
}

export function ShyDocuments({ projectId }: { projectId?:string }) {
  const formId = useId();
  const [open, setOpen] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [draft, setDraft] = useState<FileDraft | null>(null);
  const [review, setReview] = useState<Review>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [query, setQuery] = useState('');
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [preview, setPreview] = useState('');
  const [comparison, setComparison] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const lock = useRef(false); const controller = useRef<AbortController | null>(null);
  const fileEpoch = useRef(0);
  useEffect(() => () => { controller.current?.abort(); fileEpoch.current++; }, []);

  async function request(path = '', method = 'GET', body?:unknown) {
    const abort = new AbortController(); controller.current = abort;
    const suffix = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
    const response = await fetch(`${FRONTEND_API_BASE}/documents${path}${suffix}`, {
      method, cache:'no-store', signal:abort.signal, headers:{'content-type':'application/json'},
      ...(body === undefined ? {} : { body:JSON.stringify(body) }),
    });
    if (!response.ok) throw new Error(response.status === 409 ? 'Document changed or the project limit was reached. Refresh and review again.'
      : response.status === 422 || response.status === 413 ? 'Document or request exceeds supported limits. Use UTF-8 text/CSV up to 256 KiB and 100,000 characters.'
        : 'Local documents are unavailable. Check the SHY database.');
    return await response.json();
  }
  async function run(action:() => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setNotice('');
    try { await action(); }
    catch (error) {
      setConfirmed(false);
      if (!controller.current?.signal.aborted) setNotice(error instanceof Error ? error.message : 'Document operation failed.');
    } finally { lock.current = false; setBusy(false); }
  }
  async function load() {
    const result = await request();
    if (!Array.isArray(result.documents)) throw new Error('Invalid document list.');
    setDocuments(result.documents.map(parseDocument)); setSelected([]); setEvidence([]); setReview(null); setConfirmed(false); setPreview(''); setComparison('');
  }
  async function choose(file?: File) {
    const epoch = ++fileEpoch.current; setDraft(null); setConfirmed(false); setNotice('');
    if (!file) return;
    try {
      if (file.size > 256 * 1024 || !/\.(txt|md|csv)$/i.test(file.name)) throw new Error('Select a .txt, .md or .csv file up to 256 KiB.');
      const content = new TextDecoder('utf-8', { fatal:true }).decode(await file.arrayBuffer());
      if (epoch !== fileEpoch.current) return;
      if (!content.trim() || content.length > 100_000 || content.includes('\0')) throw new Error('Select nonempty UTF-8 text up to 100,000 characters.');
      setDraft({ name:file.name, kind:/\.csv$/i.test(file.name) ? 'csv' : 'text', content });
    } catch (error) { if (epoch === fileEpoch.current) setNotice(error instanceof Error ? error.message : 'Could not read selected file.'); }
  }
  function startReview(next: Review) { setReview(next); setConfirmed(false); setNotice(''); }
  async function apply() {
    if (!confirmed || (review?.action !== 'delete' && !draft)) return;
    await run(async () => {
      if (review?.action === 'delete') await request(`/${review.document.id}/delete`, 'POST', { expected_revision:review.document.revision, confirmed:true });
      else if (review?.action === 'refresh') await request(`/${review.document.id}`, 'PATCH', { ...draft, expected_revision:review.document.revision, confirmed:true });
      else await request('', 'POST', { ...draft, confirmed:true });
      await load(); setDraft(null); setConfirmed(false);
      setNotice('Document change saved. The project index now reflects it.');
    });
  }
  async function search() {
    if (!selected.length || !query.trim()) return;
    await run(async () => {
      const result = await request('/search','POST',{ query:query.trim(), document_ids:selected, limit:5 });
      if (!Array.isArray(result.evidence)) throw new Error('Invalid evidence response.');
      setEvidence(result.evidence.map(parseEvidence)); setNotice(result.evidence.length ? 'Selected source excerpts found. These are document statements, not independently verified facts.' : 'No matching evidence in the selected documents.');
    });
  }
  async function compare() {
    if (selected.length !== 2) return;
    await run(async () => {
      const result = await request('/compare','POST',{ document_ids:selected });
      if (!Array.isArray(result.documents) || result.documents.length !== 2 || !Array.isArray(result.differences)
          || result.differences.length !== 2 || !Array.isArray(result.unique_line_counts)
          || result.semantic_equivalence_checked !== false) throw new Error('Invalid comparison response.');
      const sources = result.documents.map(parseDocument);
      const groups = result.differences.map((group:unknown, index:number) => {
        if (!Array.isArray(group) || group.length > 30) throw new Error('Invalid comparison excerpts.');
        return `${sources[index].name}: ${result.unique_line_counts[index]} unique lines\n` + group.map(item => {
          if (typeof item.text !== 'string' || !Number.isInteger(item.line)) throw new Error('Invalid comparison line.');
          return `Line ${item.line}: ${item.text}`;
        }).join('\n');
      });
      setComparison(`Literal line comparison; semantic equivalence is not checked.\nCommon unique lines: ${result.common_unique_lines}\nUp to 30 differences per document, 500 characters per line.\n\n${groups.join('\n\n')}`);
    });
  }
  return <section className="shy-memory-manager" aria-label="Local documents">
    <button className="shy-button" type="button" disabled={busy} aria-expanded={open}
      onClick={() => { setOpen(!open); if (!open) void run(load); }}> {open ? 'Hide local documents' : 'Review local documents'} </button>
    {open && <>
      <p className="shy-muted">Project: {projectId ?? 'default'}. Upload only files you select and confirm. Text and CSV are indexed locally;
        CSV formulas are never executed. PDF, Word and Excel files are not supported by this control yet.
        This local installation does not authenticate project access. Avoid uploading passwords or keys.</p>
      <button className="shy-button" type="button" disabled={busy} onClick={() => void run(load)}>Refresh document list</button>
      <div><label htmlFor={`${formId}-file`}>Selected text or CSV file</label>
        <input id={`${formId}-file`} type="file" accept=".txt,.md,.csv" disabled={busy || review?.action === 'delete'} onChange={event => { void choose(event.target.files?.[0]); event.target.value = ''; }} /></div>
      {review && <p>{review.action === 'delete' ? 'Delete' : 'Refresh'} reviewed document: {review.document.name}</p>}
      {draft && review?.action !== 'delete' && <><p>{draft.name} · {draft.content.length} characters · {draft.kind}</p>
        <pre className="shy-document-preview">{draft.content.slice(0,1000)}{draft.content.length > 1000 ? '\n[Preview truncated]' : ''}</pre></>}
      {(draft || review?.action === 'delete') && <>
        <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />I reviewed this exact document change and confirm it.</label>
        <div className="shy-memory-actions">
          <button className="shy-button" type="button" disabled={busy || !confirmed} onClick={() => void apply()}>{review?.action === 'delete' ? 'Confirm document deletion' : 'Save reviewed document'}</button>
          <button className="shy-button" type="button" disabled={busy} onClick={() => { fileEpoch.current++; setDraft(null); setReview(null); setConfirmed(false); }}>Cancel document change</button>
        </div>
      </>}
      <ul className="shy-memory-list">{documents.map(document => <li key={document.id}>
        <label><input type="checkbox" checked={selected.includes(document.id)} disabled={busy || (!selected.includes(document.id) && selected.length >= 5)}
          onChange={event => { setSelected(current => event.target.checked ? [...current,document.id] : current.filter(id => id !== document.id)); setEvidence([]); setComparison(''); }} />Select {document.name}</label>
        <p>{document.kind} · {document.characters} characters</p>
        <div className="shy-memory-actions">
          <button className="shy-button" type="button" disabled={busy} onClick={() => void run(async () => { const result = await request(`/${document.id}`); setPreview(String(result.content)); })}>Read {document.name}</button>
          <button className="shy-button" type="button" disabled={busy} onClick={() => startReview({action:'refresh',document})}>Review refresh {document.name}</button>
          <button className="shy-button" type="button" disabled={busy} onClick={() => startReview({action:'delete',document})}>Review delete {document.name}</button>
        </div>
      </li>)}</ul>
      {preview && <pre className="shy-document-preview">{preview}</pre>}
      <div><label htmlFor={`${formId}-query`}>Document search keywords</label><input id={`${formId}-query`} value={query} maxLength={500} disabled={busy} onChange={event => { setQuery(event.target.value); setEvidence([]); }} /></div>
      <button className="shy-button" type="button" disabled={busy || !selected.length || !query.trim()} onClick={() => void search()}>Search selected documents</button>
      <button className="shy-button" type="button" disabled={busy || selected.length !== 2} onClick={() => void compare()}>Compare two selected documents</button>
      {comparison && <pre className="shy-document-preview">{comparison}</pre>}
      <ul className="shy-memory-list">{evidence.map(item => <li key={`${item.document_id}:${item.chunk}`}>
        <strong>{item.name} · lines {item.start_line}–{item.end_line} · chunk {item.chunk}</strong>
        <pre className="shy-document-preview">{item.excerpt}</pre>
      </li>)}</ul>
      {notice && <p role="status">{notice}</p>}
      {busy && <p role="status">Updating local documents…</p>}
    </>}
  </section>;
}
