"use client";
import { useEffect, useState } from "react";
import { trpc } from "@/lib/trpc";
import { CitationChip } from "./CitationChip";

interface Citation {
  documentId: string;
  page: number;
  chunkId: string;
  snippet: string;
}

interface SectionState {
  id: string;
  title: string;
  body: string;
  citations: Citation[];
  generatedAt: string | null;
  editedAt: string | null;
}

export function RfqSectionEditor({
  projectId,
  draftId,
  section,
}: {
  projectId: string;
  draftId: string;
  section: SectionState;
}) {
  const utils = trpc.useUtils();
  const generate = trpc.rfq.generateSection.useMutation({
    onSuccess: () => utils.rfq.getDraft.invalidate({ projectId, draftId }),
  });
  const update = trpc.rfq.updateSection.useMutation({
    onSuccess: () => utils.rfq.getDraft.invalidate({ projectId, draftId }),
  });

  const [body, setBody] = useState(section.body);
  const [editing, setEditing] = useState(false);

  // When the upstream section changes (e.g. just generated), pull it into local state.
  useEffect(() => {
    if (!editing) setBody(section.body);
  }, [section.body, editing]);

  return (
    <article className="rounded border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
        <div>
          <h3 className="text-sm font-semibold">{section.title}</h3>
          <p className="text-[10px] text-slate-500">
            {section.generatedAt
              ? `generated ${new Date(section.generatedAt).toLocaleString()}`
              : "not generated"}
            {section.editedAt && ` · edited ${new Date(section.editedAt).toLocaleString()}`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
            onClick={() =>
              generate.mutate({ projectId, draftId, sectionId: section.id })
            }
            disabled={generate.isPending}
          >
            {generate.isPending ? "Generating…" : section.body ? "Regenerate" : "Generate"}
          </button>
          <button
            className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50"
            onClick={() => setEditing((v) => !v)}
          >
            {editing ? "Preview" : "Edit"}
          </button>
        </div>
      </header>
      <div className="p-4">
        {editing ? (
          <div className="space-y-2">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={Math.max(6, body.split("\n").length + 1)}
              className="w-full rounded border border-slate-300 p-2 font-mono text-xs"
            />
            <div className="flex justify-end gap-2">
              <button
                className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                onClick={() => {
                  setBody(section.body);
                  setEditing(false);
                }}
              >
                Cancel
              </button>
              <button
                className="rounded bg-brand-600 px-2 py-0.5 text-xs text-white hover:bg-brand-700 disabled:opacity-50"
                disabled={update.isPending}
                onClick={async () => {
                  await update.mutateAsync({
                    projectId,
                    draftId,
                    sectionId: section.id,
                    body,
                  });
                  setEditing(false);
                }}
              >
                Save
              </button>
            </div>
          </div>
        ) : section.body ? (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
            {renderBody(section.body, section.citations, projectId)}
          </div>
        ) : (
          <p className="text-xs italic text-slate-500">
            Empty. Click <strong>Generate</strong> to have the agent draft this section from
            project documents.
          </p>
        )}
        {section.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1 border-t border-slate-100 pt-2">
            {section.citations.map((c) => (
              <CitationChip key={c.chunkId} projectId={projectId} citation={c} />
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function renderBody(text: string, citations: Citation[], projectId: string) {
  const byKey = new Map(citations.map((c) => [`${c.documentId}:${c.page}`, c] as const));
  const out: React.ReactNode[] = [];
  const regex = /\[doc:([0-9a-f-]{36})\s+p(\d+)\]/gi;
  let last = 0;
  let i = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const c = byKey.get(`${m[1]}:${m[2]}`);
    if (c) {
      out.push(<CitationChip key={`i-${i++}`} projectId={projectId} citation={c} compact />);
    } else {
      out.push(m[0]);
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
