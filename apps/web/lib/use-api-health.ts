"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getApiBaseUrl } from "@/lib/api-client";
import {
  HEALTH_TIMEOUT_MS,
  POLL_INTERVAL_MS,
  WAKE_RETRY_DELAY_MS,
  afterFailure,
  healthUrl,
  interpretHealthResponse,
  shouldPoll,
  type HealthStatus,
} from "@/lib/health-status";

export type ApiHealth = {
  status: HealthStatus;
  /** True while a failed attempt is being retried inside the wake window. */
  waking: boolean;
  /** API answered but reported its database probe as failing. */
  degraded: boolean;
  /** Round-trip time of the request that produced `status: "online"`; null otherwise. */
  latencyMs: number | null;
  /** Wall-clock time the last check cycle finished. */
  checkedAt: number | null;
};

const INITIAL: ApiHealth = {
  status: "checking",
  waking: false,
  degraded: false,
  latencyMs: null,
  checkedAt: null,
};

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const t = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(t);
      resolve();
    });
  });
}

/**
 * Real API health: GET {API root}/health with a 5 s timeout per attempt.
 * One check on mount, then every 60 s only while the tab is visible, plus a
 * manual `retry()`. Failures within the first 60 s of a cycle are reported as
 * "checking / waking" (Render Free cold start) rather than offline.
 */
export function useApiHealth(): ApiHealth & { retry: () => void } {
  const [health, setHealth] = useState<ApiHealth>(INITIAL);
  const runningRef = useRef(false);
  const lastCheckedRef = useRef<number | null>(null);
  const lifeRef = useRef<AbortController | null>(null);

  const runCycle = useCallback(async () => {
    const life = lifeRef.current;
    if (!life || runningRef.current) return;
    runningRef.current = true;
    const url = healthUrl(getApiBaseUrl());
    const cycleStart = Date.now();

    try {
      while (!life.signal.aborted) {
        const attempt = new AbortController();
        const onLifeAbort = () => attempt.abort();
        life.signal.addEventListener("abort", onLifeAbort);
        const timer = setTimeout(() => attempt.abort(), HEALTH_TIMEOUT_MS);
        const started = performance.now();
        try {
          const res = await fetch(url, { signal: attempt.signal, cache: "no-store" });
          const latencyMs = performance.now() - started;
          let body: unknown = null;
          try {
            body = await res.json();
          } catch {
            body = null;
          }
          const result = interpretHealthResponse(res.ok, body);
          if (result.online) {
            lastCheckedRef.current = Date.now();
            setHealth({
              status: "online",
              waking: false,
              degraded: result.degraded,
              latencyMs,
              checkedAt: lastCheckedRef.current,
            });
            return;
          }
        } catch {
          // network error, CORS failure or timeout: fall through to retry logic
        } finally {
          clearTimeout(timer);
          life.signal.removeEventListener("abort", onLifeAbort);
        }

        if (life.signal.aborted) return;
        if (afterFailure(Date.now() - cycleStart) === "offline") {
          lastCheckedRef.current = Date.now();
          setHealth({
            status: "offline",
            waking: false,
            degraded: false,
            latencyMs: null,
            checkedAt: lastCheckedRef.current,
          });
          return;
        }
        setHealth((prev) => ({ ...prev, status: "checking", waking: true, latencyMs: null }));
        await sleep(WAKE_RETRY_DELAY_MS, life.signal);
      }
    } finally {
      runningRef.current = false;
    }
  }, []);

  useEffect(() => {
    const life = new AbortController();
    lifeRef.current = life;
    void runCycle();

    const tick = () => {
      if (shouldPoll(document.visibilityState, lastCheckedRef.current, Date.now())) {
        void runCycle();
      }
    };
    const interval = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);

    return () => {
      life.abort();
      lifeRef.current = null;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [runCycle]);

  const retry = useCallback(() => {
    if (runningRef.current) return;
    setHealth((prev) => ({ ...prev, status: "checking", waking: false, latencyMs: null }));
    void runCycle();
  }, [runCycle]);

  return { ...health, retry };
}
