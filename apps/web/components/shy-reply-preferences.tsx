'use client';
import React, { useEffect, useId, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';
const languages = [['auto','Follow message language'],['en','English'],['fr','French'],['ht','Haitian Creole'],['es','Spanish'],['pt','Portuguese (Brazil)'],['ko','Korean'],['sw','Swahili']];
type Profile = {enabled:boolean;language:string;detail:string;tone:string;revision:string;reviewed:boolean};
function parse(value: unknown): Profile {
  const item=value as Partial<Profile> | null;
  if (!item || typeof item.enabled !== 'boolean' || typeof item.reviewed !== 'boolean' || !languages.some(([code])=>code===item.language) || !['short','standard','detailed'].includes(item.detail ?? '') || !['plain','formal'].includes(item.tone ?? '') || typeof item.revision !== 'string' || !/^(0|[1-9][0-9]{0,18})$/.test(item.revision)) throw new Error('Invalid reply preferences.');
  if (item.reviewed === (item.revision === "0") || (!item.reviewed && item.enabled)) throw new Error("Invalid reply preferences.");
  return item as Profile;
}
export function ShyReplyPreferences({projectId}:{projectId?:string}) {
  const id=useId();const [profile,setProfile]=useState<Profile|null>(null);const [draft,setDraft]=useState<Profile|null>(null);
  const [confirmed,setConfirmed]=useState(false);const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const lock=useRef(false);const controller=useRef<AbortController|null>(null);
  useEffect(()=>()=>controller.current?.abort(),[]);
  function change(patch:Partial<Profile>) {setDraft(current=>current?{...current,...patch}:current);setConfirmed(false);}
  async function request(save:boolean) {
    if (lock.current || (save && (!confirmed || !profile || !draft))) return;
    lock.current=true;setBusy(true);setConfirmed(false);setNotice('');const abort=new AbortController();controller.current=abort;
    try {
      const response=await fetch(`${FRONTEND_API_BASE}/memories/response-preferences${projectId?`?project_id=${encodeURIComponent(projectId)}`:''}`,{
        method:save?'PATCH':'GET',cache:'no-store',signal:abort.signal,headers:{'content-type':'application/json'},
        ...(save?{body:JSON.stringify({enabled:draft!.enabled,language:draft!.language,detail:draft!.detail,tone:draft!.tone,expected_revision:profile!.revision,confirmed:true})}:{}),
      });
      if (!response.ok) {if(response.status===409){setProfile(null);setDraft(null);}throw new Error(response.status===409?'Reply settings changed. Review them again.':'Reply preferences are unavailable.');}
      const result=parse(await response.json());if(abort.signal.aborted)return;setProfile(result);setDraft(result);
      if(save)setNotice(result.enabled?'Reviewed reply defaults saved.':'Reply defaults disabled.');
    } catch(error) {if(!abort.signal.aborted)setNotice(error instanceof Error?error.message:'Could not update reply preferences.');}
    finally {lock.current=false;if(!abort.signal.aborted)setBusy(false);}
  }
  return <section className="shy-memory-manager" aria-label="Reply preferences">
    <button type="button" className="shy-button" disabled={busy} onClick={()=>void request(false)}>Review reply preferences</button>
    {profile && draft && <>
      <p>Reply defaults for project {projectId??'default'}. {!profile.reviewed&&'No reviewed defaults have been saved.'}</p>
      <p className="shy-muted">Enabled defaults keep reply generation on your local AI model. A working local model is required. These are instructions for generated prose; model language and style quality are unverified. Exact calculations, source excerpts and other deterministic replies retain their text. Current explicit instructions take precedence. This local installation does not authenticate project access.</p>
      <label><input type="checkbox" checked={draft.enabled} disabled={busy} onChange={e=>change({enabled:e.target.checked})}/>Use reviewed reply defaults</label>
      <div><label htmlFor={`${id}-language`}>Reply language</label><select id={`${id}-language`} value={draft.language} disabled={busy} onChange={e=>change({language:e.target.value})}>{languages.map(([code,name])=><option key={code} value={code}>{name}</option>)}</select></div>
      <div><label htmlFor={`${id}-detail`}>Reply detail</label><select id={`${id}-detail`} value={draft.detail} disabled={busy} onChange={e=>change({detail:e.target.value})}><option value="short">Short</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></div>
      <div><label htmlFor={`${id}-tone`}>Reply tone</label><select id={`${id}-tone`} value={draft.tone} disabled={busy} onChange={e=>change({tone:e.target.value})}><option value="plain">Plain</option><option value="formal">Formal</option></select></div>
      <label><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>I reviewed these exact reply defaults and confirm them.</label>
      <button type="button" className="shy-button" disabled={busy||!confirmed} onClick={()=>void request(true)}>Save reviewed reply defaults</button>
    </>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
