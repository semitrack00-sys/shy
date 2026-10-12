import { expect, it } from 'vitest';
import { formatOrderedComparison } from '@/lib/document-diff';
export const diff={status:'evaluated',method:'ordered_logical_lines',line_limit:1000,left_line_count:2,right_line_count:1,inserted_lines:0,deleted_lines:1,equal_lines:1,text_identical:false,line_sequence_equal:false,line_endings_compared:false,semantic_equivalence_checked:false,minimal_patch_guaranteed:false,change_hunk_count:1,hunks:[{kind:'delete',left:{start_line:2,line_count:1,samples:[{line:2,text:'Repeated source',truncated:false}],omitted_lines:0},right:{start_line:2,line_count:0,samples:[],omitted_lines:0}}],omitted_hunks:0,preview_truncated:false,hunk_limit:10,sample_lines_per_side:2,sample_character_limit:150};
it('explains repeated-line deletion, range and truthful comparison limits',()=>{
  const text=formatOrderedComparison(diff);expect(text).toContain('0 inserted, 1 deleted, 1 equal');expect(text).toContain('First document: lines 2–2');expect(text).toContain('Second document: before line 2');expect(text).toContain('Meaning is not checked');
});
it('rejects impossible counts, forged ranges, truth claims and inconsistent truncation',()=>{
  for(const bad of [{...diff,deleted_lines:9},{...diff,semantic_equivalence_checked:true},{...diff,preview_truncated:true},{...diff,line_sequence_equal:true},{...diff,hunks:[{...diff.hunks[0],left:{...diff.hunks[0].left,start_line:99}}]},{...diff,hunks:[{...diff.hunks[0],kind:'run_shell'}]}])expect(()=>formatOrderedComparison(bad)).toThrow('Invalid ordered');
});
it('explains unavailable ordered checks and preserves literal Unicode source samples',()=>{
  expect(formatOrderedComparison({status:'unavailable',reason:'ordered_logical_line_limit',line_limit:1000})).toContain('does not check order or repetitions');
  expect(formatOrderedComparison({...diff,hunks:[{...diff.hunks[0],left:{...diff.hunks[0].left,samples:[{line:2,text:'📄'.repeat(150),truncated:false}]}}]})).toContain('📄'.repeat(150));
});

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, vi } from 'vitest';
import { ShyDocuments } from '@/components/shy-documents';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('shows ordered differences with both revisions as inactive source text',async()=>{
  const rows=[{id:'00000000-0000-0000-0000-000000000001',name:'a.txt',kind:'text',revision:'a'.repeat(64),characters:5},{id:'00000000-0000-0000-0000-000000000002',name:'b.txt',kind:'text',revision:'b'.repeat(64),characters:3}];
  const ordered={...diff,hunks:[{...diff.hunks[0],left:{...diff.hunks[0].left,samples:[{line:2,text:'[bad](https://evil.example)',truncated:false}]}}]};
  const reply=(body: unknown)=>({ok:true,json:async()=>body});
  const fetcher=vi.fn().mockResolvedValueOnce(reply({documents:rows})).mockResolvedValueOnce(reply({documents:rows,differences:[[],[]],unique_line_counts:[0,0],common_unique_lines:1,semantic_equivalence_checked:false,ordered_comparison:ordered}));vi.stubGlobal('fetch',fetcher);
  const user=userEvent.setup();render(<ShyDocuments projectId="my-project"/>);
  await user.click(screen.getByText('Review local documents'));await user.click(await screen.findByLabelText('Select a.txt'));await user.click(screen.getByLabelText('Select b.txt'));
  await user.click(screen.getByText('Compare two selected documents'));
  const preview=await screen.findByText(/Ordered line comparison: 0 inserted, 1 deleted/);
  expect(preview).toHaveTextContent('revision '+rows[0].revision);expect(preview).toHaveTextContent('revision '+rows[1].revision);
  expect(screen.queryByRole('link',{name:'bad'})).not.toBeInTheDocument();
  expect(fetcher.mock.calls[1][0]).toContain('/compare?project_id=my-project');expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({document_ids:rows.map(r=>r.id)});
});
