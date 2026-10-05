export interface SavedMemory {
  id: string;
  subject_key: string;
  category: string;
  content: string;
  status: string;
  revision: string;
}

export function parseMemory(value: unknown): SavedMemory {
  if (!value || typeof value !== 'object') throw new Error('Invalid saved-memory response.');
  const row = value as Record<string, unknown>;
  if (!['id', 'subject_key', 'category', 'content', 'status', 'revision'].every(key => typeof row[key] === 'string')
    || !/^[0-9a-f]{64}$/.test(String(row.revision))) throw new Error('Invalid saved-memory response.');
  return { id: String(row.id), subject_key: String(row.subject_key), category: String(row.category),
    content: String(row.content), status: String(row.status), revision: String(row.revision) };
}
