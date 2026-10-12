import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ShyResearchContext } from '@/components/shy-research-context';
import { parseResearchAnswer } from '@/lib/shy-api';
afterEach(cleanup);

it.each([
  ['model_synthesis',true,'A model generated this answer from the supplied search excerpts.'],
  ['missing_recent_evidence',false,'Newer dated evidence is needed before answering this as current.'],
  ['missing_excerpts',false,'Source text is needed before answering the factual question.'],
  ['possible_disagreement',false,'Possible source disagreements need more context before choosing a value.'],
])('explains %s without inventing a confidence claim', (mode, invoked, summary) => {
  render(<ShyResearchContext value={{mode,model_invoked:invoked,semantic_truth_verified:false,source_count:2,date_window_days:7,private_reasoning:'Never display this'}}/>);
  expect(screen.getByText(summary)).toBeInTheDocument();
  expect(screen.getByText('Checks and limits').closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText('2 source records checked. This is not a count of independent authorities.')).toBeInTheDocument();
  expect(screen.getByText(/within 7 UTC calendar days/)).toBeInTheDocument();
  expect(screen.getByText('Source claims have not been independently verified as true.')).toBeInTheDocument();
  expect(screen.queryByText('Never display this')).not.toBeInTheDocument();
  expect(!!screen.queryByText('SHY generated this clarification without a model.')).toBe(!invoked);
});
it('supports older metadata without guessing its source count or date window', () => {
  render(<ShyResearchContext value={{mode:'missing_excerpts',model_invoked:false,semantic_truth_verified:false}}/>);
  expect(screen.getByText('Answer context')).toBeInTheDocument();
  expect(screen.queryByText(/source records checked/)).not.toBeInTheDocument();
  expect(screen.queryByText(/recency window|UTC calendar days/)).not.toBeInTheDocument();
});
it('distinguishes no date window from a same-day UTC requirement', () => {
  const {rerender}=render(<ShyResearchContext value={{mode:'model_synthesis',model_invoked:true,semantic_truth_verified:false,date_window_days:null}}/>);
  expect(screen.getByText(/No recency window was selected/)).toBeInTheDocument();
  rerender(<ShyResearchContext value={{mode:'missing_recent_evidence',model_invoked:false,semantic_truth_verified:false,date_window_days:0}}/>);
  expect(screen.getByText(/within 0 UTC calendar days/)).toBeInTheDocument();
});
it('rejects malformed, contradictory or excessive metadata instead of showing a false badge', () => {
  const valid={mode:'missing_excerpts',model_invoked:false,semantic_truth_verified:false};
  for (const value of [null,{}, {...valid,mode:'verified'}, {...valid,mode:['missing_excerpts']},
    {...valid,model_invoked:'false'}, {...valid,model_invoked:true}, {...valid,semantic_truth_verified:true},
    {...valid,source_count:0}, {...valid,source_count:13}, {...valid,source_count:1.5},
    {...valid,date_window_days:-1}, {...valid,date_window_days:'7'}, {...valid,date_window_days:3651}]) {
    expect(parseResearchAnswer(value)).toBeUndefined();
    const {container}=render(<ShyResearchContext value={value}/>);
    expect(container).toBeEmptyDOMElement();cleanup();
  }
});

it.each([
  ['english_hint','English'],['french_hint','French'],['haitian_creole_hint','Haitian Creole'],['mixed_hint','multiple languages'],
])('shows the recorded %s rule without guessing language quality', (basis,label) => {
  const value={mode:'missing_recent_evidence',model_invoked:false,semantic_truth_verified:false,date_window_days:7,date_window_basis:basis};
  expect(parseResearchAnswer(value)?.date_window_basis).toBe(basis);
  render(<ShyResearchContext value={value}/>);
  expect(screen.getByText(new RegExp(label))).toBeInTheDocument();
  expect(screen.getByText(/do not interpret negation/)).toBeInTheDocument();
});
it('does not attribute older windows to a language and rejects contradictory rule metadata', () => {
  const value={mode:'missing_recent_evidence',model_invoked:false,semantic_truth_verified:false,date_window_days:7};
  render(<ShyResearchContext value={value}/>);
  expect(screen.getByText(/origin of this date window was not recorded/)).toBeInTheDocument();
  for (const invalid of [{...value,date_window_basis:'no_window'},{...value,date_window_basis:'french_hint',date_window_days:null},{...value,date_window_basis:'haitian_creole_hint',date_window_days:30},{...value,date_window_basis:'language_detected'}]) expect(parseResearchAnswer(invalid)).toBeUndefined();
  expect(parseResearchAnswer({...value,date_window_days:null,date_window_basis:'no_window'})?.date_window_basis).toBe('no_window');
});
