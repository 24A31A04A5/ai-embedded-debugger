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

      // ── Debug ──
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
    }),
    [fetchWithAuth, fetchRawAuth]
  );
}
