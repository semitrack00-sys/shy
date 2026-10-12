'use client';
import React, { useState } from 'react';
import type { ResearchRequest } from '@/lib/types';

export function ShyResearchRequest({ disabled, onResearch }: { disabled: boolean; onResearch: (query: string, request: ResearchRequest) => void }) {
  const [query, setQuery] = useState('');
  const [freshness, setFreshness] = useState<ResearchRequest['freshness']>('auto');
  return <details className="shy-comparison">
    <summary>Research public sources</summary>
    <p className="shy-muted">Send this question to the configured public web search provider. Source dates are estimates; cited claims are not independently verified.</p>
    <form onSubmit={event => { event.preventDefault(); if (!disabled && query.trim() && query.trim().length <= 1000) onResearch(query.trim(), {freshness}); }}>
      <fieldset disabled={disabled}>
        <legend>Research question</legend>
        <label>Question <textarea aria-label="Public research question" maxLength={1000} required value={query} onChange={event => setQuery(event.target.value)} /></label>
        <label>Source dates <select aria-label="Research source date window" value={freshness} onChange={event => setFreshness(event.target.value as ResearchRequest['freshness'])}>
          <option value="auto">Use recency phrases in my question</option>
          <option value="same_day">Same UTC calendar day</option>
          <option value="past_week">Within 7 UTC calendar days</option>
          <option value="past_month">Within 30 UTC calendar days</option>
          <option value="any_date">Any source date, including undated</option>
        </select></label>
        <p className="shy-muted">A selected date window overrides recency phrases for this request. It applies to estimated source dates, not when search retrieved them.</p>
        <button type="submit" className="shy-button" disabled={!query.trim()}>Search public web</button>
      </fieldset>
    </form>
  </details>;
}
