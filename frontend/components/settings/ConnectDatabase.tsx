"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth";
import { useUIStore } from "@/stores/ui";
import { X, Database } from "lucide-react";

interface SyncTable { name: string; columns: unknown[] }
interface SyncData { tables: SyncTable[]; added: number; changed: number; removed: number }
interface DbInfo { name: string; database: string; db_type: string; host: string; table_count: number; synced_at: string }

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

  const [connString, setConnString] = useState("");
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
  const [databases, setDatabases] = useState<DbInfo[]>([]);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  const loadStatus = useCallback(() => {
    if (!token) return;
    fetch(`${API_URL}/sync/status`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) {
          setDatabases(d.data.databases ?? []);
        }
      })
      .catch(() => {});
  }, [token]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

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

  const parseConnString = (str: string) => {
    try {
      const url = new URL(str);
      const proto = url.protocol.replace(":", "");
      setDbType(proto === "postgresql" || proto === "postgres" ? "postgresql" : proto);
      setHost(url.hostname);
      setPort(url.port || "5432");
      setDbName(url.pathname.replace(/^\//, ""));
      setUsername(url.username);
      setPassword(url.password || "");
      setConnName(url.pathname.replace(/^\//, "") || "My Database");
      const sslMode = url.searchParams.get("sslmode");
      setSsl(sslMode === "require" || sslMode === "verify-full" || sslMode === "verify-ca");
      addToast("Connection string parsed — review and click Sync Schema", "info");
    } catch {
      addToast("Invalid connection string", "error");
    }
  };

  const handleDemo = () => {
    parseConnString("postgresql://neondb_owner:npg_QNaviT4BOF3l@ep-cold-feather-ah9o0mqs-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require");
    addToast("Periodic Table demo DB filled — click Sync Schema to import", "info");
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
        addToast(`Synced ${d.data.tables.length} tables!`, "success");
        loadStatus();
      } else {
        addToast(d.error || "Sync failed", "error");
      }
    } catch {
      addToast("Sync failed", "error");
    }
    setSyncing(false);
  };

  const handleDisconnect = async (db: string) => {
    if (!token) return;
    setDisconnecting(db);
    try {
      const r = await fetch(`${API_URL}/sync/${encodeURIComponent(db)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await r.json();
      if (d.success) {
        addToast(`Disconnected ${db}`, "success");
        loadStatus();
      } else {
        addToast(d.error || "Disconnect failed", "error");
      }
    } catch {
      addToast("Disconnect failed", "error");
    }
    setDisconnecting(null);
  };

  return (
    <div className="space-y-6">
      {databases.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Connected Databases ({databases.length})</CardTitle>
            <CardDescription>Synced databases available in Query and Schema pages</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {databases.map((db) => (
                <div key={db.database} className="flex items-center justify-between rounded-lg border p-3">
                  <div className="flex items-center gap-3">
                    <Database className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{db.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {db.db_type} — {db.table_count} tables — synced {db.synced_at?.slice(0, 10) || "N/A"}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDisconnect(db.database)}
                    disabled={disconnecting === db.database}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Connect New Database</CardTitle>
          <CardDescription>Connect to your database to query your real schema</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="conn-string">Connection String</Label>
            <div className="flex gap-2">
              <Input id="conn-string" value={connString} onChange={(e) => setConnString(e.target.value)} placeholder="postgresql://user:pass@host:5432/db?sslmode=require" className="flex-1" />
              <Button variant="secondary" size="sm" onClick={() => parseConnString(connString)} disabled={!connString}>
                Parse
              </Button>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
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
            <Button variant="secondary" onClick={handleDemo} disabled={!token}>
              Try Periodic Table Demo
            </Button>
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
