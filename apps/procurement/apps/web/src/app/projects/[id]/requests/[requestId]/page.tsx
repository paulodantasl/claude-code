"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
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

const ARTIFACT_HREF: Record<string, (id: string, projectId: string) => string> = {
  package: (id, p) => `/projects/${p}/packages/${id}`,
  rfq_draft: (id, p) => `/projects/${p}/rfq/${id}`,
  rfq_version: (id, p) => `/projects/${p}/rfq/${id}`,
  comparison_run: (id, p) => `/projects/${p}/comparison/${id}`,
  rfq_export: (id, p) => `/projects/${p}`,
};

export default function RequestPage() {
  const params = useParams<{ id: string; requestId: string }>();
  const projectId = params.id;
  const requestId = params.requestId;
  const utils = trpc.useUtils();
  const q = trpc.request.get.useQuery({ projectId, requestId });
  const send = trpc.request.sendMessage.useMutation({
    onSuccess: () => utils.request.get.invalidate({ projectId, requestId }),
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [q.data?.messages.length, send.isPending]);

  if (q.isLoading) return <main className="p-10">Loading…</main>;
  if (!q.data) return <main className="p-10">Not found.</main>;
  const { request: r, messages } = q.data;

  return (
    <main className="mx-auto max-w-6xl p-6">
      <Link href={`/projects/${projectId}`} className="text-sm text-slate-500 hover:underline">
        ← Project
      </Link>
      <header className="mt-1 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{r.title}</h1>
          <p className="text-xs text-slate-500">
            Need:{" "}
            {r.need.quantity != null
              ? `${r.need.quantity} ${r.need.unit ?? ""}`
              : "(not yet captured)"}{" "}
            · {r.need.trade ?? "trade?"} · {r.need.deadline ?? "no deadline"}
          </p>
          {r.recommendation && (
            <p className="mt-1 text-sm text-emerald-700">★ {r.recommendation}</p>
          )}
        </div>
        <span className={`rounded px-2 py-1 text-xs ${STATUS_COLOR[r.status]}`}>
          {r.status.replace(/_/g, " ")}
        </span>
      </header>

      <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <section className="flex h-[640px] flex-col rounded border border-slate-200 bg-white">
          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`rounded p-3 text-sm ${
                  m.role === "user" ? "bg-slate-100" : "bg-brand-50/40 ring-1 ring-brand-500/10"
                }`}
              >
                <p className="mb-1 text-[10px] font-semibold uppercase text-slate-500">
                  {m.role}
                </p>
                <div className="whitespace-pre-wrap leading-relaxed">{m.content}</div>
                {m.artifacts.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {m.artifacts.map((a, i) => {
                      const href = ARTIFACT_HREF[a.kind]?.(a.id, projectId) ?? "#";
                      return (
                        <Link
                          key={i}
                          href={href}
                          className="rounded bg-white px-2 py-0.5 text-[10px] text-brand-700 ring-1 ring-brand-500/20 hover:bg-brand-50"
                        >
                          {a.kind}: {a.label}
                        </Link>
                      );
                    })}
                  </div>
                )}
                {m.actions.length > 0 && (
                  <details className="mt-2 text-[10px] text-slate-500">
                    <summary className="cursor-pointer">
                      {m.actions.length} tool action(s)
                    </summary>
                    <ul className="mt-1 ml-2 list-disc">
                      {m.actions.map((a, i) => (
                        <li key={i} className={a.ok ? "" : "text-red-600"}>
                          {a.tool}: {a.summary}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            ))}
            {send.isPending && <p className="text-xs italic text-slate-500">Thinking…</p>}
          </div>
          <form
            className="flex border-t border-slate-200"
            onSubmit={(e) => {
              e.preventDefault();
              const text = input.trim();
              if (!text) return;
              setInput("");
              send.mutate({ projectId, requestId, message: text });
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                r.status === "intake"
                  ? "Reply with quantities, specs, or anything else needed…"
                  : r.status === "awaiting_bids"
                    ? "Reply when bids are uploaded — I'll extract and compare."
                    : "Ask a follow-up or push the request forward…"
              }
              className="flex-1 px-3 py-2 text-sm outline-none disabled:opacity-50"
              disabled={send.isPending || r.status === "cancelled"}
            />
            <button
              type="submit"
              disabled={send.isPending || !input.trim() || r.status === "cancelled"}
              className="bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              Send
            </button>
          </form>
        </section>

        <aside className="space-y-3">
          <div className="rounded border border-slate-200 bg-white p-3 text-xs">
            <h2 className="font-semibold">Need</h2>
            <dl className="mt-2 space-y-1">
              <Row label="Item">{r.need.item ?? "—"}</Row>
              <Row label="Qty">
                {r.need.quantity != null
                  ? `${r.need.quantity} ${r.need.unit ?? ""}`
                  : "—"}
              </Row>
              <Row label="Trade">{r.need.trade ?? "—"}</Row>
              <Row label="Deadline">{r.need.deadline ?? "—"}</Row>
              <Row label="Specs">
                {r.need.specs.length === 0
                  ? "—"
                  : (
                      <ul className="list-disc pl-4">
                        {r.need.specs.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    )}
              </Row>
            </dl>
          </div>
          <div className="rounded border border-slate-200 bg-white p-3 text-xs">
            <h2 className="font-semibold">Artifacts</h2>
            <ul className="mt-2 space-y-1">
              {r.packageId && (
                <li>
                  <Link
                    href={`/projects/${projectId}/packages/${r.packageId}`}
                    className="text-brand-700 hover:underline"
                  >
                    Package →
                  </Link>
                </li>
              )}
              {r.rfqDraftId && (
                <li>
                  <Link
                    href={`/projects/${projectId}/rfq/${r.rfqDraftId}`}
                    className="text-brand-700 hover:underline"
                  >
                    RFQ draft →
                  </Link>
                </li>
              )}
              {r.comparisonRunId && (
                <li>
                  <Link
                    href={`/projects/${projectId}/comparison/${r.comparisonRunId}`}
                    className="text-brand-700 hover:underline"
                  >
                    Comparison →
                  </Link>
                </li>
              )}
              {!r.packageId && !r.rfqDraftId && !r.comparisonRunId && (
                <li className="text-slate-500">No artifacts yet.</li>
              )}
            </ul>
          </div>
        </aside>
      </div>
    </main>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <dt className="w-16 text-slate-500">{label}</dt>
      <dd className="flex-1">{children}</dd>
    </div>
  );
}
