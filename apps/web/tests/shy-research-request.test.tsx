import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ShyMessage } from '@/components/shy-message';
import { ShyResearchContext } from '@/components/shy-research-context';
import { ShyResearchRequest } from '@/components/shy-research-request';
import { buildAgentRequest, parseResearchAnswer } from '@/lib/shy-api';
afterEach(cleanup);
it('submits only the reviewed question and selected date window', () => {
  const send=vi.fn();render(<ShyResearchRequest disabled={false} onResearch={send}/>);
  expect(send).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Public research question'),{target:{value:'  Istwa Ayiti  '}});
  fireEvent.change(screen.getByLabelText('Research source date window'),{target:{value:'any_date'}});
  fireEvent.click(screen.getByText('Search public web'));
  expect(send).toHaveBeenCalledWith('Istwa Ayiti',{freshness:'any_date'});
  expect(buildAgentRequest('Istwa Ayiti',null,undefined,undefined,'haiti',undefined,undefined,{freshness:'any_date'})).toEqual({message:'Istwa Ayiti',project_id:'haiti',research_request:{freshness:'any_date'}});
  expect(buildAgentRequest('ordinary')).toEqual({message:'ordinary'});
});
it('disables research while sending and resets selection when remounted', () => {
  const send=vi.fn();const {rerender}=render(<ShyResearchRequest key="one" disabled={false} onResearch={send}/>);
  fireEvent.change(screen.getByLabelText('Public research question'),{target:{value:'Question'}});
  fireEvent.change(screen.getByLabelText('Research source date window'),{target:{value:'past_month'}});
  rerender(<ShyResearchRequest key="one" disabled={true} onResearch={send}/>);
  expect(screen.getByText('Search public web')).toBeDisabled();
  fireEvent.submit(screen.getByText('Search public web').closest('form')!);expect(send).not.toHaveBeenCalled();
  rerender(<ShyResearchRequest key="two" disabled={false} onResearch={send}/>);
  expect(screen.getByLabelText('Public research question')).toHaveValue('');
  expect(screen.getByLabelText('Research source date window')).toHaveValue('auto');
});
it('accepts only valid explicit date metadata', () => {
  const base={mode:'missing_excerpts',model_invoked:false,semantic_truth_verified:false,date_window_basis:'user_selected'};
  for (const days of [null,0,7,30]) expect(parseResearchAnswer({...base,date_window_days:days})?.date_window_basis).toBe('user_selected');
  expect(parseResearchAnswer({...base,date_window_days:60})).toBeUndefined();
});

it('retains the exact research question and choice on failed retry', () => {
  const retry=vi.fn();render(<ShyMessage onRetry={retry} message={{id:'failed-research',role:'assistant',createdAt:new Date().toISOString(),content:'',status:'failed',error:'Provider unavailable',researchQuery:'Istwa Ayiti',researchRequest:{freshness:'any_date'}}}/>);
  fireEvent.click(screen.getByText('Retry'));
  expect(retry).toHaveBeenCalledWith('Istwa Ayiti',undefined,{freshness:'any_date'});
});
it('explains any-date selection without implying source freshness', () => {
  render(<ShyResearchContext value={{mode:'missing_excerpts',model_invoked:false,semantic_truth_verified:false,date_window_days:null,date_window_basis:'user_selected'}}/>);
  expect(screen.getByText('You selected any source date; older or undated excerpts may be used.')).toBeInTheDocument();
});
