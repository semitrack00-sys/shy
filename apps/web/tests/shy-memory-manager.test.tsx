import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ShyMemoryManager } from '@/components/shy-memory-manager';

const row = { id: '00000000-0000-0000-0000-000000000002', category: 'PROJECT', subject_key: 'project.shy.database',
  content: 'SHY uses PostgreSQL.', status: 'ACTIVE', revision: 'a'.repeat(64) };
const list = { records: [row], has_more: false, page: 0 };
const success = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('reviewed memory controls', () => {
  it('saves an explicit fact only with the reviewed subject, category and content', async () => {
    const fetcher = vi.fn().mockResolvedValue(success(list)); vi.stubGlobal('fetch', fetcher);
    render(<ShyMemoryManager />);
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' })); await screen.findByText(row.content);
    fireEvent.click(screen.getByRole('button', { name: 'Remember this' }));
    fireEvent.change(screen.getByLabelText('Memory subject'), { target: { value: 'user.company' } });
    fireEvent.change(screen.getByLabelText('Memory content'), { target: { value: 'My company is GUD Express LLC.' } });
    expect(screen.getByRole('button', { name: 'Save reviewed memory' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText('I reviewed this exact memory change and confirm it.'));
    fireEvent.click(screen.getByRole('button', { name: 'Save reviewed memory' }));
    await screen.findByText('Saved memory updated.');
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ subject_key: 'user.company', category: 'USER_FACT',
      content: 'My company is GUD Express LLC.', confirmed: true });
  });
  it('fetches only after the user opens saved memories and sends no mutation before review', async () => {
    const fetcher = vi.fn().mockResolvedValue(success(list)); vi.stubGlobal('fetch', fetcher);
    render(<ShyMemoryManager />); expect(fetcher).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' }));
    await screen.findByText(row.content);
    fireEvent.click(screen.getByRole('button', { name: 'Correct project.shy.database' }));
    fireEvent.change(screen.getByLabelText('Memory content'), { target: { value: 'SHY uses SQLite.' } });
    expect(screen.getByRole('button', { name: 'Save reviewed memory' })).toBeDisabled();
    expect(fetcher).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByLabelText('I reviewed this exact memory change and confirm it.'));
    fireEvent.change(screen.getByLabelText('Memory content'), { target: { value: 'SHY uses PostgreSQL 16.' } });
    expect(screen.getByRole('button', { name: 'Save reviewed memory' })).toBeDisabled();
  });

  it('corrects with the reviewed revision and refreshes the persistent record', async () => {
    const fetcher = vi.fn().mockResolvedValue(success(list)); vi.stubGlobal('fetch', fetcher);
    render(<ShyMemoryManager />);
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' })); await screen.findByText(row.content);
    fireEvent.click(screen.getByRole('button', { name: 'Correct project.shy.database' }));
    fireEvent.change(screen.getByLabelText('Memory content'), { target: { value: 'Reviewed correction' } });
    fireEvent.click(screen.getByLabelText('I reviewed this exact memory change and confirm it.'));
    fireEvent.click(screen.getByRole('button', { name: 'Save reviewed memory' }));
    await screen.findByText('Saved memory updated.');
    const options = fetcher.mock.calls[1][1];
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body)).toEqual({ content: 'Reviewed correction', expected_revision: row.revision, confirmed: true });
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it('requires separate confirmation for deletion and explains retained chat history', async () => {
    const fetcher = vi.fn().mockResolvedValue(success(list)); vi.stubGlobal('fetch', fetcher);
    render(<ShyMemoryManager />);
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' })); await screen.findByText(row.content);
    fireEvent.click(screen.getByRole('button', { name: 'Delete project.shy.database' }));
    expect(screen.getByRole('button', { name: 'Confirm deletion' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText('I reviewed this exact memory change and confirm it.'));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }));
    await screen.findByText('Selected saved memory deleted. Original chat history remains.');
    expect(fetcher.mock.calls[1][0]).toBe(`/api/shy/memories/${row.id}/delete`);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ expected_revision: row.revision, confirmed: true });
  });

  it('handles a stale revision without retrying or retaining approval', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(success(list)).mockResolvedValueOnce({ ok: false, status: 409, json: async () => ({}) });
    vi.stubGlobal('fetch', fetcher); render(<ShyMemoryManager />);
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' })); await screen.findByText(row.content);
    fireEvent.click(screen.getByRole('button', { name: 'Delete project.shy.database' }));
    fireEvent.click(screen.getByLabelText('I reviewed this exact memory change and confirm it.'));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm deletion' }));
    await screen.findByText(/This memory changed/);
    expect(screen.getByRole('button', { name: 'Confirm deletion' })).toBeDisabled();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('cancels an in-flight list request when settings close', async () => {
    const fetcher = vi.fn().mockImplementation(() => new Promise(() => {})); vi.stubGlobal('fetch', fetcher);
    const { unmount } = render(<ShyMemoryManager />);
    fireEvent.click(screen.getByRole('button', { name: 'Review saved memories' }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
    const signal = fetcher.mock.calls[0][1].signal;
    unmount(); expect(signal.aborted).toBe(true);
  });
});
