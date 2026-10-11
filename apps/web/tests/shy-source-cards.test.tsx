import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ShySourceCards } from '@/components/shy-source-cards';
afterEach(cleanup);
it('displays HTTP sources without rendering unsafe or malformed links', () => {
  render(<ShySourceCards sources={[
    {number:1,title:'Public source',url:'https://example.com/source',source:''},
    {number:2,title:'Script source',url:'javascript:alert(1)',source:''},
    {number:3,title:'Malformed source',url:'not a url',source:''},
    {number:4,title:'Local file',url:'file:///etc/passwd',source:''},
  ]}/>);
  expect(screen.getAllByRole('link')).toHaveLength(1);
  expect(screen.getByRole('link')).toHaveAttribute('href', 'https://example.com/source');
  expect(screen.queryByText('Script source')).not.toBeInTheDocument();
  expect(screen.queryByText('Malformed source')).not.toBeInTheDocument();
});
it('labels provider date estimates separately from retrieval and missing dates', () => {
  render(<ShySourceCards sources={[
    {number:1,title:'Dated',url:'https://example.com/a',source:'example.com',source_date:'2026-10-10',source_date_status:'recent',retrieved_at:'2026-10-11T12:00:00Z'},
    {number:2,title:'Undated',url:'https://example.com/b',source:'example.com'},
  ]}/>);
  expect(screen.getByText('Provider date estimate: 2026-10-10 (recent)')).toBeInTheDocument();
  expect(screen.getByText('Retrieved: 2026-10-11T12:00:00Z')).toBeInTheDocument();
  expect(screen.getByText('Source date unknown')).toBeInTheDocument();
});
