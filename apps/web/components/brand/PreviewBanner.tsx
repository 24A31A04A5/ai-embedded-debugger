"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api-client";

type Diagnostics = {
  environment: string;
  git_sha?: string;
  database_fingerprint?: string;
  storage_backend: string;
};

type HealthState =
  | { kind: "checking" }
  | { kind: "ok"; status: string; diagnostics?: Diagnostics }
  | { kind: "offline" };

/**
 * Shown only on builds with NEXT_PUBLIC_APP_ENV=preview (set as a Vercel Preview
 * variable for the preview branch). Production builds never render it.
 * Shows the API origin (public) and the API's non-secret /health diagnostics.
 */
export function PreviewBanner() {
  if (process.env.NEXT_PUBLIC_APP_ENV !== "preview") return null;
  return <PreviewBannerInner />;
}

function PreviewBannerInner() {
  const [health, setHealth] = useState<HealthState>({ kind: "checking" });
  const apiBase = getApiBaseUrl();
  let apiHost = apiBase;
  try {
    apiHost = new URL(apiBase).host;
  } catch {
    // keep raw value
  }

  useEffect(() => {
    const controller = new AbortController();
    // Render free instances can take ~60 s to wake up.
    const timer = setTimeout(() => controller.abort(), 75_000);
    fetch(`${apiBase}/health`, { signal: controller.signal, cache: "no-store" })
      .then((r) => r.json())
      .then((body) => setHealth({ kind: "ok", status: body.status, diagnostics: body.diagnostics }))
      .catch(() => setHealth({ kind: "offline" }))
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [apiBase]);

  const d = health.kind === "ok" ? health.diagnostics : undefined;
  const parts = [
    `API ${apiHost}`,
    health.kind === "checking" ? "checking…" : health.kind === "offline" ? "API offline" : `API ${health.status}`,
    d ? `env ${d.environment}` : null,
    d?.database_fingerprint ? `db #${d.database_fingerprint}` : null,
    d ? `storage ${d.storage_backend}` : null,
    d?.git_sha ? `build ${d.git_sha}` : null,
  ].filter(Boolean);

  return (
    <div
      role="status"
      data-testid="preview-banner"
      className="fixed bottom-0 inset-x-0 z-50 border-t border-amber-500/40 bg-amber-500/15 px-3 py-1 text-center font-mono text-[11px] text-amber-200 backdrop-blur"
    >
      PREVIEW ENVIRONMENT · test data only · {parts.join(" · ")}
    </div>
  );
}
