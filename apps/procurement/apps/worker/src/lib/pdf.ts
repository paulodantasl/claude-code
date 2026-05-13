import pdfParse from "pdf-parse";

export interface PdfPage {
  page: number;
  text: string;
}

export interface PdfParseResult {
  pages: PdfPage[];
  pageCount: number;
}

// pdf-parse's `pagerender` hook is invoked per page in sequence. We track
// page numbers with an external counter because the proxy object's shape
// differs between pdfjs versions (some expose `pageNumber`, some `_pageIndex`).
export async function parsePdf(buf: Buffer): Promise<PdfParseResult> {
  const pages: PdfPage[] = [];
  let cursor = 0;
  await pdfParse(buf, {
    pagerender: async (pageData: {
      getTextContent: (opts?: unknown) => Promise<{ items: Array<{ str: string }> }>;
    }) => {
      cursor += 1;
      const content = await pageData.getTextContent({
        normalizeWhitespace: false,
        disableCombineTextItems: false,
      });
      const text = content.items
        .map((it) => it.str)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      pages.push({ page: cursor, text });
      return text;
    },
  });
  return { pages, pageCount: pages.length };
}
