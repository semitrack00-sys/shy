import type { ShyDocumentAnswer } from './types';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
export function parseDocumentAnswer(value: unknown): ShyDocumentAnswer | undefined {
  if (!object(value) || value.method !== 'local_keyword_search' || value.answer_kind !== 'verbatim_evidence_excerpts_not_generated_claims' || value.model_invoked !== false || value.semantic_support_verified !== false || typeof value.found_evidence !== 'boolean') return undefined;
  if (!Array.isArray(value.selected_documents) || value.selected_documents.length < 1 || value.selected_documents.length > 5 || value.selected_documents.some(id => typeof id !== 'string' || !uuid.test(id))) return undefined;
  const selected = value.selected_documents.map(id => (id as string).toLowerCase());
  if (new Set(selected).size !== selected.length || !Array.isArray(value.evidence) || value.evidence.length > 5 || value.found_evidence !== (value.evidence.length > 0)) return undefined;
  const evidence: ShyDocumentAnswer['evidence'] = [];
  const seen = new Set<string>();
  for (const row of value.evidence) {
    if (!object(row) || typeof row.document_id !== 'string' || !selected.includes(row.document_id.toLowerCase()) || typeof row.name !== 'string' || Array.from(row.name).length > 120 || typeof row.revision !== 'string' || !/^[0-9a-f]{64}$/.test(row.revision) || typeof row.excerpt !== 'string' || row.excerpt.length > 2000) return undefined;
    for (const key of ['chunk','start_line','end_line']) if (typeof row[key] !== 'number' || !Number.isInteger(row[key]) || (row[key] as number) < 1 || (row[key] as number) > (key === 'chunk' ? 250 : 100001)) return undefined;
    if ((row.end_line as number) < (row.start_line as number)) return undefined;
    const key = `${row.document_id.toLowerCase()}:${row.chunk}`;
    if (seen.has(key)) return undefined; seen.add(key);
    evidence.push({document_id:row.document_id.toLowerCase(),name:row.name,revision:row.revision,excerpt:row.excerpt,chunk:row.chunk as number,start_line:row.start_line as number,end_line:row.end_line as number});
  }
  return {method:'local_keyword_search',answer_kind:'verbatim_evidence_excerpts_not_generated_claims',model_invoked:false,semantic_support_verified:false,found_evidence:value.found_evidence,selected_documents:selected,evidence};
}
