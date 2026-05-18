import type {
  Bid,
  ComparisonMatrix,
  ComparisonRow,
  ComparisonCell,
  Vendor,
  BidLineItem,
} from "@procurement/db";

interface BuildInput {
  bids: Array<Bid & { vendor: Vendor }>;
}

// Builds a normalized matrix where rows are grouped by description (fuzzy
// matched on a normalized key). Cells are populated per (row, vendor).
// Totals + flags are computed in TS for predictability.
export function buildComparisonMatrix({ bids }: BuildInput): ComparisonMatrix {
  const vendors = bids.map((b) => ({
    id: b.vendorId,
    name: b.vendor.name,
    bidId: b.id,
  }));

  // Group line items across bids by a normalized description key.
  // Lines from the same bid with the same key get suffixed so they don't merge.
  const groups = new Map<
    string,
    {
      canonicalDescription: string;
      category: "base" | "alternate" | "allowance" | "exclusion";
      cellsByVendor: Map<string, ComparisonCell>;
    }
  >();

  for (const b of bids) {
    const perBidKeyCount = new Map<string, number>();
    for (const li of b.lineItems) {
      const baseKey = `${li.category}::${normalize(li.description)}`;
      const seen = perBidKeyCount.get(baseKey) ?? 0;
      perBidKeyCount.set(baseKey, seen + 1);
      const key = seen === 0 ? baseKey : `${baseKey}::${seen}`;
      const cell: ComparisonCell = {
        bidLineItemId: li.id,
        documentId: b.documentId,
        unitPrice: li.unitPrice,
        extended: li.extended,
        notes: li.notes,
        source: li.source,
      };
      const existing = groups.get(key);
      if (existing) {
        existing.cellsByVendor.set(b.vendorId, cell);
      } else {
        const g = {
          canonicalDescription: li.description.trim(),
          category: li.category,
          cellsByVendor: new Map<string, ComparisonCell>(),
        };
        g.cellsByVendor.set(b.vendorId, cell);
        groups.set(key, g);
      }
    }
  }

  const rows: ComparisonRow[] = [...groups.values()].map((g, idx) => {
    const cells: Record<string, ComparisonCell | null> = {};
    for (const v of vendors) {
      cells[v.id] = g.cellsByVendor.get(v.id) ?? null;
    }
    return {
      id: `r${idx}`,
      canonicalDescription: g.canonicalDescription,
      category: g.category,
      cells,
    };
  });

  // Stable ordering: base first, then alternate, allowance, exclusion.
  rows.sort((a, b) => {
    const order = { base: 0, alternate: 1, allowance: 2, exclusion: 3 };
    if (order[a.category] !== order[b.category]) {
      return order[a.category] - order[b.category];
    }
    return a.canonicalDescription.localeCompare(b.canonicalDescription);
  });

  // Totals per vendor. baseTotal in DB is already cents; lineItem.extended is
  // dollars (whatever the extractor said). Keep totals in cents end-to-end.
  const totals: ComparisonMatrix["totals"] = {};
  for (const b of bids) {
    const baseCents =
      b.baseTotal ?? Math.round(sumBy(b.lineItems, "base") * 100);
    const alternatesCents = Math.round(sumBy(b.lineItems, "alternate") * 100);
    totals[b.vendorId] = {
      baseCents,
      alternatesCents,
      leadTimeWeeks: b.leadTimeWeeks,
    };
  }

  const flags: ComparisonMatrix["flags"] = [];
  for (const row of rows) {
    const filled = vendors
      .map((v) => ({ vendorId: v.id, cell: row.cells[v.id] }))
      .filter((c) => c.cell !== null);
    // Missing-bid flag for base items where some vendors didn't quote.
    if (row.category === "base" && filled.length > 0 && filled.length < vendors.length) {
      for (const v of vendors) {
        if (!row.cells[v.id]) {
          flags.push({
            rowId: row.id,
            vendorId: v.id,
            kind: "missing",
            note: `${v.name} did not quote "${row.canonicalDescription}"`,
          });
        }
      }
    }
    if (row.category === "exclusion") {
      for (const c of filled) {
        const name = vendors.find((v) => v.id === c.vendorId)?.name ?? c.vendorId;
        flags.push({
          rowId: row.id,
          vendorId: c.vendorId,
          kind: "exclusion",
          note: `${name} explicitly excludes "${row.canonicalDescription}"`,
        });
      }
    }
    // Outlier: extended > 1.5x median or < 0.5x median across vendors that quoted.
    const extendedVals = filled
      .map((c) => c.cell?.extended)
      .filter((n): n is number => typeof n === "number" && Number.isFinite(n));
    if (extendedVals.length >= 2) {
      const median = quickMedian(extendedVals);
      for (const c of filled) {
        const x = c.cell?.extended;
        if (typeof x !== "number" || !Number.isFinite(x)) continue;
        if (x > median * 1.5 || x < median * 0.5) {
          const name = vendors.find((v) => v.id === c.vendorId)?.name ?? c.vendorId;
          flags.push({
            rowId: row.id,
            vendorId: c.vendorId,
            kind: "outlier",
            note: `${name}: ${formatMoney(x)} vs median ${formatMoney(median)} for "${row.canonicalDescription}"`,
          });
        }
      }
    }
  }

  return { vendors, rows, totals, flags };
}

function normalize(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sumBy(items: BidLineItem[], category: BidLineItem["category"]): number {
  return items
    .filter((i) => i.category === category)
    .reduce((acc, i) => acc + (i.extended ?? 0), 0);
}

function quickMedian(xs: number[]): number {
  const sorted = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1]! + sorted[mid]!) / 2
    : sorted[mid]!;
}

function formatMoney(n: number): string {
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
