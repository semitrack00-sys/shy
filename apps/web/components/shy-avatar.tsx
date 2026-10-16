'use client';

import Image from 'next/image';
import React, { useState } from 'react';
import { ShyAnimatedAvatar } from './shy-animated-avatar';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'transcribing' | 'unavailable';
const labels: Record<AvatarState, string> = {
  idle: 'Ready', listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking',
  transcribing: 'Transcribing', unavailable: 'Voice needs attention',
};

export function ShyAvatar({ size = 'small', state = 'idle', caption = false, motion = true, animated = false, wave = 0 }: {
  size?: 'small' | 'header' | 'welcome' | 'voice'; state?: AvatarState; caption?: boolean; motion?: boolean; animated?: boolean; wave?: number;
}) {
  const [failed, setFailed] = useState(false);
  const [animationFailed, setAnimationFailed] = useState(false);
  const use3d = animated && size === 'voice' && !animationFailed;
  return <figure className={`shy-avatar shy-avatar--${size}${use3d ? ' shy-avatar--3d' : ''}`} data-state={state} data-motion={motion && !failed ? 'on' : 'off'}>
    <div className="shy-avatar-frame">
      {use3d ? <ShyAnimatedAvatar state={state} motion={motion} wave={wave} onUnavailable={() => setAnimationFailed(true)} /> : failed ? <span className="shy-avatar-fallback" aria-label={caption ? 'SHY AI avatar' : undefined} aria-hidden={!caption}>S</span>
        : <Image src="/shy-avatar-v1.webp" width={640} height={640} unoptimized
            alt={caption ? 'SHY’s AI avatar, a young Black man with a friendly smile' : ''}
            className="shy-avatar-image" onError={() => setFailed(true)} />}
    </div>
    {animationFailed && animated && <small>3D unavailable on this device. Showing portrait.</small>}
    {caption && <figcaption>
      <span className="shy-avatar-disclosure">AI avatar</span>
      <span className="shy-avatar-presence" role="status" hidden={size === 'welcome'}><i aria-hidden="true" />{labels[state]}</span>
    </figcaption>}
  </figure>;
}
