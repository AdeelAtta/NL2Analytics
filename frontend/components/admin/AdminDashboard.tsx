"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100/api/v1";

interface HealthData {
  status: string; database: string;
}

export function AdminDashboard() {
  const token = useAuthStore((s) => s.token);
  const [health, setHealth] = useState<HealthData | null>(null);

  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/admin/health`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.json())
      .then((d) => setHealth(d.data ?? null))
      .catch(() => {});
  }, [token]);

  const services = [
    { name: "API Server", status: "healthy", icon: "🟢" },
    { name: "Database", status: health?.database ?? "unknown", icon: health?.database === "healthy" ? "🟢" : "🔴" },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {services.map((s) => (
          <Card key={s.name}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">{s.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <span>{s.icon}</span>
                <span className="text-lg font-semibold capitalize">{s.status}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>System Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            System health monitoring. Status checks run on page load.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
