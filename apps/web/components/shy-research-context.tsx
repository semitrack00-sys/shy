'use client';

import React from 'react';
import { parseResearchAnswer } from '@/lib/shy-api';

export function ShyResearchContext({ value }: { value: unknown }) {
  const answer = parseResearchAnswer(value);
  if (!answer) return null;
  const summaries = {
    model_synthesis: 'A model generated this answer from the supplied search excerpts.',
    missing_recent_evidence: 'Newer dated evidence is needed before answering this as current.',
    missing_excerpts: 'Source text is needed before answering the factual question.',
    possible_disagreement: 'Possible source disagreements need more context before choosing a value.',
  };
  const windowOrigins = {
    english_hint: 'This window comes from English recency phrases.',
    french_hint: 'This window comes from French recency phrases.',
    haitian_creole_hint: 'This window comes from Haitian Creole recency phrases.',
    mixed_hint: 'This window comes from recency phrases in multiple languages.',
    no_window: '',
  };
  const origin = answer.date_window_basis ? windowOrigins[answer.date_window_basis] : 'The origin of this date window was not recorded.';
  return (
    <section className="shy-tool-card" aria-label="Research answer context">
      <p className="shy-section-label">Answer context</p>
      <p>{summaries[answer.mode]}</p>
      {!answer.model_invoked && <p className="shy-muted">SHY generated this clarification without a model.</p>}
      <details>
        <summary>Checks and limits</summary>
        <ul>
          {answer.source_count !== undefined && <li>{answer.source_count} source {answer.source_count === 1 ? 'record' : 'records'} checked. This is not a count of independent authorities.</li>}
          {(answer.mode === 'model_synthesis' || answer.mode === 'possible_disagreement') && <li>Numeric citations were checked against the supplied sources.</li>}
          {answer.date_window_days !== undefined && <li>{answer.date_window_days === null
            ? 'No recency window was selected; older or undated excerpts may be used.'
            : `Recent sources must be within ${answer.date_window_days} UTC calendar days. ${origin}`}</li>}
          <li>Fixed phrase rules do not interpret negation, quotations or general language intent.</li>
          <li>Any provider dates are estimates. Retrieval time does not prove publication time.</li>
          {answer.mode === 'possible_disagreement' && <li>Matching field labels may refer to different subjects or dates. General prose was not independently compared for meaning.</li>}
          <li>Source claims have not been independently verified as true.</li>
        </ul>
      </details>
    </section>
  );
}
