"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ChevronDown, ChevronRight, Copy, Check, ThumbsUp, ThumbsDown } from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { useUIStore } from "@/stores/ui";
import type { QueryResult, StageResult, ColumnInfo } from "@/stores/query";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

interface ChatMessageProps {
  query: string;
  result?: QueryResult | null;
  loading?: boolean;
  error?: string | null;
  queryId?: string;
}

export function ChatMessage({ query, result, loading, error, queryId }: ChatMessageProps) {
  const token = useAuthStore((s) => s.token);
  const addToast = useUIStore((s) => s.addToast);
  const [showSql, setShowSql] = useState(true);
  const [showStages, setShowStages] = useState(false);
  const [showColumns, setShowColumns] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleCopy = async () => {
    if (!result?.sql) return;
    await navigator.clipboard.writeText(result.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = async (rating: 1 | 2) => {
    if (feedback || !token || !queryId) return;
    try {
      await fetch(`${API_URL}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query_id: queryId, rating: rating === 1 ? 5 : 1 }),
      });
      setFeedback(rating === 1 ? "up" : "down");
      addToast(rating === 1 ? "Thanks for the feedback!" : "Feedback recorded", "success");
    } catch { /* ignore */ }
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {query}
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          Analyzing your question...
        </div>
      )}

      {result && !loading && (
        <div className="max-w-[92%] space-y-3">
          {result.explanation && (
            <div className="rounded-lg border bg-muted/30 px-3 py-2.5 text-sm leading-relaxed">
              {result.explanation}
            </div>
          )}

          {result.sql && (
            <div className="rounded-lg border">
              <button
                onClick={() => setShowSql(!showSql)}
                className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50"
              >
                {showSql ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Generated SQL
              </button>
              {showSql && (
                <div className="border-t px-3 py-2">
                  <div className="flex items-start justify-between gap-2">
                    <pre className="overflow-x-auto text-sm font-mono leading-relaxed">{result.sql}</pre>
                    <Button variant="ghost" size="icon" className="shrink-0 h-6 w-6" onClick={handleCopy} aria-label="Copy SQL">
                      {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}

          {result.columns && result.columns.length > 0 && (
            <div className="rounded-lg border">
              <button
                onClick={() => setShowColumns(!showColumns)}
                className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50"
              >
                {showColumns ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Expected Columns ({result.columns.length})
              </button>
              {showColumns && (
                <div className="border-t">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b bg-muted/30">
                        <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Column</th>
                        <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Type</th>
                        <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Table</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(result.columns as ColumnInfo[]).map((c, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="px-3 py-1.5 font-mono">{c.name}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{c.type}</td>
                          <td className="px-3 py-1.5 text-muted-foreground">{c.table}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {result.stages && result.stages.length > 0 && (
            <div className="rounded-lg border">
              <button
                onClick={() => setShowStages(!showStages)}
                className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50"
              >
                {showStages ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Pipeline ({result.total_duration_ms.toFixed(0)}ms)
              </button>
              {showStages && (
                <div className="border-t px-3 py-2 space-y-1.5">
                  {result.stages.map((s: StageResult, i: number) => (
                    <div key={i}>
                      {i > 0 && <Separator className="my-1" />}
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className={`h-1.5 w-1.5 rounded-full ${
                            s.status === "success" || s.status === "dry_run"
                              ? "bg-green-500"
                              : s.status === "skipped" ? "bg-yellow-400" : "bg-red-500"
                          }`} />
                          <span className="font-medium capitalize">{s.name}</span>
                        </div>
                        <span className="text-muted-foreground">{s.duration_ms.toFixed(0)}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleFeedback(1)}
              disabled={!!feedback}
              className={`rounded p-1 transition-colors ${feedback === "up" ? "text-green-600 bg-green-50" : "text-muted-foreground hover:text-foreground hover:bg-muted"}`}
              aria-label="Good answer"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => handleFeedback(2)}
              disabled={!!feedback}
              className={`rounded p-1 transition-colors ${feedback === "down" ? "text-red-600 bg-red-50" : "text-muted-foreground hover:text-foreground hover:bg-muted"}`}
              aria-label="Bad answer"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>

          {result.error && (
            <div className="rounded-lg border border-destructive bg-destructive/10 p-3">
              <p className="text-xs text-destructive">{result.error}</p>
            </div>
          )}
        </div>
      )}

      {error && !loading && !result && (
        <div className="max-w-[90%] rounded-lg border border-destructive bg-destructive/10 p-3">
          <p className="text-xs text-destructive">{error}</p>
        </div>
      )}
    </div>
  );
}
