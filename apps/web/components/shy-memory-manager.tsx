'use client';

import React, { useEffect, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';
import { parseMemory, type SavedMemory } from '@/lib/saved-memory';

type Review = { action: 'create' | 'correct' | 'delete'; record?: SavedMemory };

export function ShyMemoryManager() {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<SavedMemory[]>([]);
  const [page, setPage] = useState(0);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<Review | null>(null);
  const [subject, setSubject] = useState('');
  const [category, setCategory] = useState('USER_FACT');
  const [content, setContent] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState('');
  const requestRef = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  useEffect(() => () => requestRef.current?.abort(), []);

  async function request(path: string, method = 'GET', body?: unknown) {
    const controller = new AbortController();
    requestRef.current = controller;
    const response = await fetch(`${FRONTEND_API_BASE}/memories${path}`, {
      method, headers: { 'content-type': 'application/json' }, cache: 'no-store', signal: controller.signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(response.status === 409
      ? 'This memory changed or the subject already exists. Refresh memories, then review it again.'
      : response.status === 422 ? 'Check the subject, content, and confirmation. Secret-like text is rejected.'
        : 'Saved memories are unavailable. Check the SHY database and try again.');
    return payload;
  }

  async function load(nextPage: number) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setNotice(''); setReview(null); setConfirmed(false);
    try {
      const payload = await request(`?page=${nextPage}`);
      if (!Array.isArray(payload.records) || typeof payload.has_more !== 'boolean') throw new Error('Invalid saved-memory list.');
      setRows(payload.records.map(parseMemory)); setMore(payload.has_more); setPage(nextPage);
    } catch (error) {
      if (!requestRef.current?.signal.aborted) setNotice(error instanceof Error ? error.message : 'Could not load memories.');
    } finally { busyRef.current = false; setBusy(false); }
  }

  function startReview(next: Review) {
    setReview(next); setSubject(next.record?.subject_key ?? ''); setCategory(next.record?.category ?? 'USER_FACT');
    setContent(next.record?.content ?? ''); setConfirmed(false); setNotice('');
  }

  async function apply() {
    if (!review || !confirmed || busyRef.current) return;
    busyRef.current = true; setBusy(true); setNotice('');
    try {
      const row = review.record;
      if (review.action === 'create') {
        await request('', 'POST', { subject_key: subject.trim(), category, content: content.trim(), confirmed: true });
      } else if (row) {
        await request(`/${row.id}${review.action === 'delete' ? '/delete' : ''}`,
          review.action === 'delete' ? 'POST' : 'PATCH', {
            ...(review.action === 'delete' ? {} : { content: content.trim() }),
            expected_revision: row.revision, confirmed: true,
          });
      }
      setReview(null); setConfirmed(false);
      const payload = await request('?page=0');
      if (!Array.isArray(payload.records)) throw new Error('Memory changed, but the refreshed list could not be read.');
      setRows(payload.records.map(parseMemory)); setMore(Boolean(payload.has_more)); setPage(0);
      setNotice(review.action === 'delete' ? 'Selected saved memory deleted. Original chat history remains.' : 'Saved memory updated.');
    } catch (error) {
      setConfirmed(false);
      if (!requestRef.current?.signal.aborted) setNotice(error instanceof Error ? error.message : 'Could not change memory.');
    } finally { busyRef.current = false; setBusy(false); }
  }

  return <section className="shy-memory-manager" aria-label="Saved memories">
    <button className="shy-button" type="button" disabled={busy} aria-expanded={open}
      onClick={() => { setOpen(!open); if (!open) void load(0); }}> {open ? 'Hide saved memories' : 'Review saved memories'} </button>
    {open && <>
      <p className="shy-muted">Saved facts for this local SHY user. Existing chat may save recognized facts and preferences automatically.
        Deleting a saved memory does not delete the original chat. This installation does not yet have account isolation.</p>
      <p className="shy-muted">Do not save passwords, API keys, tokens, or private keys.</p>
      <div className="shy-memory-actions">
        <button className="shy-button" type="button" disabled={busy} onClick={() => void load(page)}>Refresh memories</button>
        <button className="shy-button" type="button" disabled={busy} onClick={() => startReview({ action: 'create' })}>Remember this</button>
      </div>
      {busy && <p role="status">Updating saved memories…</p>}
      {!busy && !rows.length && <p>No saved memories on this page.</p>}
      <ul className="shy-memory-list">{rows.map(row => <li key={row.id}>
        <strong>{row.subject_key}</strong> <span>{row.category} · {row.status}</span>
        <p>{row.content}</p>
        <div className="shy-memory-actions">
          <button className="shy-button" type="button" disabled={busy || row.status !== 'ACTIVE'}
            onClick={() => startReview({ action: 'correct', record: row })}>Correct {row.subject_key}</button>
          <button className="shy-button" type="button" disabled={busy}
            onClick={() => startReview({ action: 'delete', record: row })}>Delete {row.subject_key}</button>
        </div>
      </li>)}</ul>
      {review && <form aria-label="Review memory change" onSubmit={event => { event.preventDefault(); void apply(); }}>
        <h3>{review.action === 'create' ? 'Remember a fact' : review.action === 'correct' ? 'Correct saved memory' : 'Delete saved memory'}</h3>
        {review.action === 'create' ? <>
          <label>Memory subject<input required value={subject} maxLength={80} pattern="[a-z0-9][a-z0-9_.-]*"
            onChange={event => { setSubject(event.target.value); setConfirmed(false); }} placeholder="project.shy.database" /></label>
          <label>Memory category<select value={category} onChange={event => { setCategory(event.target.value); setConfirmed(false); }}>
            <option value="USER_FACT">Personal fact</option><option value="PREFERENCE">Preference</option><option value="PROJECT">Project fact</option>
          </select></label>
        </> : <p>Subject: {review.record?.subject_key}</p>}
        {review.action === 'delete' ? <p>{review.record?.content}</p> : <label>Memory content<textarea required value={content} maxLength={500}
          onChange={event => { setContent(event.target.value); setConfirmed(false); }} /></label>}
        <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)} />
          I reviewed this exact memory change and confirm it.</label>
        <div className="shy-memory-actions">
          <button className="shy-button" type="submit" disabled={busy || !confirmed || (review.action !== 'delete' && !content.trim())}>
            {review.action === 'delete' ? 'Confirm deletion' : 'Save reviewed memory'}</button>
          <button className="shy-button" type="button" disabled={busy} onClick={() => { setReview(null); setConfirmed(false); }}>Cancel memory change</button>
        </div>
      </form>}
      <div className="shy-memory-actions">
        <button className="shy-button" type="button" disabled={busy || page === 0} onClick={() => void load(page - 1)}>Previous memories</button>
        <span>Page {page + 1}</span>
        <button className="shy-button" type="button" disabled={busy || !more} onClick={() => void load(page + 1)}>Next memories</button>
      </div>
      {notice && <p role="status">{notice}</p>}
    </>}
  </section>;
}
