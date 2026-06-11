function App() {
  return (
    <div className="min-h-svh bg-bg text-text">
      <header className="sticky top-0 z-10 border-b border-border bg-bg/90 backdrop-blur-sm">
        <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <span className="text-sm font-medium tracking-tight">Ariadne</span>
          <div className="flex items-center gap-4">
            <a
              href="#features"
              className="text-sm text-text-muted transition-colors hover:text-text"
            >
              Features
            </a>
            <button
              type="button"
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90"
            >
              Get Started
            </button>
          </div>
        </nav>
      </header>

      <main>
        <section className="mx-auto max-w-5xl px-6 py-24 text-center md:py-32">
          <p className="mb-4 font-mono text-xs uppercase tracking-widest text-primary">
            Woven Dusk
          </p>
          <h1 className="text-4xl font-semibold tracking-[-0.06em] md:text-5xl">
            Follow the thread
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-text-muted">
            Ariadne connects warmth and technical precision — premium without
            feeling cold.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <button
              type="button"
              className="rounded-md bg-primary px-6 py-3 text-sm font-medium text-bg transition-opacity hover:opacity-90"
            >
              Start building
            </button>
            <button
              type="button"
              className="shadow-border rounded-md bg-transparent px-6 py-3 text-sm font-medium text-text transition-colors hover:bg-surface"
            >
              View docs
            </button>
          </div>
        </section>

        <section id="features" className="mx-auto max-w-5xl px-6 pb-24">
          <div className="grid gap-6 md:grid-cols-3">
            <article className="shadow-card rounded-lg bg-surface p-6 text-left">
              <span className="inline-block rounded-full bg-primary/15 px-3 py-1 text-xs font-medium text-primary">
                Teal
              </span>
              <h2 className="mt-4 text-xl font-semibold tracking-[-0.04em]">
                Oxidized precision
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                Primary accents in oxidized teal connect directly to the Ariadne
                thread motif.
              </p>
            </article>
            <article className="shadow-card rounded-lg bg-surface p-6 text-left">
              <span className="inline-block rounded-full bg-secondary/15 px-3 py-1 text-xs font-medium text-secondary">
                Amber
              </span>
              <h2 className="mt-4 text-xl font-semibold tracking-[-0.04em]">
                Warm contrast
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                Antique amber accents prevent the dark theme from reading as
                generic tech chrome.
              </p>
            </article>
            <article className="shadow-card rounded-lg bg-surface p-6 text-left">
              <span className="inline-block rounded-full bg-text-muted/15 px-3 py-1 text-xs font-medium text-text-muted">
                Sage
              </span>
              <h2 className="mt-4 text-xl font-semibold tracking-[-0.04em]">
                Shadow depth
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-text-muted">
                Shadow-as-border replaces traditional CSS borders on dark
                surfaces for subtle elevation.
              </p>
            </article>
          </div>
        </section>
      </main>

      <footer className="border-t border-border py-8 text-center text-sm text-text-muted">
        <p>Ariadne — Woven Dusk design system</p>
      </footer>
    </div>
  )
}

export default App
