"use client";

import React, { useEffect, useState } from "react";
import { BarChart, CheckCircle2, AlertCircle, Database, AlertTriangle, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface BenchmarkMetrics {
  approach: string;
  total_cases: number;
  successful_cases: number;
  root_cause_accuracy: number;
  fix_accuracy: number;
  confidence_accuracy: number;
  code_issues_accuracy: number;
  compiler_messages_accuracy: number;
  serial_log_events_accuracy: number;
  citation_relevance: number;
  avg_fabricated_citations: number;
  avg_missing_citations: number;
  avg_unsupported_claims: number;
  high_severity_unsupported_claims: number;
  uncertainty_handling_rate: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  api_success_rate: number;
  avg_api_calls_per_case: number;
}

interface BenchmarkData {
  dev: Record<string, BenchmarkMetrics>;
  holdout: Record<string, BenchmarkMetrics>;
  provenance?: {
    source: "genuine_benchmark" | "mock" | "generated";
    verified: boolean;
    reason?: string;
  };
}

const APPROACH_LABELS: Record<string, { label: string; description: string; color: string }> = {
  plain_gemini: {
    label: "Plain Gemini",
    description: "No prompt engineering, no RAG",
    color: "text-muted-foreground"
  },
  prompt_only: {
    label: "Prompt Only",
    description: "Debugging prompt, no retrieval",
    color: "text-[var(--accent-purple)]"
  },
  full_pipeline: {
    label: "Full Pipeline",
    description: "Prompt + RAG retrieval + grounding",
    color: "text-[var(--color-emerald)]"
  }
};

export function BenchmarkResultsCard() {
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isMockData, setIsMockData] = useState(false);

  useEffect(() => {
    async function fetchResults() {
      try {
        const response = await fetch("/api/benchmark-results");
        if (!response.ok) {
          throw new Error("Failed to fetch benchmark results");
        }
        const json = await response.json();

        // Check provenance first - if source is mock, treat as mock data
        const isProvablyMock = json.provenance?.source === "mock" ||
                               json.provenance?.verified === false ||
                               json.provenance?.reason?.toLowerCase().includes("mock");

        // Check if data is empty (mock/placeholder)
        const hasRealData = json.dev && Object.keys(json.dev).length > 0 &&
                           json.dev.plain_gemini && json.dev.plain_gemini.total_cases > 0;

        if (isProvablyMock || !hasRealData) {
          setIsMockData(true);
          setData(null);
        } else {
          setData(json);
        }
      } catch {
        setIsMockData(true);
      } finally {
        setLoading(false);
      }
    }
    fetchResults();
  }, []);

  if (loading) {
    return (
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <BarChart className="h-4 w-4 text-[var(--accent-purple)]" />
            Benchmark Results
          </CardTitle>
          <CardDescription className="text-xs">
            Grounded pipeline vs baselines on 26 embedded debugging cases (18 dev / 8 holdout)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="p-3 rounded-lg bg-card/60 border border-border/40">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-6 w-full mt-2" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Show "pending" state when no real benchmark data exists
  if (isMockData || !data) {
    return (
      <Card variant="ai" className="relative overflow-hidden border-[var(--color-warning-amber)]/30">
        <div className="absolute -right-10 -top-10 w-40 h-40 bg-[var(--color-warning-amber)]/10 rounded-full blur-3xl pointer-events-none" />

        <CardHeader>
          <div className="flex items-center justify-between gap-2 mb-2">
            <Badge variant="ai" className="gap-1.5">
              <BarChart className="h-3 w-3" />
              <span>Benchmark Results</span>
            </Badge>
            <Badge variant="outline" className="text-[10px] text-[var(--color-warning-amber)] border-[var(--color-warning-amber)]/30">
              Evaluation Pending
            </Badge>
          </div>
          <CardTitle className="text-base font-semibold text-foreground">
            Benchmark Evaluation Pending
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            Real benchmark results require running the evaluation harness against live or mocked AI endpoints.
            The 26-case dataset (18 dev / 8 holdout) is ready. Run the benchmark to generate genuine results.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Status Card */}
          <div className="p-3 rounded-lg bg-[var(--color-warning-amber)]/10 border border-[var(--color-warning-amber)]/30">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-[var(--color-warning-amber)] shrink-0 mt-0.5" />
              <div className="text-xs text-[var(--color-warning-amber)] leading-relaxed">
                <span className="font-medium">Status:</span> No genuine benchmark results available.
                The previous results shown were simulated and have been replaced with this notice.
              </div>
            </div>
          </div>

          {/* Dataset Info */}
          <div className="p-3 rounded-lg bg-card/60 border border-border/40">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-2">
              <Database className="h-3 w-3 text-[var(--accent-indigo)]" />
              <span className="font-medium">Evaluation Dataset Ready</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 rounded bg-[var(--accent-purple)]/10 border border-[var(--accent-purple)]/30">
                <div className="font-medium text-[var(--accent-purple)]">Dev Set</div>
                <div className="text-muted-foreground">18 cases</div>
              </div>
              <div className="p-2 rounded bg-[var(--color-emerald)]/10 border border-[var(--color-emerald)]/30">
                <div className="font-medium text-[var(--color-emerald)]">Holdout Set</div>
                <div className="text-muted-foreground">8 cases</div>
              </div>
            </div>
          </div>

          {/* Run Commands */}
          <div className="p-3 rounded-lg bg-[var(--color-code-bg)] border border-[var(--color-code-border)] font-mono text-[10px] text-foreground/80">
            <div className="text-[var(--accent-purple)] mb-1"># Run development evaluation (mock mode):</div>
            <div className="text-[var(--color-emerald)] mb-2">python tests/evaluation/benchmark_runner.py --split dev --mock --repeat 1</div>
            <div className="text-[var(--accent-purple)] mb-1"># Run holdout evaluation (requires approval):</div>
            <div className="text-[var(--color-emerald)]">python tests/evaluation/benchmark_runner.py --split holdout --mock --repeat 1 --approve-holdout</div>
          </div>

          {/* Metrics Preview (disabled) */}
          <div className="p-3 rounded-lg bg-card/60 border border-border/40 opacity-50">
            <div className="text-xs text-muted-foreground mb-2">Metrics Preview (disabled until real results)</div>
            <div className="grid grid-cols-4 gap-2 text-center">
              {[
                { label: "Root Cause", value: "—" },
                { label: "Fix Accuracy", value: "—" },
                { label: "Citations", value: "—" },
                { label: "Uncertainty", value: "—" },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="text-lg font-bold font-display text-muted-foreground">{value}</div>
                  <div className="text-[10px] text-muted-foreground">{label}</div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const holdout = data.holdout;
  const dev = data.dev;

  const getMetric = (approach: string, key: keyof BenchmarkMetrics, split: "holdout" | "dev" = "holdout"): number => {
    return (data[split][approach]?.[key] as number) ?? 0;
  };

  const formatPct = (val: number | string) => `${Math.round(Number(val) * 100)}%`;

  return (
    <Card variant="ai" className="relative overflow-hidden">
      <div className="absolute -right-10 -top-10 w-40 h-40 bg-[var(--accent-purple)]/10 rounded-full blur-3xl pointer-events-none" />

      <CardHeader>
        <div className="flex items-center justify-between gap-2 mb-2">
          <Badge variant="ai" className="gap-1.5">
            <BarChart className="h-3 w-3" />
            <span>Benchmark Results</span>
          </Badge>
          <Badge variant="outline" className="text-[10px] text-[var(--color-emerald)] border-[var(--color-emerald)]/30">
            Holdout Set (8 cases)
          </Badge>
        </div>
        <CardTitle className="text-base font-semibold text-foreground">
          Grounded Pipeline vs. Baselines
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground">
          Measured on 26 embedded debugging cases (18 dev / 8 holdout). Higher is better for accuracy metrics.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Summary Metrics Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { key: "root_cause_accuracy", label: "Root Cause", icon: Zap, color: "text-[var(--accent-purple)]" },
            { key: "fix_accuracy", label: "Fix Accuracy", icon: CheckCircle2, color: "text-[var(--color-emerald)]" },
            { key: "citation_relevance", label: "Citations", icon: Database, color: "text-[var(--accent-indigo)]" },
            { key: "uncertainty_handling_rate", label: "Uncertainty", icon: AlertTriangle, color: "text-[var(--color-warning-amber)]" }
          ].map(({ key, label, icon: Icon, color }) => (
            <div key={key} className="p-3 rounded-lg bg-card/60 border border-border/40">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
                <Icon className={`h-3 w-3 ${color}`} />
                <span>{label}</span>
              </div>
              <div className="text-xl font-bold font-display text-foreground">
                {formatPct(getMetric("full_pipeline", key as keyof BenchmarkMetrics))}
              </div>
              <div className="text-[10px] text-muted-foreground">
                vs prompt-only: {formatPct(getMetric("prompt_only", key as keyof BenchmarkMetrics))}
              </div>
            </div>
          ))}
        </div>

        {/* Detailed Comparison Table */}
        <div className="rounded-lg border border-border/40 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[var(--accent-purple)]/5 border-b border-border/40">
                <th className="p-2 text-left font-medium text-[var(--accent-purple)]">Approach</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Root Cause</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Fix</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Confidence</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Code Issues</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Compiler</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Serial</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Citations</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Fabricated</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Uncertainty</th>
                <th className="p-2 text-center font-medium text-muted-foreground">Unsupported</th>
              </tr>
            </thead>
            <tbody>
              {["plain_gemini", "prompt_only", "full_pipeline"].map((approach) => {
                const meta = APPROACH_LABELS[approach];
                const metrics = holdout[approach];
                const isBest = approach === "full_pipeline";
                return (
                  <tr key={approach} className={`border-b border-border/30 ${isBest ? "bg-[var(--accent-purple)]/5" : ""}`}>
                    <td className="p-2 font-medium {meta.color}">
                      <div className="flex items-center gap-1.5">
                        {isBest && <CheckCircle2 className="h-3 w-3 text-[var(--color-emerald)]" />}
                        <span>{meta.label}</span>
                      </div>
                      <div className="text-[9px] text-muted-foreground">{meta.description}</div>
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.root_cause_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.fix_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.confidence_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.code_issues_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.compiler_messages_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.serial_log_events_accuracy)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.citation_relevance)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium text-[var(--color-error-red)]">
                      {metrics.avg_fabricated_citations.toFixed(1)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium">
                      {formatPct(metrics.uncertainty_handling_rate)}
                    </td>
                    <td className="p-2 text-center font-mono font-medium text-[var(--color-error-red)]">
                      {metrics.avg_unsupported_claims.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Key Insight */}
        <div className="p-3 rounded-lg bg-[var(--color-emerald)]/10 border border-[var(--color-emerald)]/30">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-[var(--color-emerald)] shrink-0 mt-0.5" />
            <div className="text-xs text-[var(--color-emerald)] leading-relaxed">
              <span className="font-medium">Key Finding:</span> The full grounded pipeline achieves{" "}
              <strong>{formatPct(holdout.full_pipeline.root_cause_accuracy)}</strong> root cause accuracy on holdout cases
              with <strong>{holdout.full_pipeline.avg_fabricated_citations.toFixed(1)} fabricated citations</strong>, compared to{" "}
              <strong>{formatPct(holdout.plain_gemini.root_cause_accuracy)}</strong> for plain Gemini.
              Grounded responses correctly express uncertainty when evidence is insufficient.
            </div>
          </div>
        </div>

        {/* Dev vs Holdout comparison */}
        <div className="text-center text-[10px] text-muted-foreground">
          Dev set (18 cases):{" "}
          {formatPct(dev.full_pipeline.root_cause_accuracy)} root cause |{" "}
          {formatPct(dev.full_pipeline.fix_accuracy)} fix |{" "}
          {formatPct(dev.full_pipeline.citation_relevance)} citations
        </div>
      </CardContent>
    </Card>
  );
}