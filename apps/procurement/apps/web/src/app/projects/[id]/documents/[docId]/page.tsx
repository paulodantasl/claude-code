"use client";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";
import { trpc } from "@/lib/trpc";

const PdfViewer = dynamic(() => import("@/components/PdfViewer").then((m) => m.PdfViewer), {
  ssr: false,
  loading: () => <div className="p-4 text-sm text-slate-500">Loading viewer…</div>,
});

export default function DocumentPage() {
  const params = useParams<{ id: string; docId: string }>();
  const search = useSearchParams();
  const initialPage = Math.max(1, Number(search.get("page") ?? "1") || 1);
  const projectId = params.id;
  const documentId = params.docId;

  const doc = trpc.document.get.useQuery({ projectId, documentId });
  const dl = trpc.document.downloadUrl.useQuery({ projectId, documentId });
  const [page, setPage] = useState(initialPage);
  const chunks = trpc.document.chunksForPage.useQuery(
    { projectId, documentId, page },
    { enabled: doc.data?.status === "parsed" },
  );

  useEffect(() => {
    setPage(initialPage);
  }, [initialPage]);

  if (doc.isLoading) return <main className="p-10">Loading…</main>;
  if (!doc.data) return <main className="p-10">Not found.</main>;

  return (
    <main className="mx-auto max-w-7xl p-6">
      <header className="mb-4">
        <Link href={`/projects/${projectId}`} className="text-sm text-slate-500 hover:underline">
          ← Project
        </Link>
        <h1 className="mt-1 truncate text-xl font-semibold">{doc.data.title}</h1>
        <p className="text-sm text-slate-600">
          Status: <span className="font-medium">{doc.data.status}</span>
          {doc.data.pageCount && ` · ${doc.data.pageCount} pages`}
          {doc.data.parseError && (
            <span className="ml-2 text-red-600">{doc.data.parseError}</span>
          )}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        <section className="rounded border border-slate-200 bg-white p-4">
          {dl.data?.url ? (
            <PdfViewer url={dl.data.url} page={page} onPageChange={setPage} />
          ) : (
            <p className="text-sm text-slate-500">Preparing download…</p>
          )}
        </section>
        <aside className="space-y-3">
          <h2 className="text-sm font-semibold">Parsed text — page {page}</h2>
          {doc.data.status !== "parsed" && (
            <p className="rounded bg-amber-50 p-3 text-xs text-amber-800">
              Document is still being processed. Parsed text will appear here when ready.
            </p>
          )}
          {chunks.data?.length === 0 && doc.data.status === "parsed" && (
            <p className="rounded bg-slate-50 p-3 text-xs text-slate-600">
              No text extracted for this page (may be an image-only page).
            </p>
          )}
          {chunks.data?.map((c) => (
            <pre
              key={c.id}
              className="whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs leading-relaxed text-slate-700"
            >
              {c.text}
            </pre>
          ))}
        </aside>
      </div>
    </main>
  );
}
