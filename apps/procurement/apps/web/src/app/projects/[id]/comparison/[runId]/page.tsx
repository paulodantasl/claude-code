"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { trpc } from "@/lib/trpc";
import { CitationChip } from "@/components/CitationChip";

export default function ComparisonPage() {
  const params = useParams<{ id: string; runId: string }>();
  const projectId = params.id;
  const runId = params.runId;
  const runQ = trpc.comparison.get.useQuery({ projectId, runId });

  if (runQ.isLoading) return <main className="p-10">Loading…</main>;
  if (!runQ.data) return <main className="p-10">Not found.</main>;
  const { matrix, title, assumptions, createdAt } = runQ.data;

  const flagsByRow = new Map<string, typeof matrix.flags>();
  for (const f of matrix.flags) {
    const arr = flagsByRow.get(f.rowId) ?? [];
    arr.push(f);
    flagsByRow.set(f.rowId, arr);
  }

  return (
    <main className="mx-auto max-w-[1400px] p-6">
      <Link href={`/projects/${projectId}`} className="text-sm text-slate-500 hover:underline">
        ← Project
      </Link>
      <h1 className="mt-1 text-2xl font-semibold">{title}</h1>
      <p className="text-xs text-slate-500">
        Immutable snapshot · created {new Date(createdAt).toLocaleString()}
      </p>

      <section className="mt-4">
        <h2 className="text-sm font-semibold">Totals</h2>
        <table className="mt-2 w-full table-auto border border-slate-200 bg-white text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-600">
            <tr>
              <th className="border-b border-slate-200 px-2 py-1 text-left">Vendor</th>
              <th className="border-b border-slate-200 px-2 py-1 text-right">Base bid</th>
              <th className="border-b border-slate-200 px-2 py-1 text-right">Alternates (net)</th>
              <th className="border-b border-slate-200 px-2 py-1 text-right">Lead time (wk)</th>
            </tr>
          </thead>
          <tbody>
            {matrix.vendors.map((v) => {
              const t = matrix.totals[v.id];
              return (
                <tr key={v.id}>
                  <td className="border-b border-slate-100 px-2 py-1">{v.name}</td>
                  <td className="border-b border-slate-100 px-2 py-1 text-right">
                    {moneyCents(t?.baseCents)}
                  </td>
                  <td className="border-b border-slate-100 px-2 py-1 text-right">
                    {moneyCents(t?.alternatesCents)}
                  </td>
                  <td className="border-b border-slate-100 px-2 py-1 text-right">
                    {t?.leadTimeWeeks ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="mt-6 overflow-x-auto">
        <h2 className="text-sm font-semibold">Line-item matrix</h2>
        <table className="mt-2 w-full table-fixed border border-slate-200 bg-white text-xs">
          <thead className="bg-slate-50 uppercase text-slate-600">
            <tr>
              <th className="w-12 border-b border-slate-200 px-2 py-1 text-left">Cat</th>
              <th className="w-[36ch] border-b border-slate-200 px-2 py-1 text-left">Line</th>
              {matrix.vendors.map((v) => (
                <th
                  key={v.id}
                  className="border-b border-l border-slate-200 px-2 py-1 text-right"
                >
                  {v.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => (
              <tr key={row.id} className="align-top">
                <td className="border-b border-slate-100 px-2 py-1 text-slate-500">
                  {row.category}
                </td>
                <td className="border-b border-slate-100 px-2 py-1">
                  <p>{row.canonicalDescription}</p>
                  {flagsByRow.get(row.id)?.map((f, i) => (
                    <p
                      key={i}
                      className={`mt-0.5 text-[10px] ${
                        f.kind === "outlier"
                          ? "text-amber-700"
                          : f.kind === "missing"
                            ? "text-slate-500"
                            : "text-red-700"
                      }`}
                    >
                      ⚑ {f.note}
                    </p>
                  ))}
                </td>
                {matrix.vendors.map((v) => {
                  const cell = row.cells[v.id];
                  if (!cell)
                    return (
                      <td
                        key={v.id}
                        className="border-b border-l border-slate-100 px-2 py-1 text-right text-slate-300"
                      >
                        not bid
                      </td>
                    );
                  return (
                    <td
                      key={v.id}
                      className="border-b border-l border-slate-100 px-2 py-1 text-right"
                    >
                      <p className="font-medium">{money(cell.extended)}</p>
                      {cell.unitPrice != null && (
                        <p className="text-[10px] text-slate-500">
                          @ {money(cell.unitPrice)}/u
                        </p>
                      )}
                      {cell.source && (
                        <div className="mt-1">
                          <CitationChip
                            projectId={projectId}
                            citation={{
                              documentId: cell.documentId,
                              page: cell.source.page,
                              chunkId: cell.source.chunkId,
                              snippet: cell.source.snippet,
                            }}
                            compact
                          />
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold">Assumptions</h2>
        <ul className="mt-2 list-disc pl-5 text-xs text-slate-600">
          {assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function money(n: number | null | undefined): string {
  if (n == null) return "—";
  return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function moneyCents(c: number | null | undefined): string {
  if (c == null) return "—";
  return money(c / 100);
}
