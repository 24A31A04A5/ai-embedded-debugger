import { useAuth } from "@clerk/nextjs";
import { useCallback, useMemo } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1";

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
        throw new Error(`API Error: ${response.statusText}`);
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

      // ── Debug (legacy single-shot — kept for backwards compatibility) ──
      analyzeDebug: (
        projectId: string,
        firmwareCode: string,
        compilerOutput: string,
        serialLogs: string
      ) =>
        fetchWithAuth(`/projects/${projectId}/debug`, {
          method: "POST",
          body: JSON.stringify({
            firmware_code: firmwareCode,
            compiler_output: compilerOutput,
            serial_logs: serialLogs,
          }),
        }),

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
        title?: string
      ): Promise<DebugSessionDetail> =>
        fetchWithAuth(`/projects/${projectId}/sessions`, {
          method: "POST",
          body: JSON.stringify({
            title: title || "Untitled Session",
            firmware_code: firmwareCode,
            compiler_output: compilerOutput,
            serial_logs: serialLogs,
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
    }),
    [fetchWithAuth, fetchRawAuth]
  );
}
