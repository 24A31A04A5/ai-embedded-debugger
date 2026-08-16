import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/v1";

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

  return {
    getProjects: () => fetchWithAuth("/projects"),
    createProject: (name: string, description?: string) =>
      fetchWithAuth("/projects", {
        method: "POST",
        body: JSON.stringify({ name, description }),
      }),
  };
}
