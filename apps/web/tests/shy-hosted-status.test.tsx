import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ShyStatus } from '../components/shy-status';
import { parseShyHealthResponse } from '../lib/shy-api';

describe('hosted model status', () => {
  it('does not report configured credentials as verified inference', () => {
    const health = parseShyHealthResponse({status:'degraded', system:'SHY', version:'0.105.25',
      model_backend:'runpod', hosted_model:'qwen/qwen3.5-4b', hosted_model_configured:true,
      hosted_model_inference_verified:false, application_healthy:false, ollama_connected:false});
    render(<ShyStatus health={health} loading={false} />);
    expect(screen.getByText('RunPod')).toBeTruthy();
    expect(screen.getByText('Awaiting first response')).toBeTruthy();
    expect(screen.queryByText('Connected')).toBeNull();
    expect(screen.getByText('qwen/qwen3.5-4b')).toBeTruthy();
  });
});
