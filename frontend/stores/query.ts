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

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  result?: QueryResult | null;
  loading?: boolean;
  error?: string | null;
}

interface QueryState {
  messages: ChatMessage[];
  pastQueries: HistoryItem[];
  loading: boolean;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (update: Partial<ChatMessage>) => void;
  execute: (query: string, token: string) => Promise<void>;
  loadHistory: (token: string) => Promise<void>;
  clearConversation: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

let msgId = 0;
const nextId = () => `msg_${Date.now()}_${++msgId}`;

export const useQueryStore = create<QueryState>()((set, get) => ({
  messages: [],
  pastQueries: [],
  loading: false,

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

  updateLastAssistant: (update) =>
    set((s) => {
      const msgs = [...s.messages];
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === "assistant") {
          msgs[i] = { ...msgs[i], ...update };
          break;
        }
      }
      return { messages: msgs };
    }),

  execute: async (query: string, token: string) => {
    if (!query.trim()) return;

    const userMsg: ChatMessage = { id: nextId(), role: "user", content: query };
    const assistantMsg: ChatMessage = {
      id: nextId(),
      role: "assistant",
      content: "",
      loading: true,
      error: null,
      result: null,
    };

    set((s) => ({ messages: [...s.messages, userMsg, assistantMsg], loading: true }));

    try {
      const res = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query, dry_run: true }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API Error [${res.status}]: ${text}`);
      }
      const data: QueryResult = await res.json();
      get().updateLastAssistant({ result: data, loading: false, error: null });
      set({ loading: false });
      get().loadHistory(token);
    } catch (e) {
      get().updateLastAssistant({
        loading: false,
        error: (e as Error).message,
        result: null,
      });
      set({ loading: false });
    }
  },

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

  clearConversation: () => set({ messages: [], loading: false }),
}));
