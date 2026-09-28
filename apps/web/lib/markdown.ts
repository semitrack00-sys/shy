const urlRegex = /https?:\/\/[\w\-./?%&=#+,:;@~]*[\w\-/#?%&=+]/gi;

export function toSafeExternalUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

export function splitMarkdownBlocks(text: string): string[] {
  return text
    .replace(/\r\n/g, '\n')
    .trim()
    .split(/\n{2,}/)
    .filter(Boolean);
}

export function isListBlock(block: string): boolean {
  return /^(?:[-*]\s|\d+\.\s)/m.test(block);
}

export function renderInlineMarkdown(text: string): Array<{ type: string; value: string; href?: string }> {
  const tokens: Array<{ type: string; value: string; href?: string }> = [];
  let cursor = 0;

  while (cursor < text.length) {
    const urlMatch = urlRegex.exec(text);
    if (!urlMatch) break;
    if (urlMatch.index > cursor) {
      tokens.push({ type: 'text', value: text.slice(cursor, urlMatch.index) });
    }
    const safe = toSafeExternalUrl(urlMatch[0]);
    if (safe) {
      tokens.push({ type: 'link', value: urlMatch[0], href: safe });
    } else {
      tokens.push({ type: 'text', value: urlMatch[0] });
    }
    cursor = urlMatch.index + urlMatch[0].length;
  }

  if (cursor < text.length) {
    tokens.push({ type: 'text', value: text.slice(cursor) });
  }

  if (tokens.length === 0) {
    return [{ type: 'text', value: text }];
  }

  return tokens;
}