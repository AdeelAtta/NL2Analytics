import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SchemaIntern — DB-Aware NL to SQL",
  description:
    "Stop writing SQL. SchemaIntern understands your database schema and converts plain English into accurate, safe SQL queries in seconds.",
};

const statCards = [
  { value: "10x", label: "Faster than writing SQL manually" },
  { value: "Zero", label: "SQL knowledge required from your team" },
  { value: "99.7%", label: "Guardrail pass rate on enterprise schemas" },
  { value: "5+", label: "Database engines supported out of the box" },
];

const problems = [
  {
    title: "Your team wastes hours writing SQL",
    desc: "Every 'can you pull me this data?' request becomes a 30-minute distraction for engineers. Analytics teams wait days for queries from busy DBAs.",
    stat: "Analysts spend 60% of their time writing SQL queries instead of analyzing results.",
    icon: "\u231B",
  },
  {
    title: "Schema complexity slows everyone down",
    desc: "JOINs across 15 tables, cryptic column names, undocumented relationships. New team members take weeks to learn the schema.",
    stat: "Average enterprise schema has 200+ tables. Most teams use under 20 regularly.",
    icon: "\u{1F9E9}",
  },
  {
    title: "SQL errors are costly and risky",
    desc: "Missing WHERE clauses cause accidental full-table scans. Wrong JOINs produce incorrect reports. Direct DB access is a security risk.",
    stat: "40% of self-serve SQL queries contain errors that lead to bad decisions.",
    icon: "\u26A0\uFE0F",
  },
  {
    title: "Data access is a bottleneck",
    desc: "Every insight requires a ticket, a wait, and context-switching. Business moves fast, but data access moves at the speed of the engineering backlog.",
    stat: "Teams with self-serve analytics report 3x faster time-to-insight.",
    icon: "\u{1F50C}",
  },
];

const solutions = [
  {
    title: "Natural Language, Not SQL",
    desc: "Ask 'how many active users signed up last quarter?' and get the answer — no SQL required. SchemaIntern handles the translation.",
    icon: "\u{1F4AC}",
  },
  {
    title: "Schema-Aware from Day One",
    desc: "Connect once, and SchemaIntern automatically discovers your tables, columns, relationships, and sample data. It understands your schema better than most engineers.",
    icon: "\u{1F50D}",
  },
  {
    title: "10-Layer Enterprise Guardrails",
    desc: "Every generated SQL passes through read-only enforcement, injection prevention, timeout limits, cost estimation, and schema validation before execution.",
    icon: "\u{1F6E1}\uFE0F",
  },
  {
    title: "Self-Learning with Feedback",
    desc: "Thumbs up or down on every response. SchemaIntern learns from your team's corrections and gets smarter over time, adapting to your specific data domain.",
    icon: "\u{1F4A1}",
  },
];

const useCases = [
  {
    title: "Analytics Teams",
    desc: "Self-serve data exploration without engineering dependencies. Ask questions, get answers, iterate in real-time.",
    icon: "\u{1F4CA}",
  },
  {
    title: "Product Managers",
    desc: "Pull user behavior data, conversion metrics, and funnel analysis on demand. No ticket needed.",
    icon: "\u{1F3AF}",
  },
  {
    title: "Data Engineers",
    desc: "Validate queries, explore unfamiliar schemas, and generate boilerplate SQL in seconds instead of minutes.",
    icon: "\u{2699}\uFE0F",
  },
  {
    title: "Business Leaders",
    desc: "Get answers to strategic questions without waiting for reports. Data-driven decisions, instantly.",
    icon: "\u{1F3C6}",
  },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Nav */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-sm px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-2.5">
            <img src="/schemaintern_logo.png" alt="SchemaIntern" className="h-8 w-8" />
            <span className="font-semibold text-lg">Schema<span className="text-primary">Intern</span></span>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/auth/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Sign In
            </Link>
            <Link
              href="/auth/login"
              className="rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all shadow-sm"
            >
              Start Free
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-6 pt-20 pb-16 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-1.5 text-xs font-medium text-muted-foreground mb-8">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Schema-Aware NL to SQL — Now in Beta
          </div>
          <h1 className="text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
            Stop writing SQL.
            <br />
            <span className="text-primary">Start asking questions.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground leading-relaxed">
            SchemaIntern knows your database schema — tables, columns, relationships, and sample data.
            Ask any question in plain English, and get accurate, safe SQL instantly.
            No SQL training required. No engineering bottleneck.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link
              href="/auth/login"
              className="rounded-lg bg-primary px-8 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-all shadow-md hover:shadow-lg"
            >
              Try SchemaIntern Free
            </Link>
            <Link
              href="/auth/login"
              className="rounded-lg border px-8 py-3 text-base font-medium hover:bg-accent transition-all"
            >
              Sign In
            </Link>
          </div>
          <p className="mt-4 text-xs text-muted-foreground/60">
            No credit card required &middot; Connect your own database &middot; Full schema discovery in seconds
          </p>
        </section>

        {/* Social proof / stats bar */}
        <section className="border-y bg-muted/30">
          <div className="mx-auto max-w-6xl px-6 py-10">
            <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
              {statCards.map((s) => (
                <div key={s.label} className="text-center">
                  <div className="text-3xl font-bold text-primary">{s.value}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* The Problem */}
        <section className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              The data access problem
            </h2>
            <p className="mt-3 text-muted-foreground max-w-2xl mx-auto">
              Every organization collects more data than it can use. The bottleneck isn&apos;t storage — it&apos;s the gap between the people who have questions and the people who can write SQL.
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {problems.map((p) => (
              <div key={p.title} className="rounded-xl border bg-card p-6 text-left">
                <div className="text-3xl mb-3">{p.icon}</div>
                <h3 className="font-semibold text-lg mb-1">{p.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{p.desc}</p>
                <div className="mt-3 rounded-lg bg-muted/50 border px-3 py-2">
                  <p className="text-xs text-muted-foreground italic">{p.stat}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* The Solution */}
        <section className="border-t bg-muted/30">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 rounded-full border bg-background px-4 py-1.5 text-xs font-medium text-primary mb-4">
                How SchemaIntern Works
              </div>
              <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
                From question to answer in seconds
              </h2>
              <p className="mt-3 text-muted-foreground max-w-2xl mx-auto">
                Connect your database once. SchemaIntern discovers your schema, understands your data model, and translates natural language into optimized SQL — every time.
              </p>
            </div>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {solutions.map((s, i) => (
                <div key={s.title} className="rounded-xl border bg-card p-6 text-left">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">
                      {i + 1}
                    </span>
                    <span className="text-2xl">{s.icon}</span>
                  </div>
                  <h3 className="font-semibold mb-1">{s.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{s.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Market Value / Use Cases */}
        <section className="mx-auto max-w-6xl px-6 py-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Built for every role in your organization
            </h2>
            <p className="mt-3 text-muted-foreground max-w-2xl mx-auto">
              SchemaIntern democratizes data access. Whether you&apos;re a CEO needing a quick number or an analyst deep-diving into trends — the answer is one question away.
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {useCases.map((u) => (
              <div key={u.title} className="rounded-xl border bg-card p-6 text-left hover:border-primary/30 transition-colors">
                <div className="text-3xl mb-3">{u.icon}</div>
                <h3 className="font-semibold mb-1">{u.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{u.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Supported DBs */}
        <section className="border-t bg-muted/30">
          <div className="mx-auto max-w-3xl px-6 py-16 text-center">
            <h2 className="text-2xl font-bold tracking-tight">Works with your existing database</h2>
            <p className="mt-2 text-sm text-muted-foreground">
              No migration needed. Connect and query in minutes.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              {[
                { name: "PostgreSQL", icon: "\u{1F4BE}" },
                { name: "MySQL", icon: "\u{1F4F1}" },
                { name: "Snowflake", icon: "\u2744\uFE0F" },
                { name: "BigQuery", icon: "\u2601\uFE0F" },
                { name: "DuckDB", icon: "\u{1F425}" },
              ].map((db) => (
                <div key={db.name} className="flex items-center gap-2 rounded-lg border bg-background px-4 py-2.5 text-sm font-medium shadow-sm">
                  <span>{db.icon}</span>
                  <span>{db.name}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Final CTA */}
        <section className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Stop waiting for SQL. Start asking questions.
          </h2>
          <p className="mt-3 text-muted-foreground">
            Connect your database in under 60 seconds. SchemaIntern will discover your schema and be ready to answer questions immediately.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link
              href="/auth/login"
              className="rounded-lg bg-primary px-8 py-3 text-base font-medium text-primary-foreground hover:bg-primary/90 transition-all shadow-md hover:shadow-lg"
            >
              Get Started Free
            </Link>
            <Link
              href="/auth/login"
              className="rounded-lg border px-8 py-3 text-base font-medium hover:bg-accent transition-all"
            >
              Sign In
            </Link>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t px-6 py-8">
        <div className="mx-auto max-w-6xl flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <img src="/schemaintern_logo.png" alt="SchemaIntern" className="h-6 w-6" />
            <span>Schema<span className="text-primary">Intern</span> &mdash; DB-Aware NL to SQL</span>
          </div>
          <p className="text-xs text-muted-foreground/60">
            &copy; {new Date().getFullYear()} SchemaIntern. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
