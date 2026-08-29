// Generates tiny synthetic fixtures so you can exercise the upload→parse→chat
// loop without committing binary blobs. Run with:
//   pnpm dlx tsx fixtures/make-fixtures.ts
// (or via the script in fixtures/README.md).

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ExcelJS from "exceljs";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "out");
mkdirSync(OUT, { recursive: true });

const pdfPath = join(OUT, "concrete-spec-excerpt.pdf");
writeFileSync(pdfPath, buildPdf());
console.log(`Wrote ${pdfPath}`);

await buildXlsx(join(OUT, "concrete-bid-vendor-a.xlsx"), {
  vendor: "Acme Concrete Inc.",
  unitPrices: { footings: 195, slab: 175, walls: 215, curing: 4500 },
  leadTime: "6 weeks from approved submittal",
});
console.log(`Wrote ${join(OUT, "concrete-bid-vendor-a.xlsx")}`);

await buildXlsx(join(OUT, "concrete-bid-vendor-b.xlsx"), {
  vendor: "Bayview Concrete Co.",
  unitPrices: { footings: 210, slab: 168, walls: 235, curing: 3900 },
  leadTime: "8 weeks from approved submittal",
});
console.log(`Wrote ${join(OUT, "concrete-bid-vendor-b.xlsx")}`);

// --- PDF (raw, single-page, monospace-ish text) ---
function buildPdf(): Buffer {
  const pages = [
    [
      "SECTION 03 30 00 - CAST-IN-PLACE CONCRETE",
      "",
      "1.1 SUMMARY",
      "A. Section Includes: Cast-in-place concrete for footings, slabs-on-grade, and walls.",
      "",
      "2.1 MATERIALS",
      "A. Cement: ASTM C150, Type I/II.",
      "B. Aggregates: ASTM C33, normal weight.",
      "C. Admixtures: ASTM C494 Type A water reducer; no calcium chloride.",
      "",
      "3.1 MIX DESIGN",
      "A. Slabs-on-grade: f'c = 4000 psi at 28 days, w/c <= 0.45, 4 inch slump +/- 1 inch.",
      "B. Walls: f'c = 4000 psi at 28 days, w/c <= 0.50, 5 inch slump +/- 1 inch.",
    ],
    [
      "SECTION 03 30 00 - CAST-IN-PLACE CONCRETE (cont.)",
      "",
      "3.2 CURING",
      "A. Cure all slabs for a minimum of 7 days using wet curing or curing compound per ASTM C309.",
      "B. Walls: cure for a minimum of 3 days prior to form removal.",
      "",
      "3.3 SUBMITTALS",
      "A. Mix design at least 14 days prior to placement.",
      "B. Manufacturer's data sheets for admixtures and curing compounds.",
      "C. Certificates of compliance for cement and aggregates.",
    ],
  ];
  return makeMinimalPdf(pages);
}

interface BidArgs {
  vendor: string;
  unitPrices: { footings: number; slab: number; walls: number; curing: number };
  leadTime: string;
}

async function buildXlsx(path: string, args: BidArgs) {
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Bid Summary");
  ws.addRow(["Vendor", args.vendor]);
  ws.addRow(["Package", "03 30 00 - Cast-in-place concrete"]);
  ws.addRow([]);
  ws.addRow(["Line Item", "Description", "Qty", "Unit", "Unit Price", "Extended"]);
  ws.addRow(["1.1", "Footings, 4000 psi", 120, "CY", args.unitPrices.footings, args.unitPrices.footings * 120]);
  ws.addRow(["1.2", "Slabs-on-grade, 4000 psi", 350, "CY", args.unitPrices.slab, args.unitPrices.slab * 350]);
  ws.addRow(["1.3", "Walls, 4000 psi", 200, "CY", args.unitPrices.walls, args.unitPrices.walls * 200]);
  ws.addRow(["2.1", "Curing compound (ASTM C309)", 1, "LS", args.unitPrices.curing, args.unitPrices.curing]);
  ws.addRow([]);
  const subtotal =
    args.unitPrices.footings * 120 +
    args.unitPrices.slab * 350 +
    args.unitPrices.walls * 200 +
    args.unitPrices.curing;
  ws.addRow(["Subtotal", "", "", "", "", subtotal]);
  ws.addRow(["Alternates", "Fly ash 20% replacement", "", "", "", -3200]);
  ws.addRow(["Exclusions", "Reinforcing steel, formwork, finishing", "", "", "", ""]);
  ws.addRow(["Lead time", args.leadTime, "", "", "", ""]);
  await wb.xlsx.writeFile(path);
}

// Minimal PDF generator (one /Page per page, plain text). Sufficient for
// pdfjs-dist to extract page-by-page text.
function makeMinimalPdf(pages: string[][]): Buffer {
  const objects: string[] = [];
  const xref: number[] = [];

  function add(obj: string): number {
    objects.push(obj);
    return objects.length;
  }

  const fontId = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>");
  const pageIds: number[] = [];
  const contentIds: number[] = [];

  for (const lines of pages) {
    const stream = ["BT", "/F1 11 Tf", "60 760 Td", "14 TL"]
      .concat(
        lines.flatMap((l) => [`(${escape(l)}) Tj`, "T*"]),
      )
      .concat(["ET"])
      .join("\n");
    const contentId = add(`<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`);
    contentIds.push(contentId);
    pageIds.push(0); // placeholder, filled below
  }

  const pagesId = add("PAGES_PLACEHOLDER");
  const actualPageIds: number[] = [];
  for (let i = 0; i < pages.length; i++) {
    const pid = add(
      `<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 ${fontId} 0 R >> >> /Contents ${contentIds[i]} 0 R >>`,
    );
    actualPageIds.push(pid);
  }
  objects[pagesId - 1] =
    `<< /Type /Pages /Kids [${actualPageIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pages.length} >>`;
  const catalogId = add(`<< /Type /Catalog /Pages ${pagesId} 0 R >>`);

  // Build the file.
  let body = "%PDF-1.4\n%\xff\xff\xff\xff\n";
  const offsets: number[] = [];
  objects.forEach((o, idx) => {
    offsets.push(Buffer.byteLength(body, "binary"));
    body += `${idx + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xrefStart = Buffer.byteLength(body, "binary");
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const off of offsets) {
    body += `${off.toString().padStart(10, "0")} 00000 n \n`;
  }
  body += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
  return Buffer.from(body, "binary");
}

function escape(s: string): string {
  return s.replace(/[\\()]/g, (m) => `\\${m}`);
}
