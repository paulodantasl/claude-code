"use client";
import { trpc } from "@/lib/trpc";

export function AuditPanel({ projectId }: { projectId: string }) {
  const audit = trpc.project.audit.useQuery({ projectId });
  if (audit.isLoading) return <p className="p-4 text-sm text-slate-500">Loading…</p>;
  if (!audit.data?.length) {
    return <p className="p-4 text-sm text-slate-500">No events yet.</p>;
  }
  return (
    <ul className="max-h-[600px] divide-y divide-slate-200 overflow-y-auto">
      {audit.data.map((e) => (
        <li key={e.id} className="p-3 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-medium">{e.action}</span>
            <time className="text-slate-500">
              {new Date(e.createdAt).toLocaleString()}
            </time>
          </div>
          {e.metadata && (
            <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-[10px] text-slate-600">
              {JSON.stringify(e.metadata, null, 2)}
            </pre>
          )}
        </li>
      ))}
    </ul>
  );
}
