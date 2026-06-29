export default function Page() {
  return (
    <main className="flex h-screen flex-col items-center justify-center gap-3 bg-bg text-text">
      <span className="font-mono text-xs uppercase tracking-[0.12em] text-text-muted">
        Ariadne · Analyst Workbench
      </span>
      <h1
        className="font-sans text-5xl font-semibold text-text"
        style={{ letterSpacing: "-2.4px" }}
      >
        Scaffold ready
      </h1>
      <p className="font-sans text-sm text-text-muted">
        Next.js + Tailwind v4 + Motion + Geist — Woven Dusk tokens wired.
      </p>
    </main>
  );
}
