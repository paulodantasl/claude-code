"use client";
import Link from "next/link";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

export function PackagesPanel({ projectId }: { projectId: string }) {
  const packages = trpc.package.list.useQuery({ projectId });
  const utils = trpc.useUtils();
  const create = trpc.package.create.useMutation({
    onSuccess: () => utils.package.list.invalidate({ projectId }),
  });
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"sourcing" | "compliance">("sourcing");

  return (
    <div className="p-4">
      <form
        className="mb-4 grid gap-2 sm:grid-cols-[2fr_1fr_auto]"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name) return;
          create.mutate({ projectId, kind, name });
          setName("");
        }}
      >
        <input
          placeholder="Package name (e.g., RFQ #1 — Concrete)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as "sourcing" | "compliance")}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="sourcing">sourcing</option>
          <option value="compliance">compliance</option>
        </select>
        <button
          type="submit"
          disabled={create.isPending || !name}
          className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Add
        </button>
      </form>

      {packages.isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : packages.data?.length === 0 ? (
        <p className="rounded border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          No packages yet. Add one above to start drafting RFQs.
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 rounded border border-slate-200 bg-white">
          {packages.data?.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${projectId}/packages/${p.id}`}
                className="block px-3 py-2 text-sm hover:bg-slate-50"
              >
                <p className="font-medium">{p.name}</p>
                <p className="text-xs text-slate-500">
                  {p.kind}
                  {p.bidDueAt && ` · due ${new Date(p.bidDueAt).toLocaleDateString()}`}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
