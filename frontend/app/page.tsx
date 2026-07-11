import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OpenQuery — Enterprise Text-to-SQL Platform",
  description: "Ask questions about your data in plain English. Get SQL queries instantly.",
};

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
            OQ
          </div>
          <span className="font-semibold text-lg">OpenQuery</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/auth/login" className="text-sm text-muted-foreground hover:text-foreground">
            Sign In
          </Link>
          <Link
            href="/auth/login"
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Get Started
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-5xl px-6 py-20 text-center">
          <h1 className="text-5xl font-bold tracking-tight sm:text-6xl">
            Talk to your data
            <span className="block text-primary mt-2">in plain English</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
            Connect any database and ask questions in natural language.
            OpenQuery generates optimized SQL, executes it safely, and explains the results.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link
              href="/auth/login"
              className="rounded-lg bg-primary px-6 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90"
            >
              Start Free
            </Link>
            <Link
              href="/auth/login"
              className="rounded-lg border px-6 py-3 text-base font-medium hover:bg-accent"
            >
              Sign In
            </Link>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-6 py-16">
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                title: "Multi-Database",
                desc: "Connect PostgreSQL, MySQL, Snowflake, BigQuery, or DuckDB with a single click.",
                icon: "\u{1F5C4}\uFE0F",
              },
              {
                title: "Natural Language",
                desc: "Ask questions like 'show me active users' and get accurate SQL instantly.",
                icon: "\u{1F50D}",
              },
              {
                title: "Safe & Secure",
                desc: "10-layer guardrail stack prevents SQL injection. Read-only enforcement. JWT authentication.",
                icon: "\u{1F512}",
              },
              {
                title: "Self-Learning",
                desc: "Thumbs up/down feedback improves accuracy over time. Your data stays yours.",
                icon: "\u{1F4A1}",
              },
              {
                title: "Schema-Aware",
                desc: "Automatically discovers your schema. No manual configuration needed.",
                icon: "\u{1F9E9}",
              },
              {
                title: "Team Ready",
                desc: "Invite teammates, create API keys, manage roles. Built for organizations.",
                icon: "\u{1F465}",
              },
            ].map((feature) => (
              <div key={feature.title} className="rounded-xl border p-6 text-left">
                <div className="text-2xl mb-3">{feature.icon}</div>
                <h3 className="font-semibold mb-1">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-t bg-muted/30">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-3xl font-bold tracking-tight">Supported Databases</h2>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              {["PostgreSQL", "MySQL", "Snowflake", "BigQuery", "DuckDB"].map((db) => (
                <div key={db} className="rounded-lg border bg-background px-5 py-3 text-sm font-medium">
                  {db}
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t px-6 py-6 text-center text-sm text-muted-foreground">
        <p>OpenQuery &mdash; Enterprise Text-to-SQL Platform</p>
      </footer>
    </div>
  );
}
