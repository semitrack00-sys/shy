'use client';

import React from 'react';
import { toSafeExternalUrl } from '@/lib/markdown';
import type { ShyResearchSource } from '@/lib/types';

interface ShySourceCardsProps {
  sources: ShyResearchSource[];
}

export function ShySourceCards({ sources }: ShySourceCardsProps) {
  const safeSources = sources.filter(source => toSafeExternalUrl(source.url));
  if (safeSources.length === 0) {
    return null;
  }

  return (
    <section className="shy-tool-card" aria-label="Research sources">
      <div>
        <p className="shy-section-label">Sources</p>
        <h4>Structured research sources</h4>
      </div>
      <div className="shy-sources">
        {safeSources.map((source) => (
          <article className="shy-source-card" key={source.number}>
            <p className="shy-chip">[{source.number}]</p>
            <h4>{source.title || `Source ${source.number}`}</h4>
            <p className="shy-muted">{source.source || new URL(source.url).host}</p>
            <a href={source.url} target="_blank" rel="noreferrer noopener">
              {source.url}
            </a>
          </article>
        ))}
      </div>
    </section>
  );
}
