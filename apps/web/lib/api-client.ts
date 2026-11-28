import { useAuth } from "@clerk/nextjs";
import { useCallback, useMemo } from "react";

import type { DebugResponse } from "../types/debug";

/**
 * Normalizes the configured API URL:
 * - Trims trailing slashes
 * - Appends /v1 if omitted
 * - Falls back to http://localhost:8000/v1 for local development
 */
export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || !envUrl.trim()) {
    return "http://localhost:8000/v1";
  }
  const trimmed = envUrl.trim().replace(/\/+$/, "");
  if (!trimmed.endsWith("/v1")) {
    return `${trimmed}/v1`;
  }
  return trimmed;
}

const API_URL = getApiBaseUrl();

export type ProjectFileMetadata = {
  id: string;
  project_id: string;
  filename: string;
  file_type: "code" | "log";
  size_bytes: number;
  checksum: string;
  created_at: string;
  updated_at: string;
  download_url: string | null;
};

export type ProjectFileContent = {
  metadata: ProjectFileMetadata;
  content: string;
};

/* ── Session types ── */

export type DebugSessionSummary = {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type DebugMessageResponse = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  token_usage: number | null;
  created_at: string;
};

export type DebugSessionDetail = {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: DebugMessageResponse[];
};

/* ── Feedback types ── */

export type FeedbackResponse = {
  id: string;
  user_id: string;
  session_id: string;
  rating: number;
  reason: string | null;
  created_at: string;
};

/* ── Document types (Phase 3.1) ── */

export type DocumentMetadata = {
  id: string;
  project_id: string;
  filename: string;
  version: string | null;
  size_bytes: number;
  checksum: string;
  extraction_status: "pending" | "processing" | "ready" | "failed";
  page_count: number | null;
  download_url: string | null;
  error_message: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type DocumentDetail = DocumentMetadata & {
  extracted_text: string | null;
  text_length: number;
};

/* ── Document Search types (Phase 3.3) ── */

export type DocumentSearchResultItem = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  content: string;
  page_number: number | null;
  chunk_index: number;
  similarity_score: number;
  metadata_json: Record<string, unknown> | null;
};

export type DocumentSearchResponse = {
  query: string;
  results: DocumentSearchResultItem[];
  total_results: number;
};

/* ── Streaming Debug Response types (Phase 11.1) ── */

export type StreamingDebugChunk = {
  type: "text" | "done" | "error";
  content: string;
  timestamp?: string;
};

export type DebugRequestPayload = {
  firmware_code: string;
  compiler_output: string;
  serial_logs: string;
  user_question?: string;
  selected_file_ids?: string[];
  selected_document_ids?: string[];
  session_id?: string;
};

/**
 * Interface for streaming debug client - provides callback-based event handling
 * for SSE/streaming responses.
 */
export interface StreamingDebugClient {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  onData: (callback: (chunk: StreamingDebugChunk) => void) => void;
  onError: (callback: (error: Error) => void) => void;
  onComplete: (callback: () => void) => void;
  cancel: () => void;
}

export function useApiClient() {
  const { getToken } = useAuth();

  const fetchWithAuth = useCallback(
    async (endpoint: string, options: RequestInit = {}) => {
      const token = await getToken();

      const headers = new Headers(options.headers);
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      headers.set("Content-Type", "application/json");

      const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers,
      });

      if (!response.ok) {
        const errorBody = await response.text();
        throw new Error(errorBody || `API Error: ${response.statusText}`);
      }

      // Handle 204 No Content
      if (response.status === 204) return null;

      return response.json();
    },
    [getToken]
  );

  /** Fetch without auto-setting Content-Type (for FormData uploads). */
  const fetchRawAuth = useCallback(
    async (endpoint: string, options: RequestInit = {}) => {
      const token = await getToken();

      const headers = new Headers(options.headers);
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      // Do NOT set Content-Type — browser will set it with multipart boundary

      const response = await fetch(`${API_URL}${endpoint}`, {
        ...options,
        headers,
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || `API Error: ${response.statusText}`);
      }

      if (response.status === 204) return null;
      return response.json();
    },
    [getToken]
  );

  return useMemo(
    () => ({
      // ── Projects ──
      getProjects: () => fetchWithAuth("/projects"),
      createProject: (name: string, description?: string) =>
        fetchWithAuth("/projects", {
          method: "POST",
          body: JSON.stringify({ name, description }),
        }),

      // ── Debug (non-streaming, Phase 11.1 fallback) ──
      analyzeDebug: (
        projectId: string,
        firmwareCode: string,
        compilerOutput: string,
        serialLogs: string,
        options?: {
          userQuestion?: string;
          selectedFileIds?: string[];
          selectedDocumentIds?: string[];
          sessionId?: string;
        }
      ): Promise<DebugResponse> =>
        fetchWithAuth(`/projects/${projectId}/debug`, {
          method: "POST",
          body: JSON.stringify({
            firmware_code: firmwareCode,
            compiler_output: compilerOutput,
            serial_logs: serialLogs,
            user_question: options?.userQuestion,
            selected_file_ids: options?.selectedFileIds,
            selected_document_ids: options?.selectedDocumentIds,
            session_id: options?.sessionId,
          }),
        }),

      // ── Debug Streaming (Phase 11.1) ──
      analyzeDebugStream: async (
        projectId: string,
        firmwareCode: string,
        compilerOutput: string,
        serialLogs: string,
        options?: {
          userQuestion?: string;
          selectedFileIds?: string[];
          selectedDocumentIds?: string[];
          sessionId?: string;
        },
        abortSignal?: AbortSignal
      ): Promise<StreamingDebugClient> => {
        const token = await getToken();

        const queryParams = new URLSearchParams({
          firmware_code: firmwareCode,
          compiler_output: compilerOutput,
          serial_logs: serialLogs,
        });

        if (options?.userQuestion) {
          queryParams.set("user_question", options.userQuestion);
        }
        if (options?.selectedFileIds && options.selectedFileIds.length > 0) {
          queryParams.set("selected_file_ids", options.selectedFileIds.join(","));
        }
        if (options?.selectedDocumentIds && options.selectedDocumentIds.length > 0) {
          queryParams.set("selected_document_ids", options.selectedDocumentIds.join(","));
        }
        if (options?.sessionId) {
          queryParams.set("session_id", options.sessionId);
        }

        const streamUrl = `${API_URL}/projects/${projectId}/debug/stream?${queryParams.toString()}`;

        const headers = new Headers();
        if (token) {
          headers.set("Authorization", `Bearer ${token}`);
        }

        // Build request body as DebugRequest
        const body = JSON.stringify({
            firmware_code: firmwareCode,
            compiler_output: compilerOutput,
            serial_logs: serialLogs,
            user_question: options?.userQuestion,
            selected_file_ids: options?.selectedFileIds,
            selected_document_ids: options?.selectedDocumentIds,
            session_id: options?.sessionId,
        });

        const response = await fetch(streamUrl, {
            method: "POST",
            headers,
            body,
            signal: abortSignal,
        });

        if (!response.ok) {
          const errorBody = await response.text();
          throw new Error(errorBody || `API Error: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No response body for streaming");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let dataCallback: ((chunk: StreamingDebugChunk) => void) | null = null;
        let errorCallback: ((error: Error) => void) | null = null;
        let completeCallback: (() => void) | null = null;
        let isCancelled = false;

        // Helper functions to invoke callbacks safely
        const invokeData = (cb: ((chunk: StreamingDebugChunk) => void) | null, chunk: StreamingDebugChunk): void => {
          if (cb) cb(chunk);
        };
        const invokeError = (cb: ((error: Error) => void) | null, err: Error): void => {
          if (cb) cb(err);
        };
        const invokeComplete = (cb: (() => void) | null): void => {
          if (cb) cb();
        };

        // Process the stream
        (async () => {
          try {
            while (!isCancelled) {
              const { done, value } = await reader.read();
              if (done) {
                invokeComplete(completeCallback);
                break;
              }

              const chunk = decoder.decode(value, { stream: true });
              const lines = chunk.split("\n");

              for (const line of lines) {
                if (line.startsWith("data: ")) {
                  const jsonStr = line.slice(6);
                  try {
                    const parsed = JSON.parse(jsonStr);
                    if (parsed.text) {
                      invokeData(dataCallback, { type: "text", content: parsed.text });
                    } else if (parsed.error) {
                      invokeError(errorCallback, new Error(parsed.error));
                    } else if (parsed.complete) {
                      invokeComplete(completeCallback);
                    }
                  } catch {
                    // Ignore parse errors for malformed SSE data
                  }
                } else if (line.startsWith("event: ")) {
                  const eventType = line.slice(7);
                  if (eventType === "timeout") {
                    invokeError(errorCallback, new Error("Stream timeout reached"));
                  } else if (eventType === "cancelled") {
                    invokeError(errorCallback, new Error("Stream cancelled"));
                  }
                }
              }
            }
          } catch (err) {
            if (!isCancelled && err instanceof DOMException && err.name === "AbortError") {
              // Expected when cancelled
            } else {
              invokeError(errorCallback, err instanceof Error ? err : new Error(String(err)));
            }
          } finally {
            reader.releaseLock();
          }
        })();

        return {
          reader,
          onData: (cb: (chunk: StreamingDebugChunk) => void) => { dataCallback = cb; },
          onError: (cb: (error: Error) => void) => { errorCallback = cb; },
          onComplete: (cb: () => void) => { completeCallback = cb; },
          cancel: () => {
            isCancelled = true;
            reader.cancel();
          },
        };
      },

      // ── Streaming Helper: Create reader for manual streaming ──
      createDebugStreamReader: async (
        _projectId: string,
        _payload: DebugRequestPayload,
        _abortSignal?: AbortSignal
      ): Promise<StreamingDebugClient | null> => {
        // Use the main streaming method
        return null;
      },

      // ── Files ──
      uploadFile: (projectId: string, file: File): Promise<ProjectFileMetadata> => {
        const formData = new FormData();
        formData.append("file", file);
        return fetchRawAuth(`/projects/${projectId}/files/upload`, {
          method: "POST",
          body: formData,
        });
      },

      listFiles: (projectId: string): Promise<ProjectFileMetadata[]> =>
        fetchWithAuth(`/projects/${projectId}/files`),

      getFileContent: (projectId: string, fileId: string): Promise<ProjectFileContent> =>
        fetchWithAuth(`/projects/${projectId}/files/${fileId}`),

      deleteFile: (projectId: string, fileId: string): Promise<null> =>
        fetchWithAuth(`/projects/${projectId}/files/${fileId}`, { method: "DELETE" }),

      // ── Sessions (Phase 2.2) ──
      createSession: (
        projectId: string,
        firmwareCode: string,
        compilerOutput: string,
        serialLogs: string,
        title?: string,
        options?: {
          userQuestion?: string;
          selectedFileIds?: string[];
          selectedDocumentIds?: string[];
        }
      ): Promise<DebugSessionDetail> =>
        fetchWithAuth(`/projects/${projectId}/sessions`, {
          method: "POST",
          body: JSON.stringify({
            title: title || "Untitled Session",
            firmware_code: firmwareCode,
            compiler_output: compilerOutput,
            serial_logs: serialLogs,
            user_question: options?.userQuestion,
            selected_file_ids: options?.selectedFileIds,
            selected_document_ids: options?.selectedDocumentIds,
          }),
        }),

      listSessions: (projectId: string): Promise<DebugSessionSummary[]> =>
        fetchWithAuth(`/projects/${projectId}/sessions`),

      getSession: (projectId: string, sessionId: string): Promise<DebugSessionDetail> =>
        fetchWithAuth(`/projects/${projectId}/sessions/${sessionId}`),

      deleteSession: (projectId: string, sessionId: string): Promise<null> =>
        fetchWithAuth(`/projects/${projectId}/sessions/${sessionId}`, {
          method: "DELETE",
        }),

      // ── Feedback (Phase 2.2) ──
      submitFeedback: (
        sessionId: string,
        rating: number,
        reason?: string
      ): Promise<FeedbackResponse> =>
        fetchWithAuth(`/sessions/${sessionId}/feedback`, {
          method: "POST",
          body: JSON.stringify({ rating, reason: reason || null }),
        }),

      getFeedback: (sessionId: string): Promise<FeedbackResponse | null> =>
        fetchWithAuth(`/sessions/${sessionId}/feedback`),

      // ── Documents (Phase 3.1) ──
      uploadDocument: (
        projectId: string,
        file: File,
        version?: string
      ): Promise<DocumentMetadata> => {
        const formData = new FormData();
        formData.append("file", file);
        if (version) {
          formData.append("version", version);
        }
        return fetchRawAuth(`/projects/${projectId}/documents/upload`, {
          method: "POST",
          body: formData,
        });
      },

      listDocuments: (projectId: string): Promise<DocumentMetadata[]> =>
        fetchWithAuth(`/projects/${projectId}/documents`),

      getDocument: (
        projectId: string,
        documentId: string
      ): Promise<DocumentDetail> =>
        fetchWithAuth(`/projects/${projectId}/documents/${documentId}`),

      deleteDocument: (
        projectId: string,
        documentId: string
      ): Promise<null> =>
        fetchWithAuth(`/projects/${projectId}/documents/${documentId}`, {
          method: "DELETE",
        }),

      // ── Document Search (Phase 3.3) ──
      searchDocuments: (
        projectId: string,
        query: string,
        options?: {
          topK?: number;
          similarityThreshold?: number;
          documentIds?: string[];
        }
      ): Promise<DocumentSearchResponse> =>
        fetchWithAuth(`/projects/${projectId}/documents/search`, {
          method: "POST",
          body: JSON.stringify({
            query,
            top_k: options?.topK ?? 5,
            similarity_threshold: options?.similarityThreshold ?? 0.0,
            document_ids: options?.documentIds,
          }),
        }),

      // ── Serial Connection (Phase 10.1) ──
      testSerialConnection: (
        baudRate: number,
        dataBits: number,
        parity: "none" | "even" | "odd",
        stopBits: number,
        xOnXOff: boolean
      ): Promise<boolean> =>
        fetchWithAuth("/serial/test", {
          method: "POST",
          body: JSON.stringify({
            baud_rate: baudRate,
            data_bits: dataBits,
            parity,
            stop_bits: stopBits,
            x_on_x_off: xOnXOff,
          }),
        }),

      // ── ESP32 Crash Analysis (Phase 10.3) ──
      analyzeCrashLog: (
        projectId: string,
        crashLog: string
      ): Promise<CrashAnalysisResult> =>
        fetchWithAuth(`/projects/${projectId}/crash-analyze`, {
          method: "POST",
          body: JSON.stringify({ crash_log: crashLog }),
        }),
    }),
    [fetchWithAuth, fetchRawAuth]
  );
}

/* ── Crash Analysis Result type (Phase 10.3) ── */
export interface CrashFrame {
  function?: string;
  offset?: number;
  module?: string;
}

export interface CrashBacktrace {
  frames: CrashFrame[];
  full: string;
}

export interface CrashAnalysisResult {
  type: string;
  reason?: string;
  crash?: string;
  registers?: Record<string, string>;
  backtrace?: CrashBacktrace;
  likelyCause: string;
  suggestedActions: string[];
  rawLog: string;
}