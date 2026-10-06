'use client';

import React, { useEffect, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';

type Preference = { automatic_saving: boolean; revision: string; reviewed: boolean };
function parse(value: unknown): Preference {
  const item = value as Partial<Preference> | null;
  if (!item || typeof item.automatic_saving !== 'boolean' || typeof item.reviewed !== 'boolean'
      || typeof item.revision !== 'string' || !/^(0|[1-9][0-9]{0,18})$/.test(item.revision)) {
    throw new Error('Invalid memory saving setting.');
  }
  return item as Preference;
}

export function ShyMemorySaving({ projectId }: { projectId?: string }) {
  const [preference, setPreference] = useState<Preference | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const lock = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function request(save: boolean) {
    if (lock.current || (save && (!confirmed || !preference))) return;
    lock.current = true; setBusy(true); setConfirmed(false); setNotice('');
    const abort = new AbortController(); controller.current = abort;
    try {
      const response = await fetch(`${FRONTEND_API_BASE}/memories/preferences${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, {
        method: save ? 'PATCH' : 'GET', cache: 'no-store', signal: abort.signal,
        headers: { 'content-type': 'application/json' },
        ...(save ? { body: JSON.stringify({ automatic_saving: enabled, expected_revision: preference!.revision, confirmed: true }) } : {}),
      });
      if (!response.ok) {
        if (response.status === 409) setPreference(null);
        throw new Error(response.status === 409 ? 'Setting changed. Review the current setting again.' : 'Memory saving setting is unavailable.');
      }
      const result = parse(await response.json());
      if (abort.signal.aborted) return;
      setPreference(result); setEnabled(result.automatic_saving);
      if (save) setNotice(result.automatic_saving ? 'Automatic memory saving resumed.' : 'Automatic memory saving paused.');
    } catch (error) {
      if (!abort.signal.aborted) setNotice(error instanceof Error ? error.message : 'Could not update memory saving.');
    } finally {
      lock.current = false;
      if (!abort.signal.aborted) setBusy(false);
    }
  }

  return <section className="shy-memory-manager" aria-label="Automatic memory saving">
    <button className="shy-button" type="button" disabled={busy} onClick={() => void request(false)}>Review automatic memory saving</button>
    {preference && <>
      <p>Automatic saving is {preference.automatic_saving ? 'on' : 'paused'}.
        {!preference.reviewed && ' This is the existing default; you have not reviewed this setting yet.'}</p>
      <p className="shy-muted">Applies to recognized facts, preferences, and task outcomes for this local SHY project ({projectId ?? 'default'}).
        Existing saved memories may still be used. Chat history and manually confirmed memories remain available.
        This installation does not yet have account isolation.</p>
      <label><input type="checkbox" checked={enabled} disabled={busy}
        onChange={event => { setEnabled(event.target.checked); setConfirmed(false); }} />Allow automatic memory saving</label>
      <label><input type="checkbox" checked={confirmed} disabled={busy}
        onChange={event => setConfirmed(event.target.checked)} />I confirm this automatic saving setting.</label>
      <button className="shy-button" type="button" disabled={busy || !confirmed} onClick={() => void request(true)}>Save memory saving setting</button>
    </>}
    {notice && <p role="status">{notice}</p>}
  </section>;
}
