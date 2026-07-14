"use client";
import { useRef, useState } from "react";
import { trpc } from "@/lib/trpc";

const KIND_OPTIONS = [
  "spec",
  "addendum",
  "drawing_index",
  "bid",
  "submittal",
  "sds",
  "warranty",
  "coi",
  "lien_waiver",
  "other",
] as const;

export function UploadButton({ projectId }: { projectId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [kind, setKind] = useState<(typeof KIND_OPTIONS)[number]>("spec");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const utils = trpc.useUtils();
  const requestUpload = trpc.document.requestUpload.useMutation();
  const finalize = trpc.document.finalizeUpload.useMutation();

  async function onChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const { uploadUrl, storageKey } = await requestUpload.mutateAsync({
        projectId,
        title: file.name,
        mimeType: file.type || "application/pdf",
        sizeBytes: file.size,
        kind,
      });
      const put = await fetch(uploadUrl, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type || "application/pdf" },
      });
      if (!put.ok) throw new Error(`Upload failed (${put.status})`);
      await finalize.mutateAsync({
        projectId,
        storageKey,
        title: file.name,
        mimeType: file.type || "application/pdf",
        kind,
      });
      await utils.document.list.invalidate({ projectId });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-2">
      <select
        className="rounded border border-slate-300 px-2 py-1 text-sm"
        value={kind}
        onChange={(e) => setKind(e.target.value as (typeof KIND_OPTIONS)[number])}
      >
        {KIND_OPTIONS.map((k) => (
          <option key={k} value={k}>
            {k}
          </option>
        ))}
      </select>
      <label className="cursor-pointer rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700">
        {busy ? "Uploading…" : "Upload"}
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.xlsx,.xls"
          className="hidden"
          onChange={onChange}
          disabled={busy}
        />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
