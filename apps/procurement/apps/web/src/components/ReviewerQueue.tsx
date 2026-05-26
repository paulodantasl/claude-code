"use client";
import { trpc } from "@/lib/trpc";

export function ReviewerQueue({ projectId }: { projectId: string }) {
  const utils = trpc.useUtils();
  const queue = trpc.requirement.reviewerQueue.useQuery({ projectId });
  const review = trpc.requirement.review.useMutation({
    onSuccess: () => utils.requirement.reviewerQueue.invalidate({ projectId }),
  });

  if (queue.isLoading) return <div className="p-4 text-sm text-slate-500">Loading…</div>;
  if (!queue.data?.length) {
    return (
      <div className="p-4 text-sm text-slate-500">
        Nothing awaiting review. Requirements appear here once evidence is attached
        or they&apos;re marked under review.
      </div>
    );
  }

  return (
    <ul className="max-h-[600px] divide-y divide-slate-200 overflow-y-auto">
      {queue.data.map(({ requirement: r, packageName }) => (
        <li key={r.id} className="p-3 text-sm">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{r.label}</p>
              <p className="text-[10px] text-slate-500">
                {packageName ?? "—"} · {r.artifactKind} · {r.severity}
              </p>
            </div>
            <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
              {r.status}
            </span>
          </div>
          <div className="mt-2 flex gap-2">
            <button
              className="rounded border border-emerald-300 px-2 py-0.5 text-xs text-emerald-800 hover:bg-emerald-50 disabled:opacity-50"
              disabled={review.isPending}
              onClick={() =>
                review.mutate({ projectId, requirementId: r.id, status: "approved" })
              }
            >
              Approve
            </button>
            <button
              className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-800 hover:bg-red-50 disabled:opacity-50"
              disabled={review.isPending}
              onClick={() => {
                const notes = window.prompt("Rejection reason?") ?? undefined;
                review.mutate({ projectId, requirementId: r.id, status: "rejected", notes });
              }}
            >
              Reject
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
