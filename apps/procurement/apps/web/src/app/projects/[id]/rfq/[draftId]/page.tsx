"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { RfqSectionEditor } from "@/components/RfqSectionEditor";
import { RfqSendPanel } from "@/components/RfqSendPanel";

export default function RfqDraftPage() {
  const params = useParams<{ id: string; draftId: string }>();
  const projectId = params.id;
  const draftId = params.draftId;
  const utils = trpc.useUtils();
  const draftQ = trpc.rfq.getDraft.useQuery({ projectId, draftId });
  const projectQ = trpc.project.get.useQuery({ projectId });
  const [openSendForVersion, setOpenSendForVersion] = useState<string | null>(null);

  const saveVersion = trpc.rfq.saveVersion.useMutation({
    onSuccess: () => utils.rfq.getDraft.invalidate({ projectId, draftId }),
  });
  const exportVersion = trpc.rfq.exportVersion.useMutation();
  const [notes, setNotes] = useState("");

  if (draftQ.isLoading) return <main className="p-10">Loading…</main>;
  if (!draftQ.data) return <main className="p-10">Not found.</main>;
  const { draft, versions, template } = draftQ.data;

  return (
    <main className="mx-auto max-w-6xl p-6">
      <Link href={`/projects/${projectId}`} className="text-sm text-slate-500 hover:underline">
        ← Project
      </Link>
      <h1 className="mt-1 text-2xl font-semibold">{draft.title}</h1>
      <p className="text-sm text-slate-600">
        {template?.name} · {template?.division ?? template?.trade}
      </p>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[2.4fr_1fr]">
        <section className="space-y-4">
          {draft.currentSections.map((sec) => (
            <RfqSectionEditor
              key={sec.id}
              projectId={projectId}
              draftId={draftId}
              section={sec}
            />
          ))}
          {draft.currentSections.length === 0 && (
            <p className="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
              This draft has no sections. (Template may be empty.)
            </p>
          )}
        </section>

        <aside className="space-y-4">
          <div className="rounded border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold">Save version</h2>
            <textarea
              placeholder="Optional notes (what changed?)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="mt-2 w-full rounded border border-slate-300 px-2 py-1 text-xs"
              rows={2}
            />
            <button
              className="mt-2 w-full rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
              disabled={saveVersion.isPending}
              onClick={() => {
                saveVersion.mutate({ projectId, draftId, notes: notes || undefined });
                setNotes("");
              }}
            >
              {saveVersion.isPending ? "Saving…" : "Freeze new version"}
            </button>
          </div>

          <div className="rounded border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold">Versions</h2>
            {versions.length === 0 ? (
              <p className="mt-2 text-xs text-slate-500">
                No versions yet. Save one to enable export.
              </p>
            ) : (
              <ul className="mt-2 space-y-3">
                {versions.map((v) => (
                  <li key={v.id} className="rounded border border-slate-100 p-2 text-xs">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">v{v.versionNumber}</p>
                        <p className="text-slate-500">
                          {new Date(v.createdAt).toLocaleString()}
                        </p>
                        {v.notes && <p className="text-slate-600">{v.notes}</p>}
                      </div>
                      <div className="flex gap-1">
                        <button
                          className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50 disabled:opacity-50"
                          disabled={exportVersion.isPending}
                          onClick={async () => {
                            const out = await exportVersion.mutateAsync({
                              projectId,
                              versionId: v.id,
                              format: "docx",
                            });
                            window.open(out.url, "_blank");
                          }}
                        >
                          Export DOCX
                        </button>
                        <button
                          className="rounded bg-brand-600 px-2 py-0.5 text-white hover:bg-brand-700"
                          onClick={() =>
                            setOpenSendForVersion((cur) => (cur === v.id ? null : v.id))
                          }
                        >
                          {openSendForVersion === v.id ? "Hide" : "Send"}
                        </button>
                      </div>
                    </div>
                    {openSendForVersion === v.id && projectQ.data && (
                      <div className="mt-2">
                        <RfqSendPanel
                          projectId={projectId}
                          versionId={v.id}
                          versionNumber={v.versionNumber}
                          organizationId={projectQ.data.project.organizationId}
                        />
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
