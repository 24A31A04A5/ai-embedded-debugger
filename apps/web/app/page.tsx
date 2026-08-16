import Link from "next/link";
import {
  ArrowRight,
  Bug,
  ChevronRight,
  Code2,
  FileTerminal,
  Lightbulb,
  Search,
  Terminal,
  Upload,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

/* ────────────────────────────────────────────────────────────
   Navbar
   ──────────────────────────────────────────────────────────── */

function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-lg">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Home">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-emerald)]">
            <Bug className="h-4 w-4 text-[var(--color-code-bg)]" />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-foreground">
            AI Embedded Debugger
          </span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex" aria-label="Main navigation">
          <a href="#problem" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Problem
          </a>
          <a href="#how-it-works" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            How It Works
          </a>
          <a href="#capabilities" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Capabilities
          </a>
          <a href="#demo" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
            Demo
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="hidden text-sm sm:inline-flex">
            Sign In
          </Button>
          <Button size="sm" className="text-sm">
            Get Started
          </Button>
        </div>
      </div>
    </header>
  );
}

/* ────────────────────────────────────────────────────────────
   Hero
   ──────────────────────────────────────────────────────────── */

function HeroCodePanel() {
  return (
    <div className="w-full overflow-hidden rounded-xl border border-[var(--color-code-border)] bg-[var(--color-code-bg)] shadow-2xl shadow-black/40">
      {/* Title bar */}
      <div className="flex items-center justify-between border-b border-[var(--color-code-border)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--color-error-red)]/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--color-warning-amber)]/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-[var(--color-success-green)]/60" />
          </div>
          <span className="ml-2 font-mono text-xs text-muted-foreground">main.c — compiler output</span>
        </div>
        <Badge variant="outline" className="border-[var(--color-error-red)]/40 text-[var(--color-error-red)] text-[10px]">
          3 errors
        </Badge>
      </div>
      {/* Code content */}
      <div className="p-4 font-mono text-[13px] leading-6">
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  1 │ </span>
          <span className="text-[var(--color-info-blue)]">#include</span>{" "}
          <span className="text-[var(--color-warning-amber)]">&quot;driver/gpio.h&quot;</span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  2 │ </span>
          <span className="text-[var(--color-info-blue)]">#include</span>{" "}
          <span className="text-[var(--color-warning-amber)]">&quot;freertos/FreeRTOS.h&quot;</span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  3 │ </span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  4 │ </span>
          <span className="text-[var(--color-info-blue)]">void</span>{" "}
          <span className="text-[var(--color-emerald)]">app_main</span>
          <span className="text-foreground/80">(</span>
          <span className="text-[var(--color-info-blue)]">void</span>
          <span className="text-foreground/80">) {"{"}</span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  5 │ </span>
          {"    "}
          <span className="text-foreground/80">gpio_config_t cfg = {"{"}</span>
        </p>
        <p className="bg-[var(--color-error-red)]/8 text-[var(--color-error-red)]">
          <span className="select-none text-[var(--color-error-red)]/40">  6 │ </span>
          {"        "}.pin_bit_mask = GPIO_SEL_2,
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  7 │ </span>
          {"        "}
          <span className="text-foreground/80">.mode = GPIO_MODE_OUPUT,</span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  8 │ </span>
          {"    "}
          <span className="text-foreground/80">{"}"};</span>
        </p>
        <p className="text-muted-foreground">
          <span className="select-none text-muted-foreground/50">  9 │ </span>
          {"    "}
          <span className="text-foreground/80">gpio_config(&cfg);</span>
        </p>

        <div className="mt-3 border-t border-[var(--color-code-border)] pt-3">
          <p className="text-[var(--color-error-red)] text-xs">
            <span className="font-semibold">error:</span> use of undeclared identifier &apos;GPIO_SEL_2&apos;
          </p>
          <p className="text-[var(--color-error-red)] text-xs mt-0.5">
            <span className="font-semibold">error:</span> use of undeclared identifier &apos;GPIO_MODE_OUPUT&apos;
          </p>
          <p className="text-[var(--color-warning-amber)] text-xs mt-0.5">
            <span className="font-semibold">note:</span> did you mean &apos;GPIO_MODE_OUTPUT&apos;?
          </p>
        </div>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="relative pt-14">
      {/* Subtle grid background */}
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          backgroundImage:
            "linear-gradient(to bottom, var(--background) 0%, transparent 15%, transparent 85%, var(--background) 100%), linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
          backgroundSize: "100% 100%, 60px 60px, 60px 60px",
        }}
        aria-hidden="true"
      />

      <div className="mx-auto max-w-6xl px-6 pt-20 pb-16 md:pt-28 md:pb-24">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16 items-center">
          {/* Left — copy */}
          <div className="max-w-xl">
            <Badge
              variant="outline"
              className="mb-5 border-[var(--color-emerald)]/30 text-[var(--color-emerald)] text-xs font-medium"
            >
              <Terminal className="mr-1.5 h-3 w-3" />
              For C/C++ embedded developers
            </Badge>

            <h1 className="text-4xl font-bold leading-[1.15] tracking-tight text-foreground sm:text-5xl lg:text-[3.25rem]">
              AI&#8209;powered debugging
              <br />
              <span className="text-[var(--color-emerald)]">
                for embedded&nbsp;firmware
              </span>
            </h1>

            <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
              Paste your compiler errors and serial logs. Get a structured
              diagnosis, root&#8209;cause analysis, and proposed fixes — backed
              by evidence, not guesswork.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button size="lg" className="gap-2 text-sm font-semibold">
                Start Debugging
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="gap-2 text-sm font-semibold"
              >
                See How It Works
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            <p className="mt-5 text-xs text-muted-foreground/80">
              Free to start · No credit card required
            </p>
          </div>

          {/* Right — code panel */}
          <div className="lg:justify-self-end">
            <HeroCodePanel />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Problem Section
   ──────────────────────────────────────────────────────────── */

const problemItems = [
  {
    icon: FileTerminal,
    title: "Fragmented debugging context",
    description:
      "You constantly switch between your IDE, serial monitor, compiler output, datasheets, forums, and browser tabs. Context is everywhere except in one place.",
  },
  {
    icon: Search,
    title: "Domain-specific reasoning required",
    description:
      "Embedded errors need hardware-aware reasoning — register addresses, timing constraints, peripheral configs. Generic AI tools miss this.",
  },
  {
    icon: Code2,
    title: "Repetitive context re-entry",
    description:
      "Every time you ask a chatbot for help, you re-explain your MCU, toolchain, RTOS, and project setup. There is no persistent project memory.",
  },
];

function ProblemSection() {
  return (
    <section id="problem" className="border-t border-border/60 bg-[var(--color-surface-raised)]">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="max-w-2xl">
          <Badge variant="secondary" className="mb-4 text-xs">
            The Problem
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Debugging embedded firmware is&nbsp;painful
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">
            Embedded developers lose hours every week piecing together information
            scattered across tools, docs, and forums — just to understand a single
            build failure or runtime crash.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {problemItems.map((item) => (
            <article
              key={item.title}
              className="group rounded-xl border border-border/60 bg-card p-6 transition-colors hover:border-border"
            >
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-surface-overlay)]">
                <item.icon className="h-5 w-5 text-[var(--color-emerald)]" />
              </div>
              <h3 className="text-[15px] font-semibold text-foreground">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {item.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   How It Works
   ──────────────────────────────────────────────────────────── */

const steps = [
  {
    number: "01",
    icon: Upload,
    title: "Provide evidence",
    description:
      "Paste or upload your C/C++ source code, compiler errors, and serial monitor output. Add project context like your MCU and toolchain.",
  },
  {
    number: "02",
    icon: Zap,
    title: "AI analyzes the evidence",
    description:
      "The platform combines your code, errors, and logs into a structured analysis context. AI reasons about root causes using embedded-specific knowledge.",
  },
  {
    number: "03",
    icon: Lightbulb,
    title: "Receive diagnosis & fix",
    description:
      "Get a structured diagnosis with ranked causes, verification steps, and corrected code — with clear explanations of what changed and why.",
  },
];

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="border-t border-border/60">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="text-center">
          <Badge variant="secondary" className="mb-4 text-xs">
            How It Works
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Three steps to a&nbsp;fix
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            No vague suggestions. AI Embedded Debugger follows a structured
            evidence → analysis → diagnosis workflow.
          </p>
        </div>

        <div className="mt-14 grid gap-8 lg:grid-cols-3">
          {steps.map((step, i) => (
            <div key={step.number} className="relative">
              {/* Connector line — visible on large screens between cards */}
              {i < steps.length - 1 && (
                <div className="pointer-events-none absolute top-12 left-full hidden h-px w-8 bg-border lg:block" aria-hidden="true" />
              )}
              <div className="rounded-xl border border-border/60 bg-card p-6">
                <div className="mb-4 flex items-center gap-3">
                  <span className="font-mono text-xs font-bold text-[var(--color-emerald)]">{step.number}</span>
                  <div className="h-px flex-1 bg-border/60" />
                  <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--color-surface-overlay)]">
                    <step.icon className="h-4.5 w-4.5 text-[var(--color-emerald)]" />
                  </div>
                </div>
                <h3 className="text-[15px] font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Capabilities
   ──────────────────────────────────────────────────────────── */

const capabilities = [
  {
    icon: FileTerminal,
    title: "Compiler diagnostics",
    description:
      "Understands GCC, Clang, and vendor compiler output. Identifies undeclared identifiers, type mismatches, linker errors, and include issues.",
  },
  {
    icon: Terminal,
    title: "Serial log analysis",
    description:
      "Detects repeated errors, abnormal sequences, crash dumps, and stack traces from UART serial monitor output.",
  },
  {
    icon: Search,
    title: "Evidence-aware reasoning",
    description:
      "Separates what the evidence shows from what is inferred. Explicitly states uncertainty when information is missing.",
  },
  {
    icon: Code2,
    title: "Suggested fixes",
    description:
      "Generates corrected code with diffs and explains why each change was made. Proposes verification steps you can run on your hardware.",
  },
];

function CapabilitiesSection() {
  return (
    <section id="capabilities" className="border-t border-border/60 bg-[var(--color-surface-raised)]">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="text-center">
          <Badge variant="secondary" className="mb-4 text-xs">
            Capabilities
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Built for embedded&nbsp;workflows
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            Not another generic chatbot. Every feature is designed around how
            embedded developers actually debug firmware.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {capabilities.map((cap) => (
            <article
              key={cap.title}
              className="group rounded-xl border border-border/60 bg-card p-6 transition-colors hover:border-border"
            >
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-surface-overlay)]">
                <cap.icon className="h-5 w-5 text-[var(--color-emerald)]" />
              </div>
              <h3 className="text-[15px] font-semibold text-foreground">{cap.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {cap.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Demo — Debugging Panel
   ──────────────────────────────────────────────────────────── */

function DemoSection() {
  return (
    <section id="demo" className="border-t border-border/60">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="text-center">
          <Badge variant="secondary" className="mb-4 text-xs">
            Example
          </Badge>
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            See it in&nbsp;action
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-muted-foreground">
            A realistic ESP32 compiler error — and the AI diagnosis you&apos;d receive.
          </p>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-2">
          {/* Input — compiler error */}
          <div className="overflow-hidden rounded-xl border border-[var(--color-code-border)] bg-[var(--color-code-bg)]">
            <div className="flex items-center gap-2 border-b border-[var(--color-code-border)] px-4 py-2.5">
              <FileTerminal className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono text-xs text-muted-foreground">Compiler Output</span>
              <Badge variant="outline" className="ml-auto border-[var(--color-error-red)]/40 text-[var(--color-error-red)] text-[10px]">
                Error
              </Badge>
            </div>
            <div className="p-4 font-mono text-[12px] leading-6 text-muted-foreground">
              <p className="text-foreground/70">
                $ <span className="text-[var(--color-emerald)]">idf.py</span> build
              </p>
              <p className="mt-2 text-[var(--color-error-red)]">
                main/main.c:6:26: error: use of undeclared identifier
                &apos;GPIO_SEL_2&apos;
              </p>
              <p className="text-muted-foreground/70">
                {"        "}.pin_bit_mask = GPIO_SEL_2,
              </p>
              <p className="text-muted-foreground/70">
                {"                         "}^
              </p>
              <p className="mt-1 text-[var(--color-error-red)]">
                main/main.c:7:17: error: use of undeclared identifier
                &apos;GPIO_MODE_OUPUT&apos;
              </p>
              <p className="text-muted-foreground/70">
                {"        "}.mode = GPIO_MODE_OUPUT,
              </p>
              <p className="text-muted-foreground/70">
                {"                "}^
              </p>
              <p className="mt-1 text-[var(--color-warning-amber)]">
                main/main.c:7:17: note: did you mean &apos;GPIO_MODE_OUTPUT&apos;?
              </p>
              <p className="mt-2 text-[var(--color-error-red)]">
                2 errors generated.
              </p>
            </div>
          </div>

          {/* Output — AI diagnosis */}
          <div className="overflow-hidden rounded-xl border border-[var(--color-emerald)]/20 bg-[var(--color-code-bg)]">
            <div className="flex items-center gap-2 border-b border-[var(--color-emerald)]/20 px-4 py-2.5">
              <Zap className="h-3.5 w-3.5 text-[var(--color-emerald)]" />
              <span className="font-mono text-xs text-[var(--color-emerald)]">AI Diagnosis</span>
              <Badge variant="outline" className="ml-auto border-[var(--color-emerald)]/30 text-[var(--color-emerald)] text-[10px]">
                2 issues found
              </Badge>
            </div>
            <div className="p-4 text-[13px] leading-relaxed">
              <div>
                <h4 className="font-semibold text-foreground">Problem Observed</h4>
                <p className="mt-1 text-sm text-muted-foreground">
                  Build fails with 2 undeclared identifier errors in GPIO
                  configuration for ESP-IDF project.
                </p>
              </div>

              <div className="mt-4">
                <h4 className="font-semibold text-foreground">Likely Causes</h4>
                <ol className="mt-1.5 space-y-1.5 text-sm text-muted-foreground">
                  <li className="flex gap-2">
                    <span className="mt-0.5 flex h-4 min-w-4 items-center justify-center rounded bg-[var(--color-emerald)]/15 font-mono text-[10px] font-bold text-[var(--color-emerald)]">1</span>
                    <span>
                      <span className="font-medium text-foreground/90">API migration:</span>{" "}
                      <code className="rounded bg-[var(--color-surface-overlay)] px-1 py-0.5 font-mono text-xs">GPIO_SEL_2</code> was removed in ESP-IDF v5.x. Use{" "}
                      <code className="rounded bg-[var(--color-surface-overlay)] px-1 py-0.5 font-mono text-xs text-[var(--color-emerald)]">BIT64(2)</code> or{" "}
                      <code className="rounded bg-[var(--color-surface-overlay)] px-1 py-0.5 font-mono text-xs text-[var(--color-emerald)]">(1ULL {"<<"} 2)</code>.
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-0.5 flex h-4 min-w-4 items-center justify-center rounded bg-[var(--color-emerald)]/15 font-mono text-[10px] font-bold text-[var(--color-emerald)]">2</span>
                    <span>
                      <span className="font-medium text-foreground/90">Typo:</span>{" "}
                      <code className="rounded bg-[var(--color-surface-overlay)] px-1 py-0.5 font-mono text-xs text-[var(--color-error-red)]">GPIO_MODE_OUPUT</code> →{" "}
                      <code className="rounded bg-[var(--color-surface-overlay)] px-1 py-0.5 font-mono text-xs text-[var(--color-emerald)]">GPIO_MODE_OUTPUT</code> (missing &apos;T&apos;).
                    </span>
                  </li>
                </ol>
              </div>

              <div className="mt-4">
                <h4 className="font-semibold text-foreground">Proposed Fix</h4>
                <div className="mt-1.5 overflow-hidden rounded-lg border border-[var(--color-code-border)] bg-[var(--color-code-bg)] font-mono text-xs leading-6">
                  <div className="flex items-center gap-2 border-b border-[var(--color-code-border)] px-3 py-1.5 text-muted-foreground/60">
                    <span>main.c — diff</span>
                  </div>
                  <div className="px-3 py-2">
                    <p className="text-[var(--color-error-red)]">
                      - .pin_bit_mask = GPIO_SEL_2,
                    </p>
                    <p className="text-[var(--color-emerald)]">
                      + .pin_bit_mask = (1ULL {"<<"} 2),
                    </p>
                    <p className="text-[var(--color-error-red)]">
                      - .mode = GPIO_MODE_OUPUT,
                    </p>
                    <p className="text-[var(--color-emerald)]">
                      + .mode = GPIO_MODE_OUTPUT,
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   CTA
   ──────────────────────────────────────────────────────────── */

function CTASection() {
  return (
    <section className="border-t border-border/60 bg-[var(--color-surface-raised)]">
      <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
            Stop guessing.
            <br />
            <span className="text-[var(--color-emerald)]">Start debugging.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">
            Paste your first compiler error or serial log and get an
            evidence&#8209;aware diagnosis in seconds.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" className="gap-2 text-sm font-semibold">
              Start Debugging
              <ArrowRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="lg" className="gap-2 text-sm font-semibold">
              View Documentation
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Footer
   ──────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--color-emerald)]">
              <Bug className="h-3 w-3 text-[var(--color-code-bg)]" />
            </div>
            <span className="text-sm font-semibold text-foreground">
              AI Embedded Debugger
            </span>
          </div>

          <nav className="flex items-center gap-6" aria-label="Footer navigation">
            <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              Documentation
            </a>
            <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              GitHub
            </a>
            <a href="#" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
              Privacy
            </a>
          </nav>

          <p className="text-xs text-muted-foreground/60">
            &copy; {new Date().getFullYear()} AI Embedded Debugger
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ────────────────────────────────────────────────────────────
   Page
   ──────────────────────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <ProblemSection />
        <HowItWorksSection />
        <CapabilitiesSection />
        <DemoSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
