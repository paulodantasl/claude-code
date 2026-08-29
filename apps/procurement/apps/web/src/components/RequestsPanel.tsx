"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

const STATUS_COLOR: Record<string, string> = {
  intake: "bg-slate-200 text-slate-700",
  sourcing: "bg-blue-100 text-blue-800",
  awaiting_bids: "bg-amber-100 text-amber-800",
  comparing: "bg-amber-100 text-amber-800",
  recommended: "bg-emerald-100 text-emerald-800",
  done: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-slate-200 text-slate-500",
};

const PROMPT_EXAMPLES = [
  "I need 670 cubic yards of 4000 psi concrete for slabs and walls, delivered in 6 weeks. Max w/c 0.45.",
  "Need 12 tons of structural steel framing per AISC 360, delivery in 8 weeks.",
  "1200 SF of drywall on 2nd floor, Level 4 finish, fire-rated where indicated.",
];

export function RequestsPanel({ projectId }: { projectId: string }) {
  const router = useRouter();
  const list = trpc.request.list.useQuery({ projectId });
  const utils = trpc.useUtils();
  const create = trpc.request.create.useMutation({
    onSuccess: (req) => {
      utils.request.list.invalidate({ projectId });
      router.push(`/projects/${projectId}/requests/${req.id}`);
    },
  });
  const [title, setTitle] = useState("");
  const [initial, setInitial] = useState("");

  return (
    <div className="p-4">
      <form
        className="mb-4 space-y-2 rounded border border-slate-200 bg-white p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!initial.trim()) return;
          const finalTitle = title.trim() || initial.split(/[.\n]/)[0]!.slice(0, 80);
          create.mutate({ projectId, title: finalTitle, initialMessage: initial });
        }}
      >
        <p className="text-sm font-semibold">New procurement request</p>
        <input
          placeholder="Title (optional — first sentence used if blank)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <textarea
          placeholder="Describe what you need: item, quantity, unit, deadline, any specs…"
          value={initial}
          onChange={(e) => setInitial(e.target.value)}
          rows={3}
          className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <div className="flex flex-wrap gap-1 text-[10px]">
          {PROMPT_EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="rounded border border-slate-200 px-1 py-0.5 text-slate-600 hover:bg-slate-50"
              onClick={() => setInitial(ex)}
            >
              {ex.slice(0, 50)}…
            </button>
          ))}
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={create.isPending || !initial.trim()}
            className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {create.isPending ? "Starting…" : "Start request"}
          </button>
        </div>
        {create.error && (
          <p className="text-xs text-red-600">{create.error.message}</p>
        )}
      </form>

      {list.isLoading ? (
        <p className="text-xs text-slate-500">Loading…</p>
      ) : list.data?.length === 0 ? (
        <p className="rounded border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
          No requests yet. Describe what you need above — the agent will take it from there.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {list.data?.map((r) => (
            <li key={r.id}>
              <Link
                href={`/projects/${projectId}/requests/${r.id}`}
                className="flex items-start justify-between gap-2 px-3 py-2 hover:bg-slate-50"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{r.title}</p>
                  <p className="text-[11px] text-slate-500">
                    {r.need.quantity != null && `${r.need.quantity} ${r.need.unit ?? ""} · `}
                    {r.need.trade ?? "—"} · updated {new Date(r.updatedAt).toLocaleString()}
                  </p>
                  {r.recommendation && (
                    <p className="mt-0.5 text-[11px] text-emerald-700">
                      ✓ {r.recommendation.slice(0, 120)}
                    </p>
                  )}
                </div>
                <span className={`rounded px-2 py-0.5 text-[10px] ${STATUS_COLOR[r.status]}`}>
                  {r.status.replace(/_/g, " ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
