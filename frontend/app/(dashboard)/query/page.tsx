"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { useQueryStore } from "@/stores/query";
import { useUIStore } from "@/stores/ui";
import { ChatInput } from "@/components/query/ChatInput";
import { ChatMessage } from "@/components/query/ChatMessage";
import Link from "next/link";

const EXAMPLE_QUERIES = [
  "show me active users",
  "total revenue by quarter",
  "list products out of stock",
  "find customers from new york",
];

export default function QueryPage() {
  const searchParams = useSearchParams();
  const token = useAuthStore((s) => s.token);
  const isAuth = useAuthStore((s) => s.isAuthenticated);
  const addToast = useUIStore((s) => s.addToast);
  const { currentResult, loading, error, history, pastQueries, execute, loadHistory, setQuery } = useQueryStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const hasRun = useRef(false);

  useEffect(() => {
    if (token && isAuth) loadHistory(token);
  }, [token, isAuth, loadHistory]);

  useEffect(() => {
    const qParam = searchParams.get("q");
    if (qParam && !hasRun.current && token && isAuth) {
      hasRun.current = true;
      setQuery(qParam);
      execute(token).catch(() => addToast("Query failed", "error"));
    }
  }, [searchParams, token, isAuth, execute, setQuery, addToast]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, currentResult, loading, pastQueries.length]);

  const handleSend = (q: string) => {
    if (!token) { addToast("Please log in first", "warning"); return; }
    hasRun.current = true;
    setQuery(q);
    execute(token).catch(() => addToast("Query failed", "error"));
  };

  const showEmpty = pastQueries.length === 0 && history.length === 0 && !loading && !error;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ask a Question</h1>
        <p className="text-sm text-muted-foreground">
          Ask a natural language question about your data
        </p>
      </div>

      <div className="flex flex-col gap-6">
        {showEmpty && (
          <div className="flex flex-col items-center gap-6 py-8">
            <div className="text-center">
              <div className="text-5xl mb-3">&#x1F50D;</div>
              <p className="text-lg font-medium">Ask anything about your data</p>
              <p className="text-sm text-muted-foreground mt-1">
                Try one of these examples to get started
              </p>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-2">
              {EXAMPLE_QUERIES.map((eq) => (
                <button
                  key={eq}
                  onClick={() => handleSend(eq)}
                  className="rounded-lg border p-3 text-left text-sm transition-colors hover:bg-accent hover:border-primary"
                >
                  <span className="text-muted-foreground">&ldquo;</span>
                  {eq}
                  <span className="text-muted-foreground">&rdquo;</span>
                  <span className="ml-2 text-xs text-primary">&rarr;</span>
                </button>
              ))}
            </div>
            <div className="text-center border-t pt-6 w-full">
              <p className="text-sm text-muted-foreground mb-2">First time here?</p>
              <div className="flex justify-center gap-3 text-sm">
                <Link href="/settings" className="text-primary hover:underline">Connect a database</Link>
                <span className="text-muted-foreground">&middot;</span>
                <Link href="/schema" className="text-primary hover:underline">Browse schema</Link>
              </div>
            </div>
          </div>
        )}

        {pastQueries.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Recent Queries
            </p>
            {pastQueries.slice(0, 5).map((pq) => (
              <button
                key={pq.id}
                onClick={() => handleSend(pq.query)}
                className="w-full rounded-lg border p-3 text-left text-sm transition-colors hover:bg-accent"
              >
                <span className="font-medium">{pq.query}</span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {pq.duration_ms.toFixed(0)}ms
                </span>
                {pq.sql && (
                  <p className="mt-0.5 line-clamp-1 font-mono text-xs text-muted-foreground">
                    {pq.sql}
                  </p>
                )}
              </button>
            ))}
          </div>
        )}

        {history.map((h, i) => (
          <ChatMessage
            key={`h-${i}`}
            query={h.query}
            result={{ success: true, query: h.query, sql: h.sql, status: "success", stages: [], total_duration_ms: 0 }}
          />
        ))}

        {currentResult && !loading && (
          <ChatMessage query={history[0]?.query ?? ""} result={currentResult} queryId={String(Date.now())} />
        )}

        {loading && <ChatMessage query={history[0]?.query ?? ""} loading={true} />}

        {error && !loading && !currentResult && (
          <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="sticky bottom-0 bg-background pb-4 pt-2">
        <ChatInput onSend={handleSend} disabled={loading || !token} />
        <p className="mt-1 text-xs text-muted-foreground text-center">
          Press Enter to submit &middot; Share: <code className="text-xs">/query?q=show%20users</code>
        </p>
      </div>
    </div>
  );
}
