"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth";
import { useUIStore } from "@/stores/ui";

interface SyncTable { name: string; columns: unknown[] }
interface SyncData { tables: SyncTable[]; added: number; changed: number; removed: number }
interface SavedConn { synced: boolean; connection: { db_type: string; host: string; port: number; database: string; username: string; table_count: number; synced_at: string } | null; table_count: number }

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";
const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "snowflake", label: "Snowflake" },
  { value: "bigquery", label: "BigQuery" },
  { value: "duckdb", label: "DuckDB" },
];

export function ConnectDatabase() {
  const token = useAuthStore((s) => s.token);
  const addToast = useUIStore((s) => s.addToast);

  const [connName, setConnName] = useState("");
  const [dbType, setDbType] = useState("postgresql");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("5432");
  const [dbName, setDbName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [ssl, setSsl] = useState(false);

  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [testResult, setTestResult] = useState<"success" | "error" | null>(null);
  const [syncResult, setSyncResult] = useState<SyncData | null>(null);
  const [savedConn, setSavedConn] = useState<SavedConn | null>(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/sync/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) {
          setSavedConn(d.data);
          if (d.data.connection) {
            const c = d.data.connection;
            setDbType(c.db_type || "postgresql");
            setHost(c.host || "localhost");
            setPort(String(c.port || 5432));
            setDbName(c.database || "");
            setUsername(c.username || "");
          }
        }
      })
      .catch(() => {});
  }, [token]);

  const getConfig = () => ({
    name: connName, db_type: dbType, host, port: parseInt(port), database: dbName, username, password, ssl,
  });

  const handleTest = async () => {
    if (!token) return;
    setTesting(true); setTestResult(null);
    try {
      const r = await fetch(`${API_URL}/sync/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(getConfig()),
      });
      const d = await r.json();
      if (d.success) {
        setTestResult("success");
        addToast("Connection successful!", "success");
      } else {
        setTestResult("error");
        addToast(d.error || "Connection failed", "error");
      }
    } catch {
      setTestResult("error");
      addToast("Connection failed", "error");
    }
    setTesting(false);
  };

  const handleSync = async () => {
    if (!token) return;
    setSyncing(true); setSyncResult(null);
    try {
      const r = await fetch(`${API_URL}/sync/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(getConfig()),
      });
      const d = await r.json();
      if (d.success) {
        setSyncResult(d.data);
        setSavedConn((prev) => prev ? { ...prev, synced: true, table_count: d.data.tables.length, connection: { ...prev.connection!, table_count: d.data.tables.length } } : prev);
        addToast(`Synced ${d.data.tables.length} tables!`, "success");
      } else {
        addToast(d.error || "Sync failed", "error");
      }
    } catch {
      addToast("Sync failed", "error");
    }
    setSyncing(false);
  };

  return (
    <div className="space-y-6">
      {savedConn?.synced && savedConn.connection && (
        <Card>
          <CardHeader>
            <CardTitle>Saved Connection</CardTitle>
            <CardDescription>Last synced: {savedConn.connection.synced_at}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">
                  {savedConn.connection.db_type} — {savedConn.connection.host}:{savedConn.connection.port}/{savedConn.connection.database}
                </p>
                <p className="text-xs text-muted-foreground">
                  {savedConn.table_count} tables synced
                </p>
              </div>
              <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">Connected</span>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{savedConn?.synced ? "Update Connection" : "Connect Database"}</CardTitle>
          <CardDescription>Connect to your database to query your real schema</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="conn-name">Connection Name</Label>
              <Input id="conn-name" value={connName} onChange={(e) => setConnName(e.target.value)} placeholder="My Production DB" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="db-type">Database Type</Label>
              <Select value={dbType} onValueChange={setDbType}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {DB_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="host">Host</Label>
              <Input id="host" value={host} onChange={(e) => setHost(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="port">Port</Label>
              <Input id="port" type="number" value={port} onChange={(e) => setPort(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dbname">Database Name</Label>
              <Input id="dbname" value={dbName} onChange={(e) => setDbName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="flex items-center gap-2 pt-2">
              <input id="ssl" type="checkbox" checked={ssl} onChange={(e) => setSsl(e.target.checked)} className="h-4 w-4 rounded border-gray-300" />
              <Label htmlFor="ssl" className="text-sm font-normal">Use SSL connection</Label>
            </div>
          </div>

          {testResult === "success" && <p className="mt-2 text-sm text-green-600">Connected successfully</p>}
          {testResult === "error" && <p className="mt-2 text-sm text-destructive">Connection failed — check your credentials</p>}

          <div className="mt-4 flex gap-2">
            <Button variant="outline" onClick={handleTest} disabled={testing || !token}>
              {testing ? "Testing..." : "Test Connection"}
            </Button>
            <Button onClick={handleSync} disabled={syncing || !token || testResult !== "success"}>
              {syncing ? "Syncing..." : "Sync Schema"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {syncResult && syncResult.tables && syncResult.tables.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Synced Tables ({syncResult.tables.length})</CardTitle>
            <CardDescription>
              {syncResult.added} added, {syncResult.changed} changed, {syncResult.removed} removed
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {syncResult.tables.map((t: SyncTable, i: number) => (
                <div key={i} className="rounded-lg border p-3">
                  <p className="text-sm font-medium">{t.name}</p>
                  <p className="text-xs text-muted-foreground">{t.columns.length} columns</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
