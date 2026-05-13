"use client";
import Link from "next/link";
import { trpc } from "@/lib/trpc";

const STATUS_COLOR: Record<string, string> = {
  uploaded: "bg-slate-200 text-slate-700",
  scanning: "bg-amber-100 text-amber-800",
  parsing: "bg-amber-100 text-amber-800",
  parsed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function DocumentList({ projectId }: { projectId: string }) {
  const docs = trpc.document.list.useQuery(
    { projectId },
    { refetchInterval: (q) => {
        const data = q.state.data;
        const pending = data?.some((d) => d.status === "scanning" || d.status === "parsing");
        return pending ? 2_000 : false;
      },
    },
  );

  if (docs.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!docs.data?.length) {
    return (
      <p className="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
        No documents yet. Upload a PDF spec, addendum, or bid to get started.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
      {docs.data.map((d) => (
        <li key={d.id} className="flex items-center justify-between p-3">
          <Link
            href={`/projects/${projectId}/documents/${d.id}`}
            className="min-w-0 flex-1"
          >
            <p className="truncate text-sm font-medium hover:underline">{d.title}</p>
            <p className="text-xs text-slate-500">
              {d.kind} · {Math.round(d.sizeBytes / 1024)} KB
              {d.pageCount ? ` · ${d.pageCount} pages` : ""}
            </p>
          </Link>
          <span
            className={`ml-3 rounded px-2 py-0.5 text-xs ${STATUS_COLOR[d.status] ?? "bg-slate-200"}`}
            title={d.parseError ?? ""}
          >
            {d.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
