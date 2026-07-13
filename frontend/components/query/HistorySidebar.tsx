"use client";

import { useEffect, useMemo, useState } from "react";
import { useAuthStore } from "@/stores/auth";
import { useQueryStore } from "@/stores/query";
import { useUIStore } from "@/stores/ui";
import { apiGet } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { X, Search } from "lucide-react";

interface HistoryItem {
  id: string; query: string; sql: string; status: string;
  duration_ms: number; has_feedback: boolean; created_at: string;
}

export function HistorySidebar() {
  const execute = useQueryStore((s) => s.execute);
  const addToast = useUIStore((s) => s.addToast);
  const token = useAuthStore((s) => s.token);
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiGet<{ data: HistoryItem[] }>("/history?page_size=50")
      .then((d) => setItems(d.data ?? []))
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(
      (i) => i.query.toLowerCase().includes(q) || i.sql.toLowerCase().includes(q)
    );
  }, [items, search]);

  const handleClick = (q: string) => {
    if (token) {
      execute(q, token);
      addToast(`Executing: "${q}"`, "info");
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed right-4 top-4 z-50 rounded-full bg-primary p-2 text-primary-foreground shadow-lg text-xs"
        aria-label="Toggle history"
      >
        {open ? <X className="h-4 w-4" /> : "History"}
      </button>
      {open && (
        <div className="fixed right-0 top-14 z-40 h-[calc(100vh-3.5rem)] w-80 border-l bg-background p-4 shadow-lg overflow-y-auto">
          <div className="mb-3 flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground shrink-0" />
            <Input
              placeholder="Search queries..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <h3 className="mb-3 text-sm font-semibold">
            {search ? `${filtered.length} results` : "Query History"}
          </h3>
          {filtered.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {search ? "No matching queries" : "No queries yet"}
            </p>
          )}
          <div className="space-y-2">
            {filtered.map((item) => (
              <button
                key={item.id}
                onClick={() => handleClick(item.query)}
                className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-accent"
              >
                <p className="line-clamp-1 text-sm font-medium">{item.query}</p>
                <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground font-mono">{item.sql}</p>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span className={`h-1.5 w-1.5 rounded-full ${
                    item.status === "success" ? "bg-green-500" : "bg-red-500"
                  }`} />
                  <span>{item.duration_ms.toFixed(0)}ms</span>
                  {item.has_feedback && <span> &bull; feedback</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
