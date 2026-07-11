import { create } from "zustand";

export interface StageResult {
  name: string;
  status: string;
  duration_ms: number;
  error?: string;
}

export interface ColumnInfo {
  name: string;
  type: string;
  table: string;
}

export interface QueryResult {
  success: boolean;
  query: string;
  sql: string;
  status: string;
  error?: string;
  explanation?: string;
  columns?: ColumnInfo[];
  stages: StageResult[];
  total_duration_ms: number;
  session_id?: string;
}

interface HistoryItem {
  id: string;
  query: string;
  sql: string;
  status: string;
  duration_ms: number;
  created_at: string;
}

interface QueryState {
  currentQuery: string;
  currentResult: QueryResult | null;
  history: { query: string; sql: string; timestamp: number }[];
  pastQueries: HistoryItem[];
  loading: boolean;
  error: string | null;
  setQuery: (q: string) => void;
  execute: (token: string) => Promise<void>;
  clearResult: () => void;
  loadHistory: (token: string) => Promise<void>;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

export const useQueryStore = create<QueryState>()((set, get) => ({
  currentQuery: "",
  currentResult: null,
  history: [],
  pastQueries: [],
  loading: false,
  error: null,
  setQuery: (q) => set({ currentQuery: q }),
  execute: async (token: string) => {
    const { currentQuery, history } = get();
    if (!currentQuery.trim()) return;
    set({ loading: true, error: null, currentResult: null });
    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: currentQuery, dry_run: true }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API Error [${res.status}]: ${text}`);
      }
      const data: QueryResult = await res.json();
      const sql = data.sql || "";
      set({
        currentResult: data,
        loading: false,
        history: [{ query: currentQuery, sql, timestamp: Date.now() }, ...history].slice(0, 50),
      });
      get().loadHistory(token);
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },
  clearResult: () => set({ currentResult: null, error: null }),
  loadHistory: async (token: string) => {
    try {
      const res = await fetch(`${API_URL}/history?page_size=20`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        set({ pastQueries: data.data ?? [] });
      }
    } catch { /* ignore */ }
  },
}));
