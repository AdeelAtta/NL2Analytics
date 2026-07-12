"use client";

import { useState, Fragment } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  ChevronDown, ChevronRight, Copy, Check,
  ThumbsUp, ThumbsDown, Sparkles, User,
  AlertCircle,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { useUIStore } from "@/stores/ui";
import type { QueryResult } from "@/stores/query";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

interface ChatMessageProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    result?: QueryResult | null;
    loading?: boolean;
    error?: string | null;
  };
}

function renderBold(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function TypingDots() {
  return (
    <div className="flex items-center gap-1">
      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" style={{ animationDelay: "0ms" }} />
      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" style={{ animationDelay: "150ms" }} />
      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/50" style={{ animationDelay: "300ms" }} />
    </div>
  );
}

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex items-end justify-end gap-2 animate-in fade-in slide-in-from-right-4 duration-300">
      <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary/90 px-4 py-2.5 text-sm text-primary-foreground shadow-sm backdrop-blur-sm">
        {content}
      </div>
      <Avatar className="h-7 w-7 border-2 border-background shrink-0">
        <AvatarFallback className="bg-primary text-[10px] text-primary-foreground">
          <User className="h-3.5 w-3.5" />
        </AvatarFallback>
      </Avatar>
    </div>
  );
}

function LoadingBubble() {
  return (
    <div className="flex items-start gap-2 animate-in fade-in slide-in-from-left-4 duration-300">
      <Avatar className="h-7 w-7 border-2 border-background shrink-0">
        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-[10px]">
          <Sparkles className="h-3.5 w-3.5" />
        </AvatarFallback>
      </Avatar>
      <div className="flex items-center gap-2.5 rounded-2xl rounded-bl-sm border bg-card px-4 py-3 shadow-sm">
        <TypingDots />
        <span className="text-xs text-muted-foreground/70">Thinking...</span>
      </div>
    </div>
  );
}

function ErrorBubble({ error }: { error: string }) {
  return (
    <div className="flex items-start gap-2 animate-in fade-in slide-in-from-left-4 duration-300">
      <Avatar className="h-7 w-7 border-2 border-background shrink-0">
        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-[10px]">
          <Sparkles className="h-3.5 w-3.5" />
        </AvatarFallback>
      </Avatar>
      <div className="flex items-start gap-2.5 rounded-2xl rounded-bl-sm border border-destructive/30 bg-destructive/10 px-4 py-3 shadow-sm">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
        <p className="text-xs text-destructive">{error}</p>
      </div>
    </div>
  );
}

function ResultBubble({ result }: { result: QueryResult }) {
  const token = useAuthStore((s) => s.token);
  const addToast = useUIStore((s) => s.addToast);
  const [showSql, setShowSql] = useState(true);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const handleCopy = async () => {
    if (!result.sql) return;
    await navigator.clipboard.writeText(result.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFeedback = async (rating: 1 | 2) => {
    if (feedback || !token) return;
    try {
      await fetch(`${API_URL}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query_id: `fb_${Date.now()}`, rating: rating === 1 ? 5 : 1 }),
      });
      setFeedback(rating === 1 ? "up" : "down");
      addToast(rating === 1 ? "Thanks for the feedback!" : "Feedback recorded", "success");
    } catch { /* ignore */ }
  };

  const hasContent = result.explanation || result.sql || (result.columns && result.columns.length > 0);

  return (
    <div className="flex items-start gap-2 animate-in fade-in slide-in-from-left-4 duration-300">
      <Avatar className="h-7 w-7 border-2 border-background shrink-0">
        <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-[10px]">
          <Sparkles className="h-3.5 w-3.5" />
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-2.5">
        {!hasContent && result.sql && (
          <div className="rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-sm shadow-sm">
            <pre className="overflow-x-auto font-mono text-sm leading-relaxed">{result.sql}</pre>
          </div>
        )}

        {result.explanation && (
          <div className="rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-sm leading-relaxed shadow-sm">
            {renderBold(result.explanation)}
          </div>
        )}

        {result.sql && (
          <div className="overflow-hidden rounded-xl border bg-card shadow-sm transition-all duration-200">
            <button
              onClick={() => setShowSql(!showSql)}
              className="flex w-full items-center gap-2 px-4 py-2.5 text-xs font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
            >
              {showSql ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              <span className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                </span>
                SQL
              </span>
              <span className="ml-auto text-[10px] uppercase tracking-widest text-muted-foreground/40">
                {result.total_duration_ms.toFixed(0)}ms
              </span>
            </button>
            {showSql && (
              <div className="border-t">
                <div className="group relative">
                  <pre className="overflow-x-auto bg-[#1e1e2e] p-4 text-sm font-mono leading-relaxed text-[#cdd6f4]">
                    <code>{result.sql}</code>
                  </pre>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="absolute right-2 top-2 h-7 gap-1.5 px-2.5 text-[10px] opacity-0 group-hover:opacity-100 transition-all duration-200 shadow-sm"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <><Check className="h-3 w-3 text-green-500" /> Copied</>
                    ) : (
                      <><Copy className="h-3 w-3" /> Copy</>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}



        <div className="flex items-center gap-0.5 px-1">
          <button
            onClick={() => handleFeedback(1)}
            disabled={!!feedback}
            className={cn(
              "rounded-lg p-1.5 transition-all duration-200",
              feedback === "up"
                ? "text-green-600 bg-green-100 dark:bg-green-950 dark:text-green-400"
                : "text-muted-foreground/50 hover:text-foreground hover:bg-muted/80"
            )}
            aria-label="Good answer"
            title="Helpful"
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => handleFeedback(2)}
            disabled={!!feedback}
            className={cn(
              "rounded-lg p-1.5 transition-all duration-200",
              feedback === "down"
                ? "text-red-600 bg-red-100 dark:bg-red-950 dark:text-red-400"
                : "text-muted-foreground/50 hover:text-foreground hover:bg-muted/80"
            )}
            aria-label="Bad answer"
            title="Not helpful"
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>
          {feedback && (
            <span className="ml-2 text-[10px] text-muted-foreground/60">
              {feedback === "up" ? "Helpful" : "Not helpful"}
            </span>
          )}
        </div>

        {result.error && (
          <div className="flex items-start gap-2.5 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <p className="text-xs text-destructive/90">{result.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const { role, content, result, loading, error } = message;

  if (role === "user") {
    return <UserBubble content={content} />;
  }

  if (loading) {
    return <LoadingBubble />;
  }

  if (error) {
    return <ErrorBubble error={error} />;
  }

  if (result) {
    return <ResultBubble result={result} />;
  }

  if (content) {
    return (
      <div className="flex items-start gap-2 animate-in fade-in slide-in-from-left-4 duration-300">
        <Avatar className="h-7 w-7 border-2 border-background shrink-0">
          <AvatarFallback className="bg-gradient-to-br from-blue-500 to-purple-600 text-white text-[10px]">
            <Sparkles className="h-3.5 w-3.5" />
          </AvatarFallback>
        </Avatar>
        <div className="rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-sm shadow-sm">
          {content}
        </div>
      </div>
    );
  }

  return null;
}
