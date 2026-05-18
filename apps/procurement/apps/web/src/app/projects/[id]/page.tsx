"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { DocumentList } from "@/components/DocumentList";
import { UploadButton } from "@/components/UploadButton";
import { ChatPanel } from "@/components/ChatPanel";
import { AuditPanel } from "@/components/AuditPanel";
import { PackagesPanel } from "@/components/PackagesPanel";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const project = trpc.project.get.useQuery({ projectId });
  const [tab, setTab] = useState<"chat" | "packages" | "audit">("chat");

  if (project.isLoading) return <main className="p-10">Loading…</main>;
  if (project.error) {
    return (
      <main className="p-10 text-red-600">
        {project.error.message}{" "}
        <Link className="underline" href="/projects">
          Back to projects
        </Link>
      </main>
    );
  }
  if (!project.data) return null;

  const p = project.data.project;

  return (
    <main className="mx-auto max-w-7xl p-6">
      <header className="flex items-center justify-between">
        <div>
          <Link href="/projects" className="text-sm text-slate-500 hover:underline">
            ← Projects
          </Link>
          <h1 className="mt-1 text-2xl font-semibold">{p.name}</h1>
          {p.jurisdiction && (
            <p className="text-sm text-slate-600">{p.jurisdiction}</p>
          )}
        </div>
        <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
          Role: {project.data.role}
        </span>
      </header>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.4fr]">
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Documents</h2>
            <UploadButton projectId={projectId} />
          </div>
          <DocumentList projectId={projectId} />
        </section>

        <section className="rounded border border-slate-200 bg-white">
          <div className="flex border-b border-slate-200">
            <button
              className={`px-4 py-2 text-sm ${tab === "chat" ? "border-b-2 border-brand-600 font-medium" : "text-slate-600"}`}
              onClick={() => setTab("chat")}
            >
              Agent
            </button>
            <button
              className={`px-4 py-2 text-sm ${tab === "packages" ? "border-b-2 border-brand-600 font-medium" : "text-slate-600"}`}
              onClick={() => setTab("packages")}
            >
              Packages & RFQs
            </button>
            <button
              className={`px-4 py-2 text-sm ${tab === "audit" ? "border-b-2 border-brand-600 font-medium" : "text-slate-600"}`}
              onClick={() => setTab("audit")}
            >
              Audit log
            </button>
          </div>
          {tab === "chat" && <ChatPanel projectId={projectId} />}
          {tab === "packages" && <PackagesPanel projectId={projectId} />}
          {tab === "audit" && <AuditPanel projectId={projectId} />}
        </section>
      </div>
    </main>
  );
}
