"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { trpc } from "@/lib/trpc";
import { CitationChip } from "./CitationChip";

export function ChatPanel({ projectId }: { projectId: string }) {
  const threads = trpc.chat.listThreads.useQuery({ projectId });
  const utils = trpc.useUtils();
  const createThread = trpc.chat.createThread.useMutation({
    onSuccess: () => utils.chat.listThreads.invalidate({ projectId }),
  });
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);

  useEffect(() => {
    if (!activeThreadId && threads.data?.[0]) {
      setActiveThreadId(threads.data[0].id);
    }
  }, [activeThreadId, threads.data]);

  if (threads.isLoading) return <div className="p-4 text-sm text-slate-500">Loading…</div>;

  return (
    <div className="flex h-[600px] flex-col">
      <div className="flex items-center gap-2 border-b border-slate-200 p-2">
        <select
          value={activeThreadId ?? ""}
          onChange={(e) => setActiveThreadId(e.target.value || null)}
          className="flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
        >
          {threads.data?.length === 0 && <option value="">No threads yet</option>}
          {threads.data?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.title} · {new Date(t.updatedAt).toLocaleString()}
            </option>
          ))}
        </select>
        <button
          className="rounded border border-slate-300 px-2 py-1 text-sm hover:bg-slate-50"
          onClick={async () => {
            const t = await createThread.mutateAsync({ projectId });
            setActiveThreadId(t.id);
          }}
        >
          + New
        </button>
      </div>
      {activeThreadId ? (
        <ChatThread projectId={projectId} threadId={activeThreadId} />
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
          Create a thread to start asking questions.
        </div>
      )}
    </div>
  );
}

function ChatThread({ projectId, threadId }: { projectId: string; threadId: string }) {
  const thread = trpc.chat.getThread.useQuery({ projectId, threadId });
  const utils = trpc.useUtils();
  const send = trpc.chat.sendMessage.useMutation({
    onSuccess: () => utils.chat.getThread.invalidate({ projectId, threadId }),
  });
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [thread.data?.messages.length, send.isPending]);

  const messages = thread.data?.messages ?? [];

  return (
    <>
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">
            Try: <em>&ldquo;Summarize the concrete spec — what mix design and curing requirements are called out?&rdquo;</em>
          </p>
        )}
        {messages.map((m) => (
          <Message key={m.id} projectId={projectId} role={m.role} content={m.content} citations={m.citations as Citation[]} />
        ))}
        {send.isPending && <p className="text-xs italic text-slate-500">Thinking…</p>}
      </div>
      <form
        className="flex border-t border-slate-200"
        onSubmit={(e) => {
          e.preventDefault();
          const text = input.trim();
          if (!text) return;
          setInput("");
          send.mutate({ projectId, threadId, message: text });
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the procurement agent…"
          className="flex-1 px-3 py-2 text-sm outline-none"
          disabled={send.isPending}
        />
        <button
          type="submit"
          disabled={send.isPending || !input.trim()}
          className="bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </>
  );
}

interface Citation {
  documentId: string;
  page: number;
  chunkId: string;
  snippet: string;
}

function Message({
  projectId,
  role,
  content,
  citations,
}: {
  projectId: string;
  role: string;
  content: string;
  citations: Citation[];
}) {
  const rendered = useMemo(() => renderWithCitations(content, citations, projectId), [content, citations, projectId]);
  return (
    <div
      className={`rounded-lg p-3 text-sm ${role === "user" ? "bg-slate-100" : "bg-brand-50/40 ring-1 ring-brand-500/10"}`}
    >
      <p className="mb-1 text-xs font-semibold uppercase text-slate-500">
        {role === "user" ? "You" : "Agent"}
      </p>
      <div className="whitespace-pre-wrap leading-relaxed">{rendered}</div>
      {role === "assistant" && citations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {citations.map((c) => (
            <CitationChip key={c.chunkId} projectId={projectId} citation={c} />
          ))}
        </div>
      )}
    </div>
  );
}

// Replace [doc:<uuid> p<n>] markers in model text with citation chips.
function renderWithCitations(text: string, citations: Citation[], projectId: string) {
  const byKey = new Map(
    citations.map((c) => [`${c.documentId}:${c.page}`, c] as const),
  );
  const parts: React.ReactNode[] = [];
  const regex = /\[doc:([0-9a-f-]{36})\s+p(\d+)\]/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;
  while ((match = regex.exec(text))) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    const c = byKey.get(`${match[1]}:${match[2]}`);
    if (c) {
      parts.push(<CitationChip key={`inline-${keyIdx++}`} projectId={projectId} citation={c} compact />);
    } else {
      parts.push(match[0]);
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}
