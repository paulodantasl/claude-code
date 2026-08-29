// Page-aware chunker. Splits a page's text into ~MAX_CHARS chunks at sentence
// boundaries where possible. Token count is approximated as chars/4.

const MAX_CHARS = 1800;
const OVERLAP = 150;

export interface PageInput {
  page: number;
  text: string;
}

export interface ChunkOutput {
  page: number;
  index: number;
  text: string;
  tokenCount: number;
}

export function chunkPages(pages: PageInput[]): ChunkOutput[] {
  const out: ChunkOutput[] = [];
  let globalIndex = 0;
  for (const p of pages) {
    const clean = normalize(p.text);
    if (!clean) continue;
    if (clean.length <= MAX_CHARS) {
      out.push({ page: p.page, index: globalIndex++, text: clean, tokenCount: estimateTokens(clean) });
      continue;
    }
    let pos = 0;
    while (pos < clean.length) {
      const end = Math.min(pos + MAX_CHARS, clean.length);
      const slice = bestBreak(clean, pos, end);
      out.push({
        page: p.page,
        index: globalIndex++,
        text: slice.text,
        tokenCount: estimateTokens(slice.text),
      });
      if (slice.nextStart <= pos) break;
      pos = slice.nextStart;
    }
  }
  return out;
}

function normalize(t: string): string {
  return t
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function bestBreak(text: string, start: number, end: number): { text: string; nextStart: number } {
  if (end >= text.length) {
    return { text: text.slice(start, end).trim(), nextStart: text.length };
  }
  // Prefer paragraph, then sentence, then space.
  const para = text.lastIndexOf("\n\n", end);
  const sentence = text.lastIndexOf(". ", end);
  const space = text.lastIndexOf(" ", end);
  const breakAt = Math.max(para > start + 200 ? para + 2 : -1, sentence > start + 200 ? sentence + 1 : -1, space > start + 200 ? space : -1);
  const cutEnd = breakAt > start ? breakAt : end;
  const piece = text.slice(start, cutEnd).trim();
  return { text: piece, nextStart: Math.max(cutEnd - OVERLAP, start + 1) };
}

function estimateTokens(s: string): number {
  return Math.ceil(s.length / 4);
}
