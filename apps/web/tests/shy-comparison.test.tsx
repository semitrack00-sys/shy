import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ShyComparison } from '@/components/shy-comparison';
import { buildAgentRequest } from '@/lib/shy-api';
afterEach(cleanup);
function fill(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
it('submits explicit criteria and numeric values through the ordinary chat body', () => {
  const onCompare=vi.fn();render(<ShyComparison disabled={false} onCompare={onCompare}/>);
  fill('Criterion 1 name','Cost');fill('Criterion 1 unit','USD');fill('Criterion 1 weight','3');
  fill('Option 1 name','A');fill('Option 2 name','B');fill('Option 1 criterion 1 value','100');fill('Option 2 criterion 1 value','200');
  fireEvent.click(screen.getByText('Calculate comparison'));
  expect(onCompare).toHaveBeenCalledOnce();
  const data=onCompare.mock.calls[0][0];
  expect(data.criteria[0]).toEqual({id:'c1',name:'Cost',unit:'USD',weight:'3',direction:'minimize'});
  expect(buildAgentRequest('Compare',null,0,'UTC','my-project',data).option_comparison).toEqual(data);
  expect(buildAgentRequest('Ordinary')).not.toHaveProperty('option_comparison');
});
it('does not submit invalid weights or nondecimal values', () => {
  const onCompare=vi.fn();render(<ShyComparison disabled={false} onCompare={onCompare}/>);
  fill('Criterion 1 name','Cost');fill('Option 1 name','A');fill('Option 2 name','B');
  fill('Option 1 criterion 1 value','NaN');fill('Option 2 criterion 1 value','1');
  fireEvent.click(screen.getByText('Calculate comparison'));expect(onCompare).not.toHaveBeenCalled();expect(screen.getByRole('alert')).toBeInTheDocument();
  fill('Option 1 criterion 1 value','0');fill('Criterion 1 weight','0');
  fireEvent.click(screen.getByText('Calculate comparison'));expect(onCompare).not.toHaveBeenCalled();
});
it('bounds additions and keeps removed criteria out of submitted values', () => {
  const onCompare=vi.fn();render(<ShyComparison disabled={false} onCompare={onCompare}/>);
  for(let i=0;i<5;i++)fireEvent.click(screen.getByText('Add criterion'));
  expect(screen.getByText('Add criterion')).toBeDisabled();
  for(let i=0;i<5;i++)fireEvent.click(screen.getByText('Remove last criterion'));
  expect(screen.getByText('Remove last criterion')).toBeDisabled();
  for(let i=0;i<6;i++)fireEvent.click(screen.getByText('Add option'));
  expect(screen.getByText('Add option')).toBeDisabled();
});
it('disables edits and submission while chat is busy', () => {
  render(<ShyComparison disabled onCompare={vi.fn()}/>);
  expect(screen.getByText('Calculate comparison')).toBeDisabled();expect(screen.getByLabelText('Criterion 1 name')).toBeDisabled();
});
