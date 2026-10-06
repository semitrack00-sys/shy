import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShyDocuments } from '@/components/shy-documents';
const row={id:'00000000-0000-0000-0000-000000000001',name:'notes.txt',kind:'text',revision:'a'.repeat(64),characters:25};
function response(value:unknown,status=200){return {ok:status===200,status,json:async()=>value};}
function file(name='notes.txt',text='Source: PostgreSQL project'){
  const item=new File([text],name,{type:'text/plain'});
  Object.defineProperty(item,'arrayBuffer',{value:async()=>new TextEncoder().encode(text).buffer});return item;
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('reads only a selected file, confirms exact upload and preserves project scope',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({documents:[]})).mockResolvedValueOnce(response({document:row})).mockResolvedValueOnce(response({documents:[row]}));
  vi.stubGlobal('fetch',fetch);const user=userEvent.setup();render(<ShyDocuments projectId="gud-express"/>);
  expect(fetch).not.toHaveBeenCalled();await user.click(screen.getByRole('button',{name:'Review local documents'}));
  await user.upload(screen.getByLabelText('Selected text or CSV file'),file());
  const save=await screen.findByRole('button',{name:'Save reviewed document'});expect(save).toBeDisabled();expect(fetch).toHaveBeenCalledTimes(1);
  await user.click(screen.getByLabelText('I reviewed this exact document change and confirm it.'));await user.click(save);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({name:'notes.txt',kind:'text',content:'Source: PostgreSQL project',confirmed:true});
  expect(fetch.mock.calls.every(call=>String(call[0]).includes('project_id=gud-express'))).toBe(true);
  expect(await screen.findByText('Document change saved. The project index now reflects it.')).toBeInTheDocument();
});
it('searches only selected documents and shows source provenance',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({documents:[row]})).mockResolvedValueOnce(response({evidence:[{document_id:row.id,name:row.name,revision:row.revision,chunk:1,start_line:2,end_line:3,excerpt:'PostgreSQL source excerpt'}]}));
  vi.stubGlobal('fetch',fetch);const user=userEvent.setup();render(<ShyDocuments/>);
  await user.click(screen.getByRole('button',{name:'Review local documents'}));await user.click(await screen.findByLabelText('Select notes.txt'));
  await user.type(screen.getByLabelText('Document search keywords'),'PostgreSQL');await user.click(screen.getByRole('button',{name:'Search selected documents'}));
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({query:'PostgreSQL',document_ids:[row.id],limit:5});
  expect(await screen.findByText('notes.txt · lines 2–3 · chunk 1')).toBeInTheDocument();expect(screen.getByText('PostgreSQL source excerpt')).toBeInTheDocument();
});
it('deletion has separate confirmation and uses the reviewed revision',async()=>{
  const fetch=vi.fn().mockResolvedValueOnce(response({documents:[row]})).mockResolvedValueOnce(response({deleted:true})).mockResolvedValueOnce(response({documents:[]}));
  vi.stubGlobal('fetch',fetch);const user=userEvent.setup();render(<ShyDocuments/>);
  await user.click(screen.getByRole('button',{name:'Review local documents'}));await user.click(await screen.findByRole('button',{name:'Review delete notes.txt'}));
  const remove=screen.getByRole('button',{name:'Confirm document deletion'});expect(remove).toBeDisabled();
  await user.click(screen.getByLabelText('I reviewed this exact document change and confirm it.'));await user.click(remove);
  expect(String(fetch.mock.calls[1][0])).toContain(row.id+'/delete');expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({expected_revision:row.revision,confirmed:true});
});
it('changing the selected file clears prior consent and rejects oversized uploads',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(response({documents:[]})));const user=userEvent.setup();render(<ShyDocuments/>);
  await user.click(screen.getByRole('button',{name:'Review local documents'}));await user.upload(screen.getByLabelText('Selected text or CSV file'),file());
  await user.click(await screen.findByLabelText('I reviewed this exact document change and confirm it.'));
  await user.upload(screen.getByLabelText('Selected text or CSV file'),file('other.txt','Different source'));
  expect(await screen.findByRole('button',{name:'Save reviewed document'})).toBeDisabled();
  await user.upload(screen.getByLabelText('Selected text or CSV file'),file('large.txt','x'.repeat(256*1024+1)));
  expect(await screen.findByText('Select a .txt, .md or .csv file up to 256 KiB.')).toBeInTheDocument();expect(screen.queryByRole('button',{name:'Save reviewed document'})).toBeNull();
});
it('compares exactly two selected documents as literal lines',async()=>{
  const other={...row,id:'00000000-0000-0000-0000-000000000002',name:'other.txt'};
  const fetch=vi.fn().mockResolvedValueOnce(response({documents:[row,other]})).mockResolvedValueOnce(response({documents:[row,other],differences:[[{line:2,text:'First exclusive'}],[{line:2,text:'Second exclusive'}]],unique_line_counts:[1,1],common_unique_lines:1,semantic_equivalence_checked:false}));
  vi.stubGlobal('fetch',fetch);const user=userEvent.setup();render(<ShyDocuments/>);
  await user.click(screen.getByRole('button',{name:'Review local documents'}));await user.click(await screen.findByLabelText('Select notes.txt'));
  const compare=screen.getByRole('button',{name:'Compare two selected documents'});expect(compare).toBeDisabled();
  await user.click(screen.getByLabelText('Select other.txt'));await user.click(compare);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({document_ids:[row.id,other.id]});
  expect(await screen.findByText(/Literal line comparison; semantic equivalence is not checked/)).toBeInTheDocument();
});
