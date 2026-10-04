"use client";

import * as React from "react";
import { useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  FileSearch,
  Info,
  Layers,
  ListChecks,
  Minus,
  RotateCcw,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { type FeedbackResponse } from "@/lib/api-client";
import { type DiagnosisResult } from "./types";
import { CauseList } from "./CauseList";
import { RecommendedSteps } from "./RecommendedSteps";
import { ProposedFix } from "./ProposedFix";
import { EvidencePanel } from "./EvidencePanel";
import { AIResponseSkeleton } from "./AIResponseSkeleton";

export type AnalysisInputs = {
  source: boolean;
  compiler: boolean;
  serial: boolean;
};

interface AIAnalysisPanelProps {
  diagnosis: DiagnosisResult | null;
  isAnalyzing: boolean;
  sessionId?: string | null;
  feedback?: FeedbackResponse | null;
  onSubmitFeedback?: (rating: number) => void;
  error?: string | null;
  onRetry?: () => void;
  inputs?: AnalysisInputs;
}

type Tone = "neutral" | "ai" | "danger" | "success" | "blue" | "orange" | "teal";

const ORB_TONE: Record<Tone, string> = {
  neutral: "bg-white/[0.08] text-foreground/85",
  ai: "bg-[oklch(0.72_0.17_158/0.22)] lg-green",
  danger: "bg-[var(--apple-red)]/18 lg-red",
  success: "bg-[oklch(0.72_0.17_158/0.22)] lg-green",
  blue: "bg-white/10 lg-white",
  orange: "bg-[oklch(0.72_0.17_158/0.22)] lg-green",
  teal: "bg-white/10 lg-white",
};

const DANGER_SURFACE: React.CSSProperties = {
  background: "linear-gradient(180deg, oklch(0.65 0.2 25 / 0.14), oklch(0.65 0.2 25 / 0.06))",
  boxShadow: "inset 0 0 0 1px oklch(0.65 0.2 25 / 0.28), inset 0 1px 0 oklch(1 0 0 / 0.06)",
};

function Orb({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  return (
    <span
      aria-hidden="true"
      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full shadow-[inset_0_1px_0_oklch(1_0_0/0.16)] ${ORB_TONE[tone]}`}
    >
      {children}
    </span>
  );
}

function InsightCard({
  icon,
  tone = "neutral",
  title,
  aside,
  children,
}: {
  icon: React.ReactNode;
  tone?: Tone;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="lg-card p-3.5" style={tone === "danger" ? DANGER_SURFACE : undefined}>
      <div className="mb-2.5 flex items-center gap-2.5">
        <Orb tone={tone}>{icon}</Orb>
        <h3
          className={`min-w-0 flex-1 truncate text-[13px] font-semibold ${
            tone === "danger" ? "text-[oklch(0.78_0.14_25)]" : "text-foreground"
          }`}
        >
          {title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Progressive-disclosure row for secondary diagnosis details. */
function DetailSection({
  label,
  count,
  defaultOpen = false,
  children,
}: {
  label: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-t border-white/[0.06] first:border-t-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full min-h-11 lg:min-h-9 items-center gap-1.5 px-3.5 text-left text-xs font-medium text-foreground/85 transition-colors hover:bg-white/[0.05] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/60"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
        <span className="flex-1 truncate">{label}</span>
        {typeof count === "number" && (
          <span className="rounded-full bg-white/10 px-1.5 font-mono text-[10px] leading-4 text-muted-foreground">{count}</span>
        )}
      </button>
      {open && <div className="space-y-2 px-3.5 pb-3.5 pt-1">{children}</div>}
    </div>
  );
}

function severityVariant(severity: string) {
  if (severity === "critical" || severity === "high") return "error" as const;
  if (severity === "medium") return "warning" as const;
  return "outline" as const;
}

const ITEM = "space-y-1.5 rounded-xl bg-black/20 p-2.5 shadow-[inset_0_0_0_1px_oklch(1_0_0/0.05)]";

function ConfidenceMeter({ level }: { level: "high" | "medium" | "low" }) {
  const filled = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const color =
    level === "high"
      ? "bg-[var(--color-success-green)]"
      : level === "medium"
        ? "bg-[var(--color-warning-amber)]"
        : "bg-muted-foreground";
  return (
    <div className="flex items-center gap-2.5" aria-label={`Confidence: ${level}`}>
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span key={i} className={`h-1.5 w-7 rounded-full ${i < filled ? color : "bg-white/10"}`} />
        ))}
      </div>
      <span className="text-xs font-medium capitalize text-foreground/90">{level}</span>
    </div>
  );
}

const FEEDBACK_BUTTON =
  "flex h-11 w-11 lg:h-8 lg:w-8 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60";

export function AIAnalysisPanel({
  diagnosis,
  isAnalyzing,
  sessionId,
  feedback,
  onSubmitFeedback,
  error,
  onRetry,
  inputs,
}: AIAnalysisPanelProps) {
  const status = isAnalyzing
    ? { label: "Analyzing", dot: "bg-[var(--accent-purple)] animate-pulse motion-reduce:animate-none", text: "text-white" }
    : error
      ? { label: "Failed", dot: "bg-[var(--color-error-red)]", text: "text-[var(--color-error-red)]" }
      : diagnosis
        ? { label: "Complete", dot: "bg-[var(--color-success-green)]", text: "text-foreground/90" }
        : { label: "Waiting", dot: "bg-muted-foreground/70", text: "text-muted-foreground" };

  const evidenceCount = (diagnosis?.evidence_used?.length ?? 0) + (diagnosis?.datasheet_citations?.length ?? 0);
  const hasDetails = Boolean(
    diagnosis &&
      (diagnosis.likely_causes?.length ||
        diagnosis.code_issues?.length ||
        diagnosis.compiler_messages?.length ||
        diagnosis.serial_log_events?.length ||
        diagnosis.risks_limitations ||
        diagnosis.follow_up_required)
  );

  return (
    <section aria-label="AI debug" className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      {/* Panel title */}
      <div className="flex h-14 lg:h-12 shrink-0 items-center justify-between gap-2 pl-3.5 pr-3">
        <h2 className="flex items-center gap-2.5 text-[13px] font-semibold tracking-tight text-foreground">
          <Orb tone="ai">
            <Sparkles className="h-3.5 w-3.5" />
          </Orb>
          AI Debug
        </h2>
        <span
          role="status"
          aria-live="polite"
          className={`lg-chip flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[11px] ${status.text}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} aria-hidden="true" />
          {status.label}
        </span>
      </div>

      <div className="ide-scroll min-h-0 flex-1 overflow-y-auto px-2.5 pb-3">
        {isAnalyzing && (
          <div className="lg-card">
            <AIResponseSkeleton />
          </div>
        )}

        {!isAnalyzing && error && (
          <div className="space-y-2.5">
            <InsightCard icon={<AlertCircle className="h-3.5 w-3.5" />} tone="danger" title="Analysis failed">
              <p className="text-xs leading-relaxed text-foreground/85 [overflow-wrap:anywhere]">{error}</p>
            </InsightCard>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="lg-chip inline-flex min-h-11 lg:min-h-9 items-center gap-1.5 rounded-full px-4 text-xs font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry analysis
              </button>
            )}
          </div>
        )}

        {!isAnalyzing && !error && !diagnosis && (
          <div className="space-y-2.5">
            <div className="lg-card flex flex-col items-center px-5 py-6 text-center">
              <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-[oklch(0.72_0.16_158/0.55)] to-[oklch(0.42_0.1_158/0.35)] shadow-[inset_0_1px_0_oklch(1_0_0/0.35),inset_0_0_0_1px_oklch(1_0_0/0.12)]">
                <Sparkles className="h-5 w-5 text-white" />
              </span>
              <p className="text-[13px] font-semibold text-foreground">Ready when you are</p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Run <span className="font-medium text-[oklch(0.86_0.14_158)]">Analyze with AI</span> to correlate your source,
                compiler output, and serial logs into a root cause, evidence, and a proposed fix.
              </p>
            </div>
            {inputs && (
              <div className="lg-card p-3.5">
                <h3 className="mb-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Inputs</h3>
                <ul className="space-y-1.5 text-xs">
                  {(
                    [
                      ["Source code", inputs.source],
                      ["Compiler output", inputs.compiler],
                      ["Serial / UART logs", inputs.serial],
                    ] as const
                  ).map(([label, present]) => (
                    <li key={label} className="flex items-center gap-2.5">
                      <span
                        className={`flex h-5 w-5 items-center justify-center rounded-full ${
                          present ? "bg-[var(--color-success-green)]/15" : "bg-white/[0.06]"
                        }`}
                      >
                        {present ? (
                          <Check className="h-3 w-3 text-[var(--color-success-green)]" />
                        ) : (
                          <Minus className="h-3 w-3 text-muted-foreground/60" />
                        )}
                      </span>
                      <span className={present ? "text-foreground/90" : "text-muted-foreground"}>{label}</span>
                      <span className="ml-auto text-[10px] text-muted-foreground/70">{present ? "provided" : "empty"}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {!isAnalyzing && diagnosis && (
          <div className="space-y-2.5">
            {diagnosis.problem_observed && diagnosis.root_cause_summary && (
              <InsightCard icon={<AlertCircle className="h-3.5 w-3.5" />} tone="danger" title="Issue detected">
                <p className="text-[13px] font-medium leading-relaxed text-foreground">{diagnosis.problem_observed}</p>
              </InsightCard>
            )}

            <InsightCard icon={<Search className="h-3.5 w-3.5" />} tone="ai" title="Root cause">
              <p className="text-[13px] leading-relaxed text-foreground/95">
                {diagnosis.root_cause_summary || diagnosis.problem_observed}
              </p>
              {diagnosis.confidence_level && (
                <div className="mt-3 flex items-center justify-between gap-3 border-t border-white/[0.06] pt-2.5">
                  <span className="text-[11px] text-muted-foreground">Confidence</span>
                  <ConfidenceMeter level={diagnosis.confidence_level} />
                </div>
              )}
            </InsightCard>

            {(evidenceCount > 0 || diagnosis.grounded_summary) && (
              <InsightCard
                icon={<FileSearch className="h-3.5 w-3.5" />}
                tone="blue"
                title="Evidence"
                aside={
                  evidenceCount > 0 ? (
                    <span className="font-mono text-[10px] text-muted-foreground/80">
                      {evidenceCount} signal{evidenceCount === 1 ? "" : "s"}
                    </span>
                  ) : undefined
                }
              >
                <EvidencePanel
                  evidence={diagnosis.evidence_used ?? []}
                  citations={diagnosis.datasheet_citations}
                  groundedSummary={diagnosis.grounded_summary}
                />
              </InsightCard>
            )}

            {(diagnosis.proposed_fix || diagnosis.corrected_code) && (
              <InsightCard icon={<Wrench className="h-3.5 w-3.5" />} tone="success" title="Proposed fix">
                <ProposedFix proposedFix={diagnosis.proposed_fix} correctedCode={diagnosis.corrected_code} />
              </InsightCard>
            )}

            {diagnosis.recommended_steps?.length > 0 && (
              <InsightCard icon={<ListChecks className="h-3.5 w-3.5" />} tone="orange" title="Recommended steps">
                <RecommendedSteps steps={diagnosis.recommended_steps} />
              </InsightCard>
            )}

            {hasDetails && (
              <section className="lg-card overflow-hidden" aria-label="More details">
                <div className="flex items-center gap-2.5 px-3.5 pb-2 pt-3">
                  <Orb tone="teal">
                    <Layers className="h-3.5 w-3.5" />
                  </Orb>
                  <h3 className="text-[13px] font-semibold text-foreground">More details</h3>
                </div>

                {diagnosis.likely_causes?.length > 0 && (
                  <DetailSection label="Likely causes" count={diagnosis.likely_causes.length}>
                    <CauseList causes={diagnosis.likely_causes} />
                  </DetailSection>
                )}

                {diagnosis.code_issues && diagnosis.code_issues.length > 0 && (
                  <DetailSection label="Code issues" count={diagnosis.code_issues.length}>
                    {diagnosis.code_issues.map((issue, idx) => (
                      <div key={idx} className={ITEM}>
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-2">
                            <Badge variant={severityVariant(issue.severity)} className="rounded-full px-1.5 font-mono text-[9px] uppercase">
                              {issue.severity}
                            </Badge>
                            <span className="text-xs font-medium capitalize text-foreground">{issue.kind.replace(/_/g, " ")}</span>
                          </div>
                          {issue.location && (
                            <span className="font-mono text-[10px] text-muted-foreground">{issue.location}</span>
                          )}
                        </div>
                        <p className="text-xs leading-relaxed text-foreground/90">{issue.description}</p>
                        {issue.evidence && (
                          <pre className="overflow-x-auto rounded-lg bg-black/30 p-2 font-mono text-[11px] text-muted-foreground">
                            {issue.evidence}
                          </pre>
                        )}
                        {issue.suggestion && (
                          <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                            <span className="font-semibold">Fix: </span>
                            {issue.suggestion}
                          </p>
                        )}
                      </div>
                    ))}
                  </DetailSection>
                )}

                {diagnosis.compiler_messages && diagnosis.compiler_messages.length > 0 && (
                  <DetailSection label="Compiler diagnostics" count={diagnosis.compiler_messages.length}>
                    {diagnosis.compiler_messages.map((msg, idx) => (
                      <div key={idx} className={ITEM}>
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-1.5">
                            {msg.is_root_cause && (
                              <Badge variant="error" className="rounded-full px-1.5 font-mono text-[9px] uppercase">
                                Root cause
                              </Badge>
                            )}
                            <Badge variant="outline" className="rounded-full border-white/15 px-1.5 font-mono text-[9px] uppercase">
                              {msg.message_type.replace(/_/g, " ")}
                            </Badge>
                          </div>
                          {(msg.file || typeof msg.line === "number") && (
                            <span className="font-mono text-[10px] text-muted-foreground">
                              {msg.file || ""}
                              {msg.line ? `:${msg.line}` : ""}
                              {msg.column ? `:${msg.column}` : ""}
                            </span>
                          )}
                        </div>
                        <p className="font-mono text-xs leading-relaxed text-foreground/90 [overflow-wrap:anywhere]">{msg.message}</p>
                        {msg.suggested_fix && (
                          <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                            <span className="font-semibold">Suggestion: </span>
                            {msg.suggested_fix}
                          </p>
                        )}
                      </div>
                    ))}
                  </DetailSection>
                )}

                {diagnosis.serial_log_events && diagnosis.serial_log_events.length > 0 && (
                  <DetailSection label="Serial events" count={diagnosis.serial_log_events.length}>
                    {diagnosis.serial_log_events.map((evt, idx) => (
                      <div key={idx} className={ITEM}>
                        <div className="flex flex-wrap items-center justify-between gap-1.5">
                          <div className="flex items-center gap-2">
                            <Badge variant={severityVariant(evt.severity)} className="rounded-full px-1.5 font-mono text-[9px] uppercase">
                              {evt.event_type.replace(/_/g, " ")}
                            </Badge>
                            {evt.is_repeated && (
                              <span className="font-mono text-[10px] text-[var(--color-warning-amber)]">
                                repeated{evt.repeat_count ? ` ${evt.repeat_count}×` : ""}
                              </span>
                            )}
                          </div>
                          {evt.timestamp && <span className="font-mono text-[10px] text-muted-foreground">{evt.timestamp}</span>}
                        </div>
                        <p className="text-xs leading-relaxed text-foreground/90">{evt.message}</p>
                        {evt.evidence && (
                          <pre className="overflow-x-auto rounded-lg bg-black/30 p-2 font-mono text-[11px] text-muted-foreground">
                            {evt.evidence}
                          </pre>
                        )}
                        {evt.suggested_action && (
                          <p className="text-[11px] leading-relaxed text-[var(--color-success-green)]">
                            <span className="font-semibold">Action: </span>
                            {evt.suggested_action}
                          </p>
                        )}
                      </div>
                    ))}
                  </DetailSection>
                )}

                {diagnosis.risks_limitations && (
                  <DetailSection label="Risks & limitations" defaultOpen>
                    <div className="flex items-start gap-2 text-xs leading-relaxed text-foreground/90">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-warning-amber)]" />
                      <p>{diagnosis.risks_limitations}</p>
                    </div>
                  </DetailSection>
                )}

                {diagnosis.follow_up_required && (
                  <DetailSection label="Follow-up verification" defaultOpen>
                    <div className="flex items-start gap-2 text-xs leading-relaxed text-foreground/90">
                      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-info-blue)]" />
                      <p>{diagnosis.follow_up_required}</p>
                    </div>
                  </DetailSection>
                )}
              </section>
            )}

            {sessionId && onSubmitFeedback && (
              <div className="lg-card flex items-center justify-between gap-3 py-1.5 pl-3.5 pr-1.5">
                <span className="text-xs text-muted-foreground">Was this diagnosis accurate?</span>
                <div className="flex gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={`${FEEDBACK_BUTTON} ${
                          feedback?.rating === 1
                            ? "bg-[var(--color-success-green)]/20 text-[var(--color-success-green)]"
                            : "lg-ghost text-muted-foreground hover:text-[var(--color-success-green)]"
                        }`}
                        onClick={() => onSubmitFeedback(1)}
                        aria-label="Mark diagnosis as helpful"
                        aria-pressed={feedback?.rating === 1}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top">{feedback?.rating === 1 ? "Marked as helpful" : "Mark as helpful"}</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className={`${FEEDBACK_BUTTON} ${
                          feedback?.rating === 0
                            ? "bg-[var(--color-error-red)]/20 text-[var(--color-error-red)]"
                            : "lg-ghost text-muted-foreground hover:text-[var(--color-error-red)]"
                        }`}
                        onClick={() => onSubmitFeedback(0)}
                        aria-label="Mark diagnosis as unhelpful"
                        aria-pressed={feedback?.rating === 0}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top">{feedback?.rating === 0 ? "Marked as unhelpful" : "Mark as unhelpful"}</TooltipContent>
                  </Tooltip>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
