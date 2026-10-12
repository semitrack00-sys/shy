'use client';

import React from 'react';
import type { ShyHealthResponse } from '@/lib/types';

interface ShyStatusProps {
  health: ShyHealthResponse | null;
  loading: boolean;
}

export function ShyStatus({ health, loading }: ShyStatusProps) {
  const hosted = health?.model_backend === 'runpod';
  const modelConnected = hosted ? health?.hosted_model_inference_verified : health?.ollama_connected;
  return (
    <section className="shy-sidebar-section shy-status-panel" aria-label="System status">
      <div>
        <p className="shy-section-label">Status</p>
        <h3>SHY</h3>
      </div>
      <div className="shy-status-grid">
        <div className="shy-status-row">
          <span>Runtime</span>
          <strong className={health?.application_healthy ? 'shy-status-good' : 'shy-status-bad'}>
            {health?.application_healthy ? 'Healthy' : loading ? 'Loading…' : 'Degraded'}
          </strong>
        </div>
        <div className="shy-status-row">
          <span>Core version</span>
          <strong>{health?.version ?? (loading ? 'Loading…' : '—')}</strong>
        </div>
        <div className="shy-status-row">
          <span>Model</span>
          <strong>{(hosted ? health?.hosted_model : health?.local_model) ?? '—'}</strong>
        </div>
        <div className="shy-status-row">
          <span>{hosted ? 'RunPod' : 'Ollama'}</span>
          <strong className={modelConnected ? 'shy-status-good' : 'shy-status-bad'}>
            {modelConnected ? 'Connected' : loading ? 'Loading…' : hosted && health?.hosted_model_configured ? 'Awaiting first response' : 'Offline'}
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
