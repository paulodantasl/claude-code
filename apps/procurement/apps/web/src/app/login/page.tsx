"use client";
import { useState } from "react";
import { trpc } from "@/lib/trpc";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const requestLink = trpc.auth.requestMagicLink.useMutation();

  return (
    <main className="mx-auto max-w-md p-10">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="mt-2 text-sm text-slate-600">
        We&apos;ll email you a magic link. In dev, the link is printed to the API server console.
      </p>
      <form
        className="mt-6 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (email) requestLink.mutate({ email });
        }}
      >
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="w-full rounded border border-slate-300 px-3 py-2"
        />
        <button
          type="submit"
          disabled={requestLink.isPending}
          className="w-full rounded bg-brand-600 px-3 py-2 text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {requestLink.isPending ? "Sending…" : "Send magic link"}
        </button>
      </form>
      {requestLink.isSuccess && (
        <p className="mt-4 rounded bg-emerald-50 p-3 text-sm text-emerald-700">
          Magic link sent — check your inbox (or the API server console in dev).
        </p>
      )}
      {requestLink.error && (
        <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">
          {requestLink.error.message}
        </p>
      )}
    </main>
  );
}
