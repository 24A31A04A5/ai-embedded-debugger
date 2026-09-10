export type LikelyCause = {
  cause: string;
  plausibility: "high" | "medium" | "low";
};

export type DocumentCitation = {
  chunk_id?: string | null;
  document_id?: string | null;
  document_name: string;
  page_number?: number | null;
  relevant_snippet?: string | null;
  relevance_explanation?: string | null;
};

export type CodeIssue = {
  kind: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  confirmed: boolean;
  description: string;
  location?: string | null;
  evidence?: string | null;
  suggestion?: string | null;
};

export type CompilerMessage = {
  message_type: "error" | "warning" | "note" | "linker_error" | "linker_warning" | "other";
  severity: "critical" | "high" | "medium" | "low" | "info";
  is_root_cause: boolean;
  file?: string | null;
  line?: number | null;
  column?: number | null;
  message: string;
  code_context?: string | null;
  likely_cause?: string | null;
  suggested_fix?: string | null;
};

export type SerialLogEvent = {
  event_type: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  is_repeated: boolean;
  repeat_count?: number | null;
  timestamp?: string | null;
  message: string;
  evidence: string;
  likely_cause?: string | null;
  suggested_action?: string | null;
};

export type DiagnosisResult = {
  problem_observed: string;
  root_cause_summary?: string | null;
  confidence_level?: "high" | "medium" | "low" | null;
  evidence_used: string[];
  likely_causes: LikelyCause[];
  recommended_steps: string[];
  proposed_fix: string;
  corrected_code?: string | null;
  risks_limitations?: string | null;
  follow_up_required?: string | null;
  datasheet_citations?: DocumentCitation[] | null;
  grounded_summary?: string | null;
  code_issues?: CodeIssue[] | null;
  compiler_messages?: CompilerMessage[] | null;
  serial_log_events?: SerialLogEvent[] | null;
};

