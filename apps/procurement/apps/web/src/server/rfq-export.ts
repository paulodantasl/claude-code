import {
  Document,
  Packer,
  Paragraph,
  HeadingLevel,
  TextRun,
  AlignmentType,
} from "docx";
import type { FilledSection } from "@procurement/db";

interface DocxInput {
  rfqTitle: string;
  projectName: string;
  versionNumber: number;
  sections: FilledSection[];
  documentTitles: Record<string, string>;
}

// Renders a frozen RFQ version to a Word document. Citation markers
// [doc:<uuid> p<n>] in the body are converted to (Doc Name, p<n>) and a
// References appendix lists every cited document.
export async function renderRfqDocx(input: DocxInput): Promise<Buffer> {
  const allCitations = new Map<
    string,
    { documentTitle: string; pages: Set<number> }
  >();
  for (const sec of input.sections) {
    for (const c of sec.citations) {
      const e = allCitations.get(c.documentId) ?? {
        documentTitle: input.documentTitles[c.documentId] ?? `Document ${c.documentId.slice(0, 8)}`,
        pages: new Set<number>(),
      };
      e.pages.add(c.page);
      allCitations.set(c.documentId, e);
    }
  }

  const sectionChildren: Paragraph[] = [
    new Paragraph({
      heading: HeadingLevel.TITLE,
      alignment: AlignmentType.LEFT,
      children: [new TextRun({ text: input.rfqTitle, bold: true })],
    }),
    new Paragraph({
      children: [
        new TextRun({ text: `Project: ${input.projectName}`, italics: true }),
      ],
    }),
    new Paragraph({
      children: [
        new TextRun({ text: `Version: v${input.versionNumber}`, italics: true }),
      ],
    }),
    new Paragraph({ children: [new TextRun("")] }),
  ];

  for (const sec of input.sections) {
    sectionChildren.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: sec.title, bold: true })],
      }),
    );
    const rendered = renderBody(sec.body, input.documentTitles);
    for (const para of rendered) sectionChildren.push(para);
    sectionChildren.push(new Paragraph({ children: [new TextRun("")] }));
  }

  // References appendix
  if (allCitations.size > 0) {
    sectionChildren.push(
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: "References", bold: true })],
      }),
    );
    for (const [docId, entry] of allCitations) {
      const pages = [...entry.pages].sort((a, b) => a - b).join(", ");
      sectionChildren.push(
        new Paragraph({
          children: [
            new TextRun({ text: entry.documentTitle, bold: true }),
            new TextRun({ text: ` — pages ${pages} (id: ${docId})` }),
          ],
        }),
      );
    }
  }

  const doc = new Document({
    creator: "Construction Procurement Agent",
    title: input.rfqTitle,
    sections: [{ properties: {}, children: sectionChildren }],
  });

  return Packer.toBuffer(doc) as Promise<Buffer>;
}

// Splits markdown body into paragraphs and converts [doc:<uuid> p<n>] markers
// to (Document Name, p<n>) inline. List items get a • prefix; we don't try to
// fully render markdown in v1.
function renderBody(body: string, titles: Record<string, string>): Paragraph[] {
  const lines = body.split("\n");
  const paras: Paragraph[] = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      paras.push(new Paragraph({ children: [new TextRun("")] }));
      continue;
    }
    const isBullet = /^[-*]\s+/.test(line);
    const content = isBullet ? line.replace(/^[-*]\s+/, "") : line;
    const isSubHeading = /^#{2,}\s+/.test(content);
    const headingText = isSubHeading ? content.replace(/^#+\s+/, "") : null;

    const text = (headingText ?? content).replace(
      /\[doc:([0-9a-f-]{36})\s+p(\d+)\]/gi,
      (_, id: string, pg: string) => {
        const title = titles[id] ?? `Document ${id.slice(0, 8)}`;
        return ` (${title}, p${pg})`;
      },
    );

    if (headingText) {
      paras.push(
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [new TextRun({ text, bold: true })],
        }),
      );
    } else if (isBullet) {
      paras.push(
        new Paragraph({
          bullet: { level: 0 },
          children: [new TextRun(text)],
        }),
      );
    } else {
      paras.push(new Paragraph({ children: [new TextRun(text)] }));
    }
  }
  return paras;
}
