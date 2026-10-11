'use client';

import React, { useState } from 'react';

export interface OptionComparison {
  criteria: { id: string; name: string; unit: string; direction: 'minimize' | 'maximize'; weight: string }[];
  options: { id: string; name: string; values: Record<string, string> }[];
}

export function ShyComparison({ disabled, onCompare }: { disabled: boolean; onCompare: (data: OptionComparison) => void }) {
  const [criteria, setCriteria] = useState<OptionComparison['criteria']>([{ id: 'c1', name: '', unit: '', direction: 'minimize', weight: '1' }]);
  const [options, setOptions] = useState<OptionComparison['options']>([{ id: 'o1', name: '', values: {} }, { id: 'o2', name: '', values: {} }]);
  const [error, setError] = useState('');
  function updateCriterion(index: number, patch: Partial<OptionComparison['criteria'][number]>) {
    setCriteria(current => current.map((item, i) => i === index ? { ...item, ...patch } : item));
  }
  return <details className="shy-comparison">
    <summary>Compare options</summary>
    <p className="shy-muted">Enter numeric values in the same unit for each criterion. Shy ranks only these supplied options and weights. Values are not independently verified.</p>
    <form onSubmit={event => {
      event.preventDefault();
      const decimal = /^[+-]?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?$/;
      if (criteria.some(c => !c.name.trim() || !decimal.test(c.weight) || Number(c.weight) <= 0 || Number(c.weight) > 100) ||
          options.some(o => !o.name.trim() || criteria.some(c => !decimal.test(o.values[c.id] ?? '')))) {
        setError('Supply names, every decimal value, and weights greater than zero and at most 100.'); return;
      }
      setError(''); onCompare({ criteria, options: options.map(o => ({ ...o, values: Object.fromEntries(criteria.map(c => [c.id, o.values[c.id]])) })) });
    }}>
      <fieldset disabled={disabled}>
        <legend>Criteria and options</legend>
        {criteria.map((c, i) => <fieldset key={c.id}>
          <legend>Criterion {i + 1}</legend>
          <label>Name <input aria-label={`Criterion ${i + 1} name`} maxLength={80} required value={c.name} onChange={e => updateCriterion(i, { name: e.target.value })} /></label>
          <label>Unit <input aria-label={`Criterion ${i + 1} unit`} maxLength={24} value={c.unit} onChange={e => updateCriterion(i, { unit: e.target.value })} /></label>
          <label>Preference <select aria-label={`Criterion ${i + 1} preference`} value={c.direction} onChange={e => updateCriterion(i, { direction: e.target.value as 'minimize' | 'maximize' })}><option value="minimize">Lower is better</option><option value="maximize">Higher is better</option></select></label>
          <label>Weight <input aria-label={`Criterion ${i + 1} weight`} maxLength={24} required value={c.weight} inputMode="decimal" onChange={e => updateCriterion(i, { weight: e.target.value })} /></label>
        </fieldset>)}
        <button type="button" disabled={criteria.length >= 6} onClick={() => setCriteria(current => [...current, { id: `c${current.length + 1}`, name: '', unit: '', direction: 'maximize', weight: '1' }])}>Add criterion</button>
        <button type="button" disabled={criteria.length <= 1} onClick={() => setCriteria(current => current.slice(0, -1))}>Remove last criterion</button>
        {options.map((o, i) => <fieldset key={o.id}>
          <legend>Option {i + 1}</legend>
          <label>Name <input aria-label={`Option ${i + 1} name`} maxLength={80} required value={o.name} onChange={e => setOptions(current => current.map((item, index) => index === i ? { ...item, name: e.target.value } : item))} /></label>
          {criteria.map((c, ci) => <label key={c.id}>Value for {c.name || `criterion ${ci + 1}`} <input aria-label={`Option ${i + 1} criterion ${ci + 1} value`} maxLength={24} required inputMode="decimal" value={o.values[c.id] ?? ''} onChange={e => setOptions(current => current.map((item, index) => index === i ? { ...item, values: { ...item.values, [c.id]: e.target.value } } : item))} /></label>)}
        </fieldset>)}
        <button type="button" disabled={options.length >= 8} onClick={() => setOptions(current => [...current, { id: `o${current.length + 1}`, name: '', values: {} }])}>Add option</button>
        <button type="button" disabled={options.length <= 2} onClick={() => setOptions(current => current.slice(0, -1))}>Remove last option</button>
        <button type="submit" className="shy-button">Calculate comparison</button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
    </form>
  </details>;
}
