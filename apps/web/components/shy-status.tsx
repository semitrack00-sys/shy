'use client';

import React from 'react';
import type { ShyHealthResponse } from '@/lib/types';

interface ShyStatusProps {
  health: ShyHealthResponse | null;
  loading: boolean;
}

export function ShyStatus({ health, loading }: ShyStatusProps) {
  return (
    <section className="shy-sidebar-section shy-status-panel" aria-label="System status">
      <div>
        <p className="shy-section-label">Status</p>
        <h3>SHY</h3>
      </div>
      <div className="shy-status-grid">
        <div className="shy-status-row">
          <span>Core version</span>
          <strong>{health?.version ?? (loading ? 'Loading…' : '—')}</strong>
        </div>
        <div className="shy-status-row">
          <span>Model</span>
          <strong>{health?.active_model ?? health?.local_model ?? '—'}</strong>
        </div>
        <div className="shy-status-row">
          <span>Inference</span>
          <strong className={health?.inference_connected ? 'shy-status-good' : 'shy-status-bad'}>
            {health?.inference_connected ? 'Connected' : loading ? 'Loading…' : 'Offline'}
          </strong>
        </div>
        <div className="shy-status-row">
          <span>Database</span>
          <strong className={health?.database_connected ? 'shy-status-good' : 'shy-status-bad'}>
            {health?.database_connected ? 'Connected' : loading ? 'Loading…' : 'Offline'}
          </strong>
        </div>
      </div>
    </section>
  );
}