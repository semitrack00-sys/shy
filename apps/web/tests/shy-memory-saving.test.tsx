import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ShyMemorySaving } from '@/components/shy-memory-saving';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function response(automatic_saving = true, revision = '0', status = 200) {
  return { ok: status === 200, status, json: async () => ({ automatic_saving, revision, reviewed: revision !== '0' }) };
}
it('loads only on review and requires confirmation of the exact selected setting', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response()).mockResolvedValueOnce(response(false, '1'));
  vi.stubGlobal('fetch', fetch); const user = userEvent.setup(); render(<ShyMemorySaving />);
  expect(fetch).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: 'Review automatic memory saving' }));
  const save = screen.getByRole('button', { name: 'Save memory saving setting' }); expect(save).toBeDisabled();
  await user.click(screen.getByLabelText('I confirm this automatic saving setting.'));
  await user.click(screen.getByLabelText('Allow automatic memory saving')); expect(save).toBeDisabled();
  await user.click(screen.getByLabelText('I confirm this automatic saving setting.')); await user.click(save);
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ automatic_saving: false, expected_revision: '0', confirmed: true });
  expect(await screen.findByText('Automatic memory saving paused.')).toBeInTheDocument(); expect(save).toBeDisabled();
});
it('requires a fresh review after a stale change and does not retry automatically', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response()).mockResolvedValueOnce(response(true, '1', 409));
  vi.stubGlobal('fetch', fetch); const user = userEvent.setup(); render(<ShyMemorySaving />);
  await user.click(screen.getByRole('button', { name: 'Review automatic memory saving' }));
  await user.click(screen.getByLabelText('I confirm this automatic saving setting.'));
  await user.click(screen.getByRole('button', { name: 'Save memory saving setting' }));
  expect(await screen.findByText('Setting changed. Review the current setting again.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Save memory saving setting' })).toBeNull(); expect(fetch).toHaveBeenCalledTimes(2);
});
