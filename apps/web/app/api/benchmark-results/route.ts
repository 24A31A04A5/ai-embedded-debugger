import { NextResponse } from "next/server";
import { readFileSync } from "fs";
import { join } from "path";

interface BenchmarkMetadata {
  status?: string;
  message?: string;
  version?: string;
}

interface BenchmarkMetrics {
  approach: string;
  total_cases: number;
  successful_cases: number;
  root_cause_accuracy?: number;
  fix_accuracy?: number;
  confidence_accuracy?: number;
  code_issues_accuracy?: number;
  compiler_messages_accuracy?: number;
  serial_log_events_accuracy?: number;
  citation_relevance?: number;
  avg_fabricated_citations?: number;
  avg_missing_citations?: number;
  avg_unsupported_claims?: number;
  high_severity_unsupported_claims?: number;
  uncertainty_handling_rate?: number;
  avg_latency_ms?: number;
  p50_latency_ms?: number;
  p95_latency_ms?: number;
  api_success_rate?: number;
  avg_api_calls_per_case?: number;
}

interface BenchmarkData {
  dev: Record<string, BenchmarkMetrics>;
  holdout: Record<string, BenchmarkMetrics>;
  metadata?: BenchmarkMetadata;
}

export async function GET() {
  try {
    // Try to read the new benchmark runner results first
    const newResultsPath = join(process.cwd(), "..", "..", "tests", "evaluation", "benchmark_results_dev.json");
    const legacyResultsPath = join(process.cwd(), "..", "..", "tests", "evaluation", "benchmark_results.json");

    let data: BenchmarkData = {
      dev: {},
      holdout: {},
      metadata: {
        status: "no_results",
        message: "No benchmark results found. Run the evaluation harness to generate results."
      }
    };

    // Try new format first
    try {
      const fileContent = readFileSync(newResultsPath, "utf-8");
      const parsed = JSON.parse(fileContent);
      data = {
        dev: parsed.dev || {},
        holdout: parsed.holdout || {},
        metadata: parsed.metadata || {},
      };
    } catch {
      // Try legacy format
      try {
        const fileContent = readFileSync(legacyResultsPath, "utf-8");
        const parsed = JSON.parse(fileContent);
        data = {
          dev: parsed.dev || {},
          holdout: parsed.holdout || {},
          metadata: parsed.metadata || { status: "legacy_format" },
        };
      } catch {
        // Return empty structure indicating no results
        data = {
          dev: {},
          holdout: {},
          metadata: {
            status: "no_results",
            message: "No benchmark results found. Run the evaluation harness to generate results."
          }
        };
      }
    }

    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Failed to load benchmark results" }, { status: 500 });
  }
}