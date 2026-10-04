import * as React from "react";
import Link from "next/link";
import { Cpu, FileTerminal, Sparkles } from "lucide-react";

import { LiquidBackdrop } from "@/components/ui/liquid-backdrop";

const HIGHLIGHTS = [
  { icon: FileTerminal, tone: "lg-green", title: "Compiler & linker errors", body: "Trace GCC / Clang diagnostics back to the line that caused them." },
  { icon: Cpu, tone: "lg-white", title: "Serial & UART logs", body: "Spot resets, panics and watchdog loops in device output." },
  { icon: Sparkles, tone: "lg-green", title: "Evidence-aware fixes", body: "Root cause, confidence and a proposed patch you can review." },
];

/** Liquid Glass frame around Clerk's sign-in / sign-up cards. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative isolate flex min-h-dvh flex-col">
      <LiquidBackdrop />

      <header className="flex items-center px-4 pt-4 sm:px-6 sm:pt-6">
        <Link
          href="/"
          className="flex min-h-11 items-center gap-2.5 rounded-full text-sm font-semibold tracking-tight text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/70"
        >
          <img
            src="/brand/ai-embedded-debugger-logo.png"
            alt=""
            width={1536}
            height={1024}
            className="h-10 w-auto shrink-0 object-contain"
          />
          AI Embedded Debugger
        </Link>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-8 sm:px-6">
        <div className="grid w-full max-w-5xl grid-cols-1 items-center gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:gap-14">
          <section className="hidden lg:block" aria-label="About">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-[oklch(0.8_0.1_285)]">Firmware debugging, grounded</p>
            <h1 className="mt-3 max-w-md text-4xl font-semibold leading-tight tracking-tight text-foreground">
              Find the root cause, not just the error.
            </h1>
            <ul className="mt-8 max-w-md space-y-3">
              {HIGHLIGHTS.map(({ icon: Icon, tone, title, body }) => (
                <li key={title} className="lg-glass flex items-start gap-3.5 rounded-[18px] p-4">
                  <span className={`lg-tile lg-tile-lg ${tone}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <div className="flex min-w-0 justify-center">{children}</div>
        </div>
      </main>
    </div>
  );
}
