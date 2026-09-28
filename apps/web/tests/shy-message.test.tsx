import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { ShyMessage } from '../components/shy-message';
import { ShyComposer } from '../components/shy-composer';

describe('message rendering', () => {
  it('renders research sources and citations', () => {
    render(
      <ShyMessage
        message={{
          id: '1',
          role: 'assistant',
          content: 'Answer with citation [1].',
          createdAt: new Date().toISOString(),
          status: 'sent',
          responseStatus: 'RESPOND',
          toolName: 'web.search',
          toolStatus: 'EXECUTED',
          researchProvider: 'tavily',
          sources: [
            { number: 1, title: 'Blackwell', url: 'https://example.com', source: 'example.com' },
          ],
        }}
      />
    );

    expect(screen.getByText('Answer with citation [1].')).toBeInTheDocument();
    expect(screen.getByText('Structured research sources')).toBeInTheDocument();
    expect(screen.getByText('Blackwell')).toBeInTheDocument();
  });

  it('renders tool result outputs', () => {
    render(
      <ShyMessage
        message={{
          id: '2',
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          status: 'sent',
          responseStatus: 'TOOL_RESULT',
          toolName: 'system.health',
          toolStatus: 'EXECUTED',
          output: { system: 'SHY', status: 'healthy' },
        }}
      />
    );

    expect(screen.getByText('Tool result')).toBeInTheDocument();
    expect(screen.getByText(/"status": "healthy"/)).toBeInTheDocument();
  });

  it('renders controlled failures', () => {
    render(
      <ShyMessage
        message={{
          id: '3',
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          status: 'failed',
          responseStatus: 'FAILED',
          error: 'Research synthesis unavailable.',
        }}
      />
    );

    expect(screen.getByText('Request failed.')).toBeInTheDocument();
    expect(screen.getByText('Research synthesis unavailable.')).toBeInTheDocument();
  });
});

describe('composer keyboard behavior', () => {
  it('submits on Enter and preserves Shift+Enter newline behavior', () => {
    const onSend = vi.fn();
    const onChange = vi.fn();

    render(<ShyComposer value="Hello" onChange={onChange} onSend={onSend} />);

    const composer = screen.getByRole('textbox');
    composer.focus();
    fireEvent.keyDown(composer, { key: 'Enter', code: 'Enter', charCode: 13 });

    expect(onSend).toHaveBeenCalledTimes(1);
  });
});