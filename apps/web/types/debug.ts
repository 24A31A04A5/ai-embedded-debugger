/* ── Debug Types (Phase 11.1) ──
 * These types mirror the Pydantic schemas in apps/api/app/schemas/debug.py
 */

export type Literal<T extends string> = T;

export type Likelihood = Literal<"high" | "medium" | "low">;
export type Severity = Literal<"critical" | "high" | "medium" | "low" | "info">;
export type MessageType = Literal<
  | "syntax_error"
  | "compile_error"
  | "null_pointer"
  | "dangling_pointer"
  | "pointer_misuse"
  | "buffer_overflow"
  | "out_of_bounds"
  | "uninitialized_variable"
  | "incorrect_type"
  | "incorrect_cast"
  | "memory_leak"
  | "resource_misuse"
  | "logic_error"
  | "control_flow"
  | "peripheral_register"
  | "other"
>;
export type CompilerMessageType = Literal<
  | "error"
  | "warning"
  | "note"
  | "linker_error"
  | "linker_warning"
  | "other"
>;
export type SerialLogEventType = Literal<
  | "runtime_error"
  | "crash_fault"
  | "panic"
  | "watchdog_reset"
  | "brownout_reset"
  | "boot_failure"
  | "timeout"
  | "communication_error"
  | "warning"
  | "repeated_error"
  | "unexpected_value"
  | "timing_anomaly"
  | "info"
  | "other"
>;

export interface DocumentCitation {
  chunk_id?: string;
  document_id?: string;
  document_name: string;
  page_number?: number;
  relevant_snippet?: string;
  relevance_explanation?: string;
}

export interface LikelyCause {
  cause: string;
  plausibility: Likelihood;
}

export interface CodeIssue {
  kind: MessageType;
  severity: Severity;
  confirmed: boolean;
  description: string;
  location?: string;
  evidence?: string;
  suggestion?: string;
}

export interface CompilerMessage {
  message_type: CompilerMessageType;
  severity: Severity;
  is_root_cause: boolean;
  file?: string;
  line?: number;
  column?: number;
  message: string;
  code_context?: string;
  likely_cause?: string;
  suggested_fix?: string;
}

export interface SerialLogEvent {
  event_type: SerialLogEventType;
  severity: Severity;
  is_repeated?: boolean;
  repeat_count?: number;
  timestamp?: string;
  message: string;
  evidence: string;
  likely_cause?: string;
  suggested_action?: string;
}

export interface DebugResponse {
  problem_observed: string;
  root_cause_summary?: string;
  confidence_level?: Likelihood;
  evidence_used: string[];
  likely_causes: LikelyCause[];
  recommended_steps: string[];
  proposed_fix: string;
  corrected_code?: string;
  risks_limitations?: string;
  follow_up_required?: string;
  datasheet_citations?: DocumentCitation[];
  grounded_summary?: string;
  code_issues?: CodeIssue[];
  compiler_messages?: CompilerMessage[];
  serial_log_events?: SerialLogEvent[];
}