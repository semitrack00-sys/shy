'use client';

import React from 'react';
import { isListBlock, renderInlineMarkdown, splitMarkdownBlocks, toSafeExternalUrl } from '@/lib/markdown';

interface ShyMarkdownProps {
  content: string;
}

function renderInline(content: string) {
  return renderInlineMarkdown(content).map((token, index) => {
    if (token.type === 'link' && token.href) {
      return (
        <a key={`${token.value}-${index}`} href={token.href} target="_blank" rel="noreferrer noopener">
          {token.value}
        </a>
      );
    }

    return <span key={`${token.value}-${index}`}>{token.value}</span>;
  });
}

export function ShyMarkdown({ content }: ShyMarkdownProps) {
  const blocks = splitMarkdownBlocks(content);

  if (blocks.length === 0) {
    return null;
  }

  return (
    <div className="shy-markdown">
      {blocks.map((block, blockIndex) => {
        if (block.startsWith('```')) {
          const code = block.replace(/^```[a-zA-Z0-9_-]*\n?/, '').replace(/\n?```$/, '');
          return (
            <pre key={blockIndex}>
              <code>{code}</code>
            </pre>
          );
        }

        if (isListBlock(block)) {
          const items = block.split(/\n/).filter(Boolean);
          return (
            <ul key={blockIndex}>
              {items.map((item) => {
                const cleaned = item.replace(/^(?:[-*]|\d+\.)\s+/, '');
                const href = toSafeExternalUrl(cleaned);
                return <li key={item}>{renderInline(cleaned)}</li>;
              })}
            </ul>
          );
        }

        return <p key={blockIndex}>{renderInline(block)}</p>;
      })}
    </div>
  );
}