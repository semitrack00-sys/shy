'use client';

import Image from 'next/image';
import React, { useState } from 'react';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'transcribing' | 'unavailable';
const labels: Record<AvatarState, string> = {
  idle: 'Ready', listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking',
  transcribing: 'Transcribing', unavailable: 'Voice needs attention',
};

export function ShyAvatar({ size = 'small', state = 'idle', caption = false }: {
  size?: 'small' | 'header' | 'welcome' | 'voice'; state?: AvatarState; caption?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  return <figure className={`shy-avatar shy-avatar--${size}`} data-state={state}>
    <div className="shy-avatar-frame">
      {failed ? <span className="shy-avatar-fallback" aria-label={caption ? 'SHY AI avatar' : undefined} aria-hidden={!caption}>S</span>
        : <Image src="/shy-avatar-v1.webp" width={640} height={640} unoptimized
            alt={caption ? 'SHY’s AI avatar, a young Black man with a friendly smile' : ''}
            className="shy-avatar-image" onError={() => setFailed(true)} />}
    </div>
    {caption && <figcaption>
      <span className="shy-avatar-disclosure">AI avatar</span>
      <span className="shy-avatar-presence" role="status"><i aria-hidden="true" />{labels[state]}</span>
    </figcaption>}
  </figure>;
}
