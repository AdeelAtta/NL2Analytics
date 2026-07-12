"use client";

import { useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useAuthStore } from "@/stores/auth";
import { useQueryStore } from "@/stores/query";
import { useUIStore } from "@/stores/ui";
import { ChatInput } from "@/components/query/ChatInput";
import { ChatMessage } from "@/components/query/ChatMessage";
import { Sparkles, Database, MessageSquare, Trash2 } from "lucide-react";
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
  const { messages, loading, execute, loadHistory, clearConversation } = useQueryStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hasRun = useRef(false);

  useEffect(() => {
    if (token && isAuth) loadHistory(token);
  }, [token, isAuth, loadHistory]);

  useEffect(() => {
    const qParam = searchParams.get("q");
    if (qParam && !hasRun.current && token && isAuth) {
      hasRun.current = true;
      execute(qParam, token).catch(() => addToast("Query failed", "error"));
    }
  }, [searchParams, token, isAuth, execute, addToast]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(
    (q: string) => {
      if (!token) {
        addToast("Please log in first", "warning");
        return;
      }
      hasRun.current = true;
      execute(q, token).catch(() => addToast("Query failed", "error"));
    },
    [token, execute, addToast],
  );

  const handleClear = () => {
    clearConversation();
    addToast("Conversation cleared", "info");
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Messages area */}
      <div
        ref={containerRef}
        className="mx-auto w-full max-w-3xl flex-1 overflow-y-auto scroll-smooth"
      >
        {isEmpty ? (
          <div className="flex h-full flex-col items-center justify-center gap-8 px-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 shadow-lg ring-1 ring-white/10">
              <Sparkles className="h-8 w-8 text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold tracking-tight">Ask anything about your data</h1>
              <p className="mt-2 text-sm text-muted-foreground max-w-sm">
                Describe the data you&apos;re looking for in plain English
              </p>
            </div>
            <div className="grid w-full max-w-lg gap-2.5 sm:grid-cols-2">
              {EXAMPLE_QUERIES.map((eq) => (
                <button
                  key={eq}
                  onClick={() => handleSend(eq)}
                  className="group flex items-center gap-2.5 rounded-xl border bg-card/50 p-3.5 text-left text-sm transition-all duration-200 hover:border-primary/50 hover:bg-accent hover:shadow-sm"
                >
                  <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground/60 group-hover:text-primary transition-colors" />
                  <span className="line-clamp-1 font-medium">{eq}</span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <Link
                href="/settings"
                className="inline-flex items-center gap-1.5 text-primary hover:underline underline-offset-4"
              >
                <Database className="h-4 w-4" />
                Connect a database
              </Link>
              <span className="text-muted-foreground/30">&middot;</span>
              <Link
                href="/schema"
                className="text-primary hover:underline underline-offset-4"
              >
                Browse schema
              </Link>
            </div>
          </div>
        ) : (
          <>
          <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-background/80 backdrop-blur-sm px-4 py-2.5">
            <h2 className="text-sm font-medium text-muted-foreground">
              {messages.length} message{messages.length !== 1 ? "s" : ""}
            </h2>
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground/60 hover:text-foreground hover:bg-muted/80 transition-all"
            >
              <Trash2 className="h-3.5 w-3.5" />
              New chat
            </button>
          </div>
          <div className="space-y-2 px-4 pb-4 pt-4">
            {messages.map((msg, i) => (
              <div key={msg.id}>
                {i > 0 && messages[i - 1].role === "assistant" && msg.role === "user" && (
                  <div className="pb-4" />
                )}
                <ChatMessage message={msg} />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          </>
        )}
      </div>

      {/* Input area */}
      <div className="border-t bg-background/95 backdrop-blur-sm px-4 py-4">
        <div className="mx-auto flex items-center gap-2">
          <ChatInput onSend={handleSend} disabled={loading || !token} />
          {messages.length > 0 && !loading && (
            <button
              onClick={handleClear}
              className="shrink-0 rounded-lg p-2 text-muted-foreground/50 hover:text-foreground hover:bg-muted/80 transition-all"
              title="Clear conversation"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[10px] text-muted-foreground/40">
          Enter to send &middot; Shift+Enter for new line &middot; Share questions via <code className="text-xs">/query?q=your%20question</code>
        </p>
      </div>
    </div>
  );
}
