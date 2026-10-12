const publicMessages = new Set([
  'SHY is already answering another cloud request. Please wait for it to finish.',
  'The cloud model did not finish starting or answering in time. Please try again.',
  'Hosted intelligence is temporarily unavailable. Please try again shortly.',
  'Local intelligence unavailable.',
]);

export function safeAgentFailure(body: string) {
  let reason = 'SHY is temporarily unavailable. Please try again.';
  try {
    const payload: unknown = body.length <= 4096 ? JSON.parse(body) : null;
    if (payload && typeof payload === 'object' && 'detail' in payload &&
        typeof payload.detail === 'string' && publicMessages.has(payload.detail)) {
      reason = payload.detail;
    }
  } catch { /* Never reflect arbitrary upstream errors or credentials. */ }
  return { assistant: 'SHY', status: 'FAILED', reason };
}
