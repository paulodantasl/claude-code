"use client";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

type Recipient = { vendorId?: string; email: string };

const STATUS_COLOR: Record<string, string> = {
  pending: "bg-slate-200 text-slate-700",
  sent: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export function RfqSendPanel({
  projectId,
  versionId,
  versionNumber,
  organizationId,
}: {
  projectId: string;
  versionId: string;
  versionNumber: number;
  organizationId: string;
}) {
  const utils = trpc.useUtils();
  const vendorsQ = trpc.vendor.list.useQuery({ organizationId });
  const sendsQ = trpc.rfq.listSends.useQuery({ projectId, versionId });
  const send = trpc.rfq.sendToVendors.useMutation({
    onSuccess: () => utils.rfq.listSends.invalidate({ projectId, versionId }),
  });

  const [selected, setSelected] = useState<Recipient[]>([]);
  const [adhocEmail, setAdhocEmail] = useState("");
  const [responseDueDays, setResponseDueDays] = useState(10);
  const [cc, setCc] = useState("");

  const toggleVendor = (vendorId: string, email: string | null, name: string) => {
    if (!email) return; // no contact email — skip
    setSelected((prev) => {
      const idx = prev.findIndex((r) => r.vendorId === vendorId);
      if (idx >= 0) return prev.filter((_, i) => i !== idx);
      return [...prev, { vendorId, email }];
    });
  };

  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <h2 className="text-sm font-semibold">Send v{versionNumber} to vendors</h2>

      <div className="mt-2">
        <p className="text-[10px] font-semibold uppercase text-slate-500">
          Project vendor directory
        </p>
        {vendorsQ.isLoading ? (
          <p className="text-xs text-slate-500">Loading…</p>
        ) : vendorsQ.data?.length === 0 ? (
          <p className="text-xs text-slate-500">
            No vendors in directory yet. Add one from Packages → Bids.
          </p>
        ) : (
          <ul className="mt-1 max-h-32 space-y-1 overflow-y-auto rounded border border-slate-100 p-1 text-xs">
            {vendorsQ.data?.map((v) => {
              const checked = selected.some((r) => r.vendorId === v.id);
              const disabled = !v.contactEmail;
              return (
                <li key={v.id} className={`flex items-center gap-2 ${disabled ? "opacity-50" : ""}`}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => toggleVendor(v.id, v.contactEmail, v.name)}
                  />
                  <span className="flex-1">{v.name}</span>
                  <span className="text-[10px] text-slate-500">
                    {v.contactEmail ?? "(no email)"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="mt-2 flex items-center gap-1">
        <input
          placeholder="Add ad-hoc email…"
          value={adhocEmail}
          onChange={(e) => setAdhocEmail(e.target.value)}
          type="email"
          className="flex-1 rounded border border-slate-300 px-2 py-0.5 text-xs"
        />
        <button
          className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50 disabled:opacity-50"
          disabled={!adhocEmail}
          onClick={() => {
            setSelected((prev) => [...prev, { email: adhocEmail }]);
            setAdhocEmail("");
          }}
        >
          + Add
        </button>
      </div>

      {selected.length > 0 && (
        <div className="mt-2 rounded bg-slate-50 p-2">
          <p className="text-[10px] font-semibold uppercase text-slate-500">
            Will send to ({selected.length})
          </p>
          <ul className="mt-1 space-y-0.5 text-xs">
            {selected.map((r, i) => (
              <li key={`${r.vendorId}-${i}`} className="flex items-center justify-between">
                <span>{r.email}</span>
                <button
                  className="text-slate-400 hover:text-red-600"
                  onClick={() => setSelected((p) => p.filter((_, idx) => idx !== i))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <label>
          <span className="text-[10px] uppercase text-slate-500">Response due (days)</span>
          <input
            type="number"
            min={1}
            max={120}
            value={responseDueDays}
            onChange={(e) => setResponseDueDays(parseInt(e.target.value || "10", 10))}
            className="mt-0.5 w-full rounded border border-slate-300 px-1 py-0.5"
          />
        </label>
        <label>
          <span className="text-[10px] uppercase text-slate-500">CC (comma-separated)</span>
          <input
            value={cc}
            onChange={(e) => setCc(e.target.value)}
            className="mt-0.5 w-full rounded border border-slate-300 px-1 py-0.5"
            placeholder="pm@gc.com"
          />
        </label>
      </div>

      <button
        className="mt-2 w-full rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
        disabled={selected.length === 0 || send.isPending}
        onClick={() =>
          send.mutate({
            projectId,
            versionId,
            recipients: selected,
            responseDueDays,
            cc: cc
              .split(",")
              .map((s) => s.trim())
              .filter((s) => s.length > 0 && s.includes("@")),
          })
        }
      >
        {send.isPending ? "Sending…" : `Send to ${selected.length || "…"} recipient(s)`}
      </button>

      {send.data && (
        <p className="mt-2 text-[10px] text-slate-600">
          ✅ Sent: {send.data.sent} · ❌ Failed: {send.data.failed}
        </p>
      )}
      {send.error && (
        <p className="mt-2 text-[10px] text-red-600">{send.error.message}</p>
      )}

      {sendsQ.data && sendsQ.data.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2">
          <p className="text-[10px] font-semibold uppercase text-slate-500">
            Recent sends
          </p>
          <ul className="mt-1 space-y-1 text-[11px]">
            {sendsQ.data.slice(0, 10).map((row) => (
              <li key={row.send.id} className="flex items-center justify-between gap-2">
                <span className="truncate">
                  {row.vendor?.name ?? row.send.toEmail}{" "}
                  <span className="text-slate-400">
                    {new Date(row.send.sentAt ?? row.send.createdAt).toLocaleString()}
                  </span>
                </span>
                <span className={`rounded px-1.5 py-0.5 ${STATUS_COLOR[row.send.status]}`}>
                  {row.send.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
