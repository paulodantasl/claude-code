"use client";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { CitationChip } from "./CitationChip";

const STATUS_COLOR: Record<string, string> = {
  missing: "bg-slate-200 text-slate-700",
  received: "bg-blue-100 text-blue-800",
  under_review: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-800",
};

const SEVERITY_COLOR: Record<string, string> = {
  required: "text-red-700",
  recommended: "text-amber-700",
  optional: "text-slate-500",
};

export function CompliancePanel({
  projectId,
  packageId,
}: {
  projectId: string;
  packageId: string;
}) {
  const utils = trpc.useUtils();
  const reqs = trpc.requirement.list.useQuery({ projectId, packageId });
  const gap = trpc.requirement.gapReport.useQuery({ projectId, packageId });
  const templates = trpc.requirement.listTemplates.useQuery({ projectId });
  const docs = trpc.document.list.useQuery({ projectId });

  const invalidate = () => {
    utils.requirement.list.invalidate({ projectId, packageId });
    utils.requirement.gapReport.invalidate({ projectId, packageId });
  };
  const addFromTemplate = trpc.requirement.addFromTemplate.useMutation({ onSuccess: invalidate });
  const derive = trpc.requirement.deriveFromSpec.useMutation({ onSuccess: invalidate });
  const addManual = trpc.requirement.addManual.useMutation({ onSuccess: invalidate });

  const [templateId, setTemplateId] = useState("");
  const [manualLabel, setManualLabel] = useState("");

  return (
    <section className="mt-6 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold">Compliance checklist</h2>
        {gap.data && (
          <span className="text-xs text-slate-500">
            {gap.data.counts.approved}/{gap.data.total} approved
            {gap.data.requiredOpen > 0 && (
              <span className="ml-1 text-red-600">
                · {gap.data.requiredOpen} required open
              </span>
            )}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={templateId}
          onChange={(e) => setTemplateId(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-xs"
        >
          <option value="">Add from template…</option>
          {templates.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
        <button
          className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
          disabled={!templateId || addFromTemplate.isPending}
          onClick={() => {
            if (templateId) addFromTemplate.mutate({ projectId, packageId, templateId });
            setTemplateId("");
          }}
        >
          Add
        </button>
        <button
          className="rounded bg-brand-600 px-2 py-1 text-xs text-white hover:bg-brand-700 disabled:opacity-50"
          disabled={derive.isPending}
          onClick={() => derive.mutate({ projectId, packageId })}
        >
          {derive.isPending ? "Deriving…" : "Derive from spec (AI)"}
        </button>
      </div>
      {derive.data?.note && <p className="text-xs text-slate-500">{derive.data.note}</p>}
      {derive.error && <p className="text-xs text-red-600">{derive.error.message}</p>}

      <form
        className="flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!manualLabel) return;
          addManual.mutate({ projectId, packageId, label: manualLabel });
          setManualLabel("");
        }}
      >
        <input
          placeholder="Add requirement manually…"
          value={manualLabel}
          onChange={(e) => setManualLabel(e.target.value)}
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs"
        />
        <button
          className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
          disabled={!manualLabel || addManual.isPending}
        >
          Add
        </button>
      </form>

      {reqs.isLoading ? (
        <p className="text-xs text-slate-500">Loading…</p>
      ) : reqs.data?.length === 0 ? (
        <p className="rounded border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">
          No requirements yet. Add from a template or derive them from the spec.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {reqs.data?.map((row) => (
            <RequirementRow
              key={row.requirement.id}
              projectId={projectId}
              packageId={packageId}
              row={row}
              docs={docs.data ?? []}
              onChange={invalidate}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

type Row = {
  requirement: {
    id: string;
    label: string;
    description: string | null;
    artifactKind: string;
    severity: string;
    status: "missing" | "received" | "under_review" | "approved" | "rejected";
    sourceClause: string | null;
    sourceDocumentId: string | null;
    sourcePage: number | null;
    sourceSnippet: string | null;
    reviewerNotes: string | null;
  };
  currentFulfillment: {
    evidenceDocumentId: string;
    evidencePage: number | null;
  } | null;
};

function RequirementRow({
  projectId,
  packageId,
  row,
  docs,
  onChange,
}: {
  projectId: string;
  packageId: string;
  row: Row;
  docs: Array<{ id: string; title: string; status: string }>;
  onChange: () => void;
}) {
  const bind = trpc.requirement.bindEvidence.useMutation({ onSuccess: onChange });
  const review = trpc.requirement.review.useMutation({ onSuccess: onChange });
  const [docId, setDocId] = useState("");
  const [page, setPage] = useState("");
  const r = row.requirement;
  const parsedDocs = docs.filter((d) => d.status === "parsed");

  return (
    <li className="p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">
            {r.label}{" "}
            <span className={`text-[10px] uppercase ${SEVERITY_COLOR[r.severity]}`}>
              ({r.severity})
            </span>
          </p>
          {r.description && <p className="text-xs text-slate-600">{r.description}</p>}
          <p className="mt-0.5 text-[10px] text-slate-500">
            kind: {r.artifactKind}
            {r.sourceClause && ` · src: ${r.sourceClause}`}
          </p>
          {r.sourceDocumentId && r.sourcePage && (
            <div className="mt-1">
              <CitationChip
                projectId={projectId}
                citation={{
                  documentId: r.sourceDocumentId,
                  page: r.sourcePage,
                  chunkId: "src",
                  snippet: r.sourceSnippet ?? "",
                }}
                compact
              />
            </div>
          )}
        </div>
        <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[r.status]}`}>
          {r.status}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
        <select
          value={docId}
          onChange={(e) => setDocId(e.target.value)}
          className="rounded border border-slate-300 px-1 py-0.5 text-xs"
        >
          <option value="">Bind evidence doc…</option>
          {parsedDocs.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <input
          placeholder="page"
          value={page}
          onChange={(e) => setPage(e.target.value)}
          className="w-14 rounded border border-slate-300 px-1 py-0.5 text-xs"
        />
        <button
          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
          disabled={!docId || bind.isPending}
          onClick={() => {
            if (!docId) return;
            bind.mutate({
              projectId,
              requirementId: r.id,
              documentId: docId,
              page: page ? Number(page) : undefined,
            });
            setDocId("");
            setPage("");
          }}
        >
          Attach
        </button>

        <span className="mx-1 text-slate-300">|</span>

        <button
          className="rounded border border-amber-300 px-2 py-0.5 text-xs text-amber-800 hover:bg-amber-50 disabled:opacity-50"
          disabled={review.isPending}
          onClick={() =>
            review.mutate({ projectId, requirementId: r.id, status: "under_review" })
          }
        >
          Under review
        </button>
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
      {row.currentFulfillment && (
        <p className="mt-1 text-[10px] text-slate-500">
          Evidence attached
          {row.currentFulfillment.evidencePage
            ? ` · p${row.currentFulfillment.evidencePage}`
            : ""}
        </p>
      )}
      {r.reviewerNotes && (
        <p className="mt-1 text-[10px] text-red-700">Reviewer: {r.reviewerNotes}</p>
      )}
    </li>
  );
}
