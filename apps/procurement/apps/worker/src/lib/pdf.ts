import pdfParse from "pdf-parse";

export interface PdfPage {
  page: number;
  text: string;
}

export interface PdfParseResult {
  pages: PdfPage[];
  pageCount: number;
}

interface PdfTextContent {
  items: Array<{ str: string }>;
}
interface PdfPageProxy {
  getTextContent: (opts?: unknown) => Promise<PdfTextContent>;
}

// pdf-parse's `pagerender` hook is invoked per page in sequence. We track
// page numbers with an external counter because the proxy object's shape
// differs between pdfjs versions (some expose `pageNumber`, some `_pageIndex`).
//
// @types/pdf-parse types `pagerender` as returning `string`, but the library
// awaits the result at runtime, so an async hook is correct. We cast the
// options to sidestep the inaccurate type.
export async function parsePdf(buf: Buffer): Promise<PdfParseResult> {
  const pages: PdfPage[] = [];
  let cursor = 0;
  const pagerender = async (pageData: PdfPageProxy): Promise<string> => {
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
  };
  await pdfParse(buf, { pagerender } as unknown as Parameters<typeof pdfParse>[1]);
  return { pages, pageCount: pages.length };
}
