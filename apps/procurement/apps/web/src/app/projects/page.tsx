"use client";
import Link from "next/link";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

export default function ProjectsPage() {
  const me = trpc.auth.me.useQuery();
  const projects = trpc.project.list.useQuery();
  const create = trpc.project.create.useMutation({
    onSuccess: () => projects.refetch(),
  });

  const [name, setName] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [orgId, setOrgId] = useState<string>("");

  if (me.isLoading) return <main className="p-10">Loading…</main>;
  if (!me.data) return (
    <main className="p-10">
      <p>You&apos;re not signed in. <Link className="text-brand-600 underline" href="/login">Sign in</Link></p>
    </main>
  );

  const orgs = me.data.organizations;
  const activeOrgId = orgId || orgs[0]?.id || "";

  return (
    <main className="mx-auto max-w-4xl p-10">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Projects</h1>
        <span className="text-sm text-slate-600">{me.data.email}</span>
      </header>

      <section className="mt-6 rounded border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold">Create project</h2>
        <form
          className="mt-3 grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name || !activeOrgId) return;
            create.mutate({
              organizationId: activeOrgId,
              name,
              jurisdiction: jurisdiction || undefined,
            });
            setName("");
            setJurisdiction("");
          }}
        >
          <input
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          />
          <input
            placeholder="Jurisdiction (optional)"
            value={jurisdiction}
            onChange={(e) => setJurisdiction(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          />
          <select
            value={activeOrgId}
            onChange={(e) => setOrgId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1"
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="rounded bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700"
            disabled={create.isPending}
          >
            {create.isPending ? "Creating…" : "Create"}
          </button>
        </form>
      </section>

      <ul className="mt-6 space-y-2">
        {projects.data?.map((p) => (
          <li key={p.id} className="rounded border border-slate-200 bg-white p-4">
            <Link href={`/projects/${p.id}`} className="block hover:underline">
              <h3 className="text-lg font-medium">{p.name}</h3>
              {p.jurisdiction && (
                <p className="text-sm text-slate-600">{p.jurisdiction}</p>
              )}
            </Link>
          </li>
        ))}
        {projects.data?.length === 0 && (
          <li className="rounded border border-dashed border-slate-300 p-6 text-center text-slate-500">
            No projects yet — create one above.
          </li>
        )}
      </ul>
    </main>
  );
}
