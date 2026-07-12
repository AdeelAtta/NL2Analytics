import type { Metadata } from "next";
import { DashboardClient } from "./DashboardClient";

export const metadata: Metadata = {
  title: "Dashboard — SchemaIntern",
};

export default function DashboardPage() {
  return <DashboardClient />;
}
