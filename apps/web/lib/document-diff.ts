function record(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function integer(value: unknown, max: number): value is number { return typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= max; }
function invalid(): never { throw new Error('Invalid ordered comparison response.'); }
export function formatOrderedComparison(value: unknown): string {
  if (!record(value) || value.line_limit !== 1000) return invalid();
  if (value.status === 'unavailable') {
    if (!['ordered_text_character_limit','ordered_logical_line_limit'].includes(String(value.reason))) return invalid();
    return 'Ordered comparison unavailable: each document must fit within 100,000 characters and 1,000 logical lines. The unique-line summary below does not check order or repetitions.';
  }
  if (value.status !== 'evaluated' || value.method !== 'ordered_logical_lines' || value.line_endings_compared !== false || value.semantic_equivalence_checked !== false || value.minimal_patch_guaranteed !== false || value.hunk_limit !== 10 || value.sample_lines_per_side !== 2 || value.sample_character_limit !== 150) return invalid();
  for (const key of ['left_line_count','right_line_count','inserted_lines','deleted_lines','equal_lines','change_hunk_count','omitted_hunks']) if (!integer(value[key], 2000)) return invalid();
  const leftCount=value.left_line_count as number, rightCount=value.right_line_count as number, deleted=value.deleted_lines as number, inserted=value.inserted_lines as number, equal=value.equal_lines as number, count=value.change_hunk_count as number;
  if (leftCount > 1000 || rightCount > 1000 || equal + deleted !== leftCount || equal + inserted !== rightCount || typeof value.line_sequence_equal !== 'boolean' || value.line_sequence_equal !== (count === 0) || typeof value.text_identical !== 'boolean' || (value.text_identical && !value.line_sequence_equal) || typeof value.preview_truncated !== 'boolean' || !Array.isArray(value.hunks) || value.hunks.length !== Math.min(count,10) || value.omitted_hunks !== count-value.hunks.length) return invalid();
  let truncated=(value.omitted_hunks as number)>0;
  function side(value: unknown, length: number, name: string): string {
    if (!record(value) || !integer(value.start_line,1001) || value.start_line < 1 || !integer(value.line_count,1000) || value.start_line + value.line_count > length+1 || !integer(value.omitted_lines,1000) || value.omitted_lines !== Math.max(0,value.line_count-2) || !Array.isArray(value.samples) || value.samples.length !== Math.min(value.line_count,2)) return invalid();
    const text=[value.line_count === 0 ? `${name}: before line ${value.start_line} (no lines).` : `${name}: lines ${value.start_line}–${value.start_line + value.line_count-1}.`];
    for (const [index,row] of value.samples.entries()) {
      if (!record(row) || row.line !== value.start_line+index || typeof row.text !== 'string' || Array.from(row.text).length > 150 || typeof row.truncated !== 'boolean') return invalid();
      truncated ||= row.truncated; text.push(`Line ${row.line}: ${row.text}${row.truncated ? ' [line excerpt truncated]' : ''}`);
    }
    truncated ||= value.omitted_lines>0;
    if (value.omitted_lines) text.push(`${value.omitted_lines} lines omitted from this excerpt.`);
    return text.join('\n');
  }
  const hunks=value.hunks.map((h: unknown) => {
    if (!record(h) || !['insert','delete','replace'].includes(String(h.kind)) || !record(h.left) || !record(h.right)) return invalid();
    if ((h.kind === 'insert' && (h.left.line_count !== 0 || !h.right.line_count)) || (h.kind === 'delete' && (h.right.line_count !== 0 || !h.left.line_count)) || (h.kind === 'replace' && (!h.left.line_count || !h.right.line_count))) return invalid();
    return `${h.kind}\n${side(h.left,leftCount,'First document')}\n${side(h.right,rightCount,'Second document')}`;
  });
  if (value.preview_truncated !== truncated) return invalid();
  return [`Ordered line comparison: ${inserted} inserted, ${deleted} deleted, ${equal} equal lines.`,
    value.line_sequence_equal ? (value.text_identical ? 'The stored text is identical.' : 'Logical lines match; stored text differs in line separators or endings.') : 'Line order or occurrence counts differ.',
    'Line separators and endings are not compared. Meaning is not checked; this is a preview, not a guaranteed minimal patch.',
    'At most 10 change groups, 2 sample lines per side and 150 characters per line are shown.',
    value.preview_truncated ? 'Preview truncated: some changes or source text are omitted.' : 'All change groups and their source lines fit within this preview.',
    `${value.omitted_hunks} additional change groups omitted.`,...hunks].join('\n\n');
}
