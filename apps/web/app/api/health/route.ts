import { NextResponse } from "next/server";

type HealthStatus = "online" | "offline" | "checking";

interface DatabaseCheck {
  status: "ok" | "error";
  reachable: boolean;
}

interface HealthResponse {
  status: HealthStatus;
  latency?: number;
  description: string;
  last_checked: string;
  checks?: Record<string, DatabaseCheck>;
  version?: string;
  benchmark_results_available?: boolean;
  mock_mode?: boolean;
}

// Helper function to get API base URL
function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl || !envUrl.trim()) {
    return "http://localhost:8000";
  }
  return envUrl.trim().replace(/\/+$/, "");
}

/**
 * Returns online/offline status by probing the FastAPI backend health endpoint.
 * This implements Phase 8B spec: probes FastAPI backend and returns status.
 * - "online": FastAPI health endpoint responds with status "ok"
 * - "offline": FastAPI health endpoint unreachable or returns degraded/error
 * - "checking": health check in progress
 */
export async function GET() {
  const startTime = Date.now();

  // Only use mock mode when explicitly set
  const isMockMode = process.env.NEXT_PUBLIC_MOCK_HEALTH_MODE === "true" ||
                     process.env.NEXT_PUBLIC_MOCK_HEALTH_MODE === "1";

  const apiBaseUrl = getApiBaseUrl();
  const healthUrl = `${apiBaseUrl}/health`;

  try {
    const backendResponse = await fetch(healthUrl, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
      // Timeout after 3 seconds
      signal: AbortSignal.timeout(3000),
    });

    const latency = Date.now() - startTime;

    if (backendResponse.ok) {
      const data = await backendResponse.json() as { status: "ok" | "degraded"; checks?: Record<string, DatabaseCheck>; version?: string };

      if (data.status === "ok") {
        const healthResponse: HealthResponse = {
          status: "online",
          latency,
          description: "Backend services available",
          last_checked: new Date().toISOString(),
          version: data.version || "0.1.0",
          checks: data.checks || {},
          mock_mode: isMockMode,
          benchmark_results_available: false,
        };
        return NextResponse.json(healthResponse);
      } else {
        const healthResponse: HealthResponse = {
          status: "offline",
          latency,
          description: "Backend services degraded",
          last_checked: new Date().toISOString(),
          checks: data.checks || {},
          mock_mode: isMockMode,
          benchmark_results_available: false,
        };
        return NextResponse.json(healthResponse);
      }
    } else {
      const healthResponse: HealthResponse = {
        status: "offline",
        latency,
        description: `Backend health check failed: ${backendResponse.status}`,
        last_checked: new Date().toISOString(),
        checks: {},
        mock_mode: isMockMode,
        benchmark_results_available: false,
      };
      return NextResponse.json(healthResponse);
    }
  } catch (error) {
    const latency = Date.now() - startTime;

    // Check if it's an AbortError (timeout)
    const errorMessage = error instanceof Error
      ? error.message
      : "Unknown error";

    const healthResponse: HealthResponse = {
      status: "offline",
      latency,
      description: isMockMode
        ? "Mock mode: simulated backend unavailable"
        : `Unable to reach backend: ${errorMessage}`,
      last_checked: new Date().toISOString(),
      checks: {},
      mock_mode: isMockMode,
      benchmark_results_available: false,
    };
    return NextResponse.json(healthResponse);
  }
}