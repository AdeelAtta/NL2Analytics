"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/auth";
import { useUIStore } from "@/stores/ui";
import { CardSkeleton } from "@/components/ui/skeleton";
import {
  Database, Table2, History, Activity,
  CheckCircle2, XCircle, ArrowRight, ExternalLink,
} from "lucide-react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

interface SyncConnection {
  name: string; db_type: string; host: string; port: number;
  database: string; username: string; table_count?: number;
  synced_at?: string;
}

interface HistoryItem {
  id: string; query: string; sql: string; status: string;
  duration_ms: number; model_tier: string; has_feedback: boolean;
  created_at: string;
}

function timeAgo(iso: string | null) {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function DashboardClient() {
  const token = useAuthStore((s) => s.token);
  const name = useAuthStore((s) => s.name);
  const email = useAuthStore((s) => s.email);
  const addToast = useUIStore((s) => s.addToast);

  const [loading, setLoading] = useState(true);
  const [queryCount, setQueryCount] = useState<number | null>(null);
  const [tableCount, setTableCount] = useState<number | null>(null);
  const [recentQueries, setRecentQueries] = useState<HistoryItem[]>([]);
  const [syncStatus, setSyncStatus] = useState<{
    synced: boolean; table_count: number;
    connection: SyncConnection | null;
  } | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    Promise.allSettled([
      fetch(`${API_URL}/history?page_size=5`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.ok ? r.json() : null)
        .then((d) => {
          setQueryCount(d?.meta?.total ?? 0);
          setRecentQueries(d?.data ?? []);
        }),
      fetch(`${API_URL}/schema/tables?page_size=1`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.ok ? r.json() : null)
        .then((d) => setTableCount(d?.meta?.total ?? 0)),
      fetch(`${API_URL}/sync/status`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => r.ok ? r.json() : null)
        .then((d) => setSyncStatus(d?.data ?? null)),
    ])
      .catch(() => addToast("Could not load dashboard data", "warning"))
      .finally(() => setLoading(false));
  }, [token, addToast]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Welcome{name ? `, ${name}` : ""} — {email || "SchemaIntern"}
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/query">
          <Card className="transition-all hover:border-primary/50 hover:shadow-sm cursor-pointer h-full">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total Queries</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground/60" />
            </CardHeader>
            <CardContent>
              {loading ? <CardSkeleton /> : (
                <>
                  <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                    {queryCount ?? "—"}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Queries executed</p>
                </>
              )}
            </CardContent>
          </Card>
        </Link>

        <Link href="/settings">
          <Card className="transition-all hover:border-primary/50 hover:shadow-sm cursor-pointer h-full">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Connections</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground/60" />
            </CardHeader>
            <CardContent>
              {loading ? <CardSkeleton /> : (
                <>
                  <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                    {syncStatus?.connection ? 1 : 0}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Databases connected</p>
                </>
              )}
            </CardContent>
          </Card>
        </Link>

        <Link href="/schema">
          <Card className="transition-all hover:border-primary/50 hover:shadow-sm cursor-pointer h-full">
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-medium text-muted-foreground">Schema Tables</CardTitle>
              <Table2 className="h-4 w-4 text-muted-foreground/60" />
            </CardHeader>
            <CardContent>
              {loading ? <CardSkeleton /> : (
                <>
                  <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                    {tableCount ?? "—"}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Tables discovered</p>
                </>
              )}
            </CardContent>
          </Card>
        </Link>

        <Card className="h-full">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">Sync Status</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground/60" />
          </CardHeader>
          <CardContent>
            {loading ? <CardSkeleton /> : (
              <>
                <div className="flex items-center gap-2">
                  {syncStatus?.synced ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                  ) : (
                    <XCircle className="h-5 w-5 text-muted-foreground/40" />
                  )}
                  <span className={`text-lg font-semibold ${syncStatus?.synced ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                    {syncStatus?.synced ? "Synced" : "Not synced"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {syncStatus?.table_count ?? 0} tables in registry
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Connections + Recent Queries */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Connections */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Database Connections</CardTitle>
              <CardDescription>Your synced databases</CardDescription>
            </div>
            <Link href="/settings">
              <Button variant="ghost" size="sm" className="gap-1">
                Manage <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3"><CardSkeleton /><CardSkeleton /></div>
            ) : !syncStatus?.connection ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <Database className="h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No databases connected yet</p>
                <Link href="/settings">
                  <Button size="sm" variant="outline">Connect a database</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {(() => {
                  const conn = syncStatus.connection!;
                  return (
                    <div className="flex items-center justify-between rounded-lg border p-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Database className="h-4 w-4 shrink-0 text-muted-foreground" />
                          <span className="text-sm font-medium truncate">{conn.name || conn.database}</span>
                          <span className="shrink-0 rounded-full bg-emerald-100 dark:bg-emerald-950 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:text-emerald-400">
                            synced
                          </span>
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-xs text-muted-foreground">
                          <span>{conn.db_type}</span>
                          <span>{conn.host}:{conn.port}/{conn.database}</span>
                          {syncStatus.table_count > 0 && (
                            <span>{syncStatus.table_count} tables</span>
                          )}
                        </div>
                      </div>
                      <div className="shrink-0 text-right text-[10px] text-muted-foreground/60">
                        <div>{timeAgo(conn.synced_at ?? null)}</div>
                      </div>
                    </div>
                  );
                })()}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Queries */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Recent Queries</CardTitle>
              <CardDescription>Last 5 natural language queries</CardDescription>
            </div>
            <Link href="/query">
              <Button variant="ghost" size="sm" className="gap-1">
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3"><CardSkeleton /><CardSkeleton /></div>
            ) : recentQueries.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <History className="h-8 w-8 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">No queries yet</p>
                <Link href="/query">
                  <Button size="sm" variant="outline">Ask a question</Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {recentQueries.map((q) => (
                  <Link key={q.id} href="/query" className="block">
                    <div className="group flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-accent">
                      <div className={`mt-0.5 shrink-0 rounded-full p-1 ${
                        q.status === "success"
                          ? "bg-emerald-100 dark:bg-emerald-950"
                          : "bg-red-100 dark:bg-red-950"
                      }`}>
                        {q.status === "success"
                          ? <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                          : <XCircle className="h-3 w-3 text-red-600 dark:text-red-400" />
                        }
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                          {q.query}
                        </p>
                        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                          {q.sql && (
                            <code className="truncate max-w-[200px] font-mono text-[10px] opacity-70">
                              {q.sql}
                            </code>
                          )}
                          <span className="shrink-0">{q.duration_ms.toFixed(0)}ms</span>
                          {q.model_tier && <span className="shrink-0 capitalize">{q.model_tier}</span>}
                          <span className="shrink-0">{timeAgo(q.created_at)}</span>
                        </div>
                      </div>
                      <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/30 group-hover:text-foreground transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}