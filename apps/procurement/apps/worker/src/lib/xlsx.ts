import ExcelJS from "exceljs";

export interface XlsxSheet {
  page: number; // We treat each sheet as a "page" so the citation model is uniform.
  text: string;
}

export interface XlsxParseResult {
  pages: XlsxSheet[];
  pageCount: number;
}

export async function parseXlsx(buf: Buffer): Promise<XlsxParseResult> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.load(buf);
  const pages: XlsxSheet[] = [];
  let idx = 0;
  wb.eachSheet((sheet) => {
    idx++;
    const lines: string[] = [`# Sheet: ${sheet.name}`];
    sheet.eachRow({ includeEmpty: false }, (row) => {
      const cells: string[] = [];
      row.eachCell({ includeEmpty: true }, (cell) => {
        cells.push(cellValue(cell));
      });
      lines.push(cells.join("\t"));
    });
    pages.push({ page: idx, text: lines.join("\n") });
  });
  return { pages, pageCount: pages.length };
}

function cellValue(cell: ExcelJS.Cell): string {
  const v = cell.value;
  if (v == null) return "";
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return String(v);
  if (v instanceof Date) return v.toISOString();
  if (typeof v === "object" && "richText" in v && Array.isArray(v.richText)) {
    return v.richText.map((rt: { text: string }) => rt.text).join("");
  }
  if (typeof v === "object" && "result" in v) {
    return String((v as { result: unknown }).result ?? "");
  }
  return String(v);
}
