import React from 'react';
import { fireEvent, render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ShyAvatar } from '../components/shy-avatar';
afterEach(cleanup);
it('labels the human-looking portrait as an AI avatar and falls back when its asset fails',()=>{
  render(<ShyAvatar size="welcome" caption/>);
  const portrait=screen.getByAltText('SHY’s AI avatar, a young Black man with a friendly smile');
  expect(new URL(portrait.getAttribute('src')!, 'http://localhost').pathname).toBe('/shy-avatar-v1.webp');
  expect(screen.getByText('AI avatar')).toBeInTheDocument();
  fireEvent.error(portrait);
  expect(screen.getByLabelText('SHY AI avatar')).toHaveTextContent('S');
  expect(screen.queryByRole('img')).toBeNull();
});
