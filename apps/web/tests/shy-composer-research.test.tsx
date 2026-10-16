import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ShyComposer } from '../components/shy-composer';
afterEach(cleanup);
it('suggests research without sending externally until selected, and resets after send', () => {
  const send = vi.fn();
  render(<ShyComposer value="What is the latest news?" onChange={vi.fn()} onSend={send} researchAvailable />);
  expect(screen.getByText(/This may need up-to-date/)).toBeInTheDocument();
  const checkbox = screen.getByLabelText('Search web for this answer');
  expect(checkbox).not.toBeChecked();
  fireEvent.click(screen.getByRole('button', {name:'Send'}));
  expect(send).toHaveBeenLastCalledWith(false);
  fireEvent.click(checkbox);
  fireEvent.keyDown(screen.getByLabelText('Message SHY'), {key:'Enter'});
  expect(send).toHaveBeenLastCalledWith(true);
  expect(checkbox).not.toBeChecked();
});
it('blocks oversized search on both button and keyboard while keeping ordinary chat available', () => {
  const send = vi.fn();
  render(<ShyComposer value={'x'.repeat(1001)} onChange={vi.fn()} onSend={send} researchAvailable />);
  fireEvent.click(screen.getByLabelText('Search web for this answer'));
  expect(screen.getByRole('button', {name:'Search and answer'})).toBeDisabled();
  fireEvent.keyDown(screen.getByLabelText('Message SHY'), {key:'Enter'});
  expect(send).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('Search web for this answer'));
  fireEvent.keyDown(screen.getByLabelText('Message SHY'), {key:'Enter'});
  expect(send).toHaveBeenCalledWith(false);
});
it('does not offer unavailable research', () => {
  render(<ShyComposer value="today's news" onChange={vi.fn()} onSend={vi.fn()} researchAvailable={false} />);
  expect(screen.getByLabelText('Search web for this answer')).toBeDisabled();
  expect(screen.getByText(/Web research is not configured/)).toBeInTheDocument();
});
