"use client";
import Link from "next/link";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

interface Props {
  projectId: string;
  packageId: string;
  organizationId: string;
}

export function BidsPanel({ projectId, packageId, organizationId }: Props) {
  const utils = trpc.useUtils();
  const bidsQ = trpc.bid.list.useQuery({ projectId, packageId });
  const vendorsQ = trpc.vendor.list.useQuery({ organizationId });
  const docsQ = trpc.document.list.useQuery({ projectId });
  const compsQ = trpc.comparison.list.useQuery({ projectId, packageId });

  const register = trpc.bid.register.useMutation({
    onSuccess: () => utils.bid.list.invalidate({ projectId, packageId }),
  });
  const extract = trpc.bid.extract.useMutation({
    onSuccess: () => utils.bid.list.invalidate({ projectId, packageId }),
  });
  const createVendor = trpc.vendor.create.useMutation({
    onSuccess: () => utils.vendor.list.invalidate({ organizationId }),
  });
  const createComparison = trpc.comparison.create.useMutation({
    onSuccess: () => utils.comparison.list.invalidate({ projectId, packageId }),
  });

  const [vendorId, setVendorId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [newVendorName, setNewVendorName] = useState("");
  const [selectedBidIds, setSelectedBidIds] = useState<string[]>([]);
  const [comparisonTitle, setComparisonTitle] = useState("");

  const bidDocs = docsQ.data?.filter(
    (d) => d.kind === "bid" && d.status === "parsed" && !bidsQ.data?.some((b) => b.document.id === d.id),
  );

  return (
    <section className="mt-6 space-y-4">
      <div>
        <h2 className="text-sm font-semibold">Vendors</h2>
        <form
          className="mt-2 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (!newVendorName) return;
            createVendor.mutate({ organizationId, name: newVendorName });
            setNewVendorName("");
          }}
        >
          <input
            placeholder="Vendor name"
            value={newVendorName}
            onChange={(e) => setNewVendorName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            className="rounded bg-brand-600 px-2 py-1 text-xs text-white hover:bg-brand-700 disabled:opacity-50"
            disabled={createVendor.isPending || !newVendorName}
          >
            Add vendor
          </button>
          <span className="text-xs text-slate-500">
            {vendorsQ.data?.length ?? 0} in org
          </span>
        </form>
      </div>

      <div>
        <h2 className="text-sm font-semibold">Register a bid</h2>
        <form
          className="mt-2 grid gap-2 sm:grid-cols-[2fr_2fr_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!vendorId || !documentId) return;
            register.mutate({
              projectId,
              packageId,
              vendorId,
              documentId,
            });
            setVendorId("");
            setDocumentId("");
          }}
        >
          <select
            value={vendorId}
            onChange={(e) => setVendorId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Select vendor…</option>
            {vendorsQ.data?.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">Select parsed bid document…</option>
            {bidDocs?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.title} ({d.pageCount} pp)
              </option>
            ))}
          </select>
          <button
            className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            disabled={!vendorId || !documentId || register.isPending}
          >
            Register
          </button>
        </form>
        {register.error && (
          <p className="mt-1 text-xs text-red-600">{register.error.message}</p>
        )}
        <p className="mt-1 text-xs text-slate-500">
          Upload the bid document with kind <code>bid</code> from the Documents
          section, wait for parsing, then register it here.
        </p>
      </div>

      <div>
        <h2 className="text-sm font-semibold">Bids</h2>
        {bidsQ.isLoading ? (
          <p className="mt-2 text-xs text-slate-500">Loading…</p>
        ) : bidsQ.data?.length === 0 ? (
          <p className="mt-2 text-xs text-slate-500">No bids registered yet.</p>
        ) : (
          <ul className="mt-2 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {bidsQ.data?.map((r) => {
              const checked = selectedBidIds.includes(r.bid.id);
              return (
                <li key={r.bid.id} className="flex items-center gap-3 p-3 text-sm">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) =>
                      setSelectedBidIds((prev) =>
                        e.target.checked
                          ? [...prev, r.bid.id]
                          : prev.filter((id) => id !== r.bid.id),
                      )
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{r.vendor.name}</p>
                    <p className="truncate text-xs text-slate-500">
                      {r.document.title} ·{" "}
                      {r.bid.extractedAt
                        ? `${r.bid.lineItems.length} line items extracted`
                        : "not extracted"}
                      {r.bid.baseTotal != null &&
                        ` · base $${(r.bid.baseTotal / 100).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
                    </p>
                  </div>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
                    {r.bid.status}
                  </span>
                  <button
                    className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
                    disabled={extract.isPending}
                    onClick={() =>
                      extract.mutate({ projectId, bidId: r.bid.id })
                    }
                  >
                    {r.bid.extractedAt ? "Re-extract" : "Extract"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div>
        <h2 className="text-sm font-semibold">Comparison</h2>
        <form
          className="mt-2 flex flex-wrap items-center gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (selectedBidIds.length < 2 || !comparisonTitle) return;
            const run = await createComparison.mutateAsync({
              projectId,
              packageId,
              bidIds: selectedBidIds,
              title: comparisonTitle,
            });
            setComparisonTitle("");
            setSelectedBidIds([]);
            // Open the comparison page.
            window.location.href = `/projects/${projectId}/comparison/${run.id}`;
          }}
        >
          <input
            placeholder="Comparison title"
            value={comparisonTitle}
            onChange={(e) => setComparisonTitle(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          />
          <button
            className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            disabled={
              selectedBidIds.length < 2 ||
              !comparisonTitle ||
              createComparison.isPending
            }
          >
            Compare {selectedBidIds.length || ""} bids
          </button>
          {createComparison.error && (
            <p className="text-xs text-red-600">{createComparison.error.message}</p>
          )}
        </form>
        {compsQ.data && compsQ.data.length > 0 && (
          <ul className="mt-3 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
            {compsQ.data.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/projects/${projectId}/comparison/${c.id}`}
                  className="block px-3 py-2 text-sm hover:bg-slate-50"
                >
                  <p className="font-medium">{c.title}</p>
                  <p className="text-xs text-slate-500">
                    {c.matrix.rows.length} lines · {c.bidIds.length} vendors ·{" "}
                    {new Date(c.createdAt).toLocaleString()}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
