/**
 * Pure helpers for the homepage API health indicator (Phase 8B).
 *
 * Kept free of React and of other imports so they can be unit-tested with
 * `node --test` (see lib/__tests__/health-status.test.mjs).
 */

export type HealthStatus = "checking" | "online" | "offline";

/** Per-request timeout. */
export const HEALTH_TIMEOUT_MS = 5_000;
/**
 * Render Free instances can take ~50 s to wake. Failures inside this window
 * (measured from the start of a check cycle) keep the indicator in a
 * "Waking server…" checking state instead of declaring the API offline.
 */
export const WAKE_WINDOW_MS = 60_000;
/** Pause between attempts inside one check cycle. */
export const WAKE_RETRY_DELAY_MS = 2_000;
/** Background re-check interval, only while the tab is visible. */
export const POLL_INTERVAL_MS = 60_000;

/**
 * The health router is mounted at the API root (`/health`) as well as under
 * `/v1`. NEXT_PUBLIC_API_URL may or may not already end in `/v1`.
 */
export function healthUrl(apiBase: string): string {
  const root = apiBase.trim().replace(/\/+$/, "").replace(/\/v1$/, "");
  return `${root}/health`;
}

export type HealthInterpretation = { online: boolean; degraded: boolean };

/**
 * `/health` answers 200 with `{status: "ok" | "degraded"}`; "degraded" means
 * the API is up but its database probe failed.
 */
export function interpretHealthResponse(httpOk: boolean, body: unknown): HealthInterpretation {
  if (!httpOk) return { online: false, degraded: false };
  const status =
    body && typeof body === "object" && "status" in body
      ? (body as { status?: unknown }).status
      : undefined;
  if (status === "ok") return { online: true, degraded: false };
  if (status === "degraded") return { online: true, degraded: true };
  // 2xx without a recognisable body: reachable, but we cannot vouch for it.
  return { online: true, degraded: true };
}

/**
 * After a failed attempt: keep trying (server may be waking) while the cycle
 * is younger than the wake window, otherwise give up and report offline.
 */
export function afterFailure(
  cycleElapsedMs: number,
  wakeWindowMs: number = WAKE_WINDOW_MS,
): "retry" | "offline" {
  return cycleElapsedMs < wakeWindowMs ? "retry" : "offline";
}

/** Background polling: only when visible and the last check is old enough. */
export function shouldPoll(
  visibility: string,
  lastCheckedAt: number | null,
  now: number,
  intervalMs: number = POLL_INTERVAL_MS,
): boolean {
  if (visibility !== "visible") return false;
  if (lastCheckedAt === null) return true;
  return now - lastCheckedAt >= intervalMs;
}

/** Latency text, or null when nothing was measured. */
export function formatLatency(ms: number | null | undefined): string | null {
  if (ms === null || ms === undefined || !Number.isFinite(ms) || ms < 0) return null;
  if (ms < 1_000) return `${Math.round(ms)} ms`;
  return `${(ms / 1_000).toFixed(1)} s`;
}
