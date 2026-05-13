"use client";
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Use the CDN worker so we don't need a build-time copy step.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export function PdfViewer({
  url,
  page,
  onPageChange,
}: {
  url: string;
  page: number;
  onPageChange: (n: number) => void;
}) {
  const [numPages, setNumPages] = useState<number | null>(null);

  return (
    <div>
      <Document
        file={url}
        onLoadSuccess={(info) => setNumPages(info.numPages)}
        loading={<p className="text-sm text-slate-500">Loading PDF…</p>}
        error={<p className="text-sm text-red-600">Failed to load PDF.</p>}
      >
        <Page pageNumber={page} width={680} renderTextLayer renderAnnotationLayer={false} />
      </Document>
      <div className="mt-3 flex items-center justify-center gap-3 text-sm">
        <button
          className="rounded border border-slate-300 px-2 py-0.5 disabled:opacity-50"
          disabled={page <= 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
        >
          ← Prev
        </button>
        <span>
          Page {page} of {numPages ?? "?"}
        </span>
        <button
          className="rounded border border-slate-300 px-2 py-0.5 disabled:opacity-50"
          disabled={numPages !== null && page >= numPages}
          onClick={() => onPageChange((numPages ? Math.min(numPages, page + 1) : page + 1))}
        >
          Next →
        </button>
      </div>
    </div>
  );
}
