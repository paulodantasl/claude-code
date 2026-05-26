"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { BidsPanel } from "@/components/BidsPanel";
import { CompliancePanel } from "@/components/CompliancePanel";

export default function PackageDetailPage() {
  const params = useParams<{ id: string; pkgId: string }>();
  const projectId = params.id;
  const packageId = params.pkgId;

  const pkg = trpc.package.get.useQuery({ projectId, packageId });
  const project = trpc.project.get.useQuery({ projectId });
  const templates = trpc.rfq.listTemplates.useQuery({ projectId });
  const drafts = trpc.rfq.listDrafts.useQuery({ projectId, packageId });
  const utils = trpc.useUtils();
  const createDraft = trpc.rfq.createDraft.useMutation({
    onSuccess: () => utils.rfq.listDrafts.invalidate({ projectId, packageId }),
  });

  const [templateId, setTemplateId] = useState("");
  const [title, setTitle] = useState("");

  if (pkg.isLoading) return <main className="p-10">Loading…</main>;
  if (!pkg.data) {
    return (
      <main className="p-10">
        Not found.{" "}
        <Link className="underline" href={`/projects/${projectId}`}>
          Back
        </Link>
      </main>
    );
  }

  const tpl = templates.data?.find((t) => t.id === templateId);

  return (
    <main className="mx-auto max-w-5xl p-6">
      <Link href={`/projects/${projectId}`} className="text-sm text-slate-500 hover:underline">
        ← Project
      </Link>
      <h1 className="mt-1 text-2xl font-semibold">{pkg.data.name}</h1>
      <p className="text-sm text-slate-600">{pkg.data.kind}</p>

      <section className="mt-6 rounded border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Start a new RFQ draft</h2>
        <form
          className="mt-3 grid gap-2 sm:grid-cols-[2fr_2fr_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!templateId || !title) return;
            createDraft.mutate({
              projectId,
              packageId,
              templateId,
              title,
            });
            setTitle("");
          }}
        >
          <select
            value={templateId}
            onChange={(e) => {
              setTemplateId(e.target.value);
              const found = templates.data?.find((t) => t.id === e.target.value);
              if (found && !title) setTitle(found.name);
            }}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Select template…</option>
            {templates.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <input
            placeholder="Draft title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            type="submit"
            disabled={!templateId || !title || createDraft.isPending}
            className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Create
          </button>
        </form>
        {tpl && (
          <p className="mt-2 text-xs text-slate-500">{tpl.description}</p>
        )}
      </section>

      {project.data && pkg.data.kind === "sourcing" && (
        <BidsPanel
          projectId={projectId}
          packageId={packageId}
          organizationId={project.data.project.organizationId}
        />
      )}

      <CompliancePanel projectId={projectId} packageId={packageId} />

      <section className="mt-6">
        <h2 className="text-sm font-semibold">RFQ drafts</h2>
        {drafts.isLoading ? (
          <p className="mt-2 text-sm text-slate-500">Loading…</p>
        ) : drafts.data?.length === 0 ? (
          <p className="mt-2 rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
            No drafts yet for this package.
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {drafts.data?.map((d) => (
              <li key={d.id}>
                <Link
                  href={`/projects/${projectId}/rfq/${d.id}`}
                  className="block px-3 py-2 text-sm hover:bg-slate-50"
                >
                  <p className="font-medium">{d.title}</p>
                  <p className="text-xs text-slate-500">
                    {d.currentSections.length} sections · updated{" "}
                    {new Date(d.updatedAt).toLocaleString()}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
