// Run with: pnpm --filter web test  (node --test, Node >= 22.18 strips TS types)
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  afterFailure,
  formatLatency,
  healthUrl,
  interpretHealthResponse,
  shouldPoll,
  WAKE_WINDOW_MS,
  POLL_INTERVAL_MS,
  HEALTH_TIMEOUT_MS,
} from "../health-status.ts";

test("healthUrl targets the API root /health", () => {
  assert.equal(healthUrl("https://api.example.com/v1"), "https://api.example.com/health");
  assert.equal(healthUrl("https://api.example.com/v1/"), "https://api.example.com/health");
  assert.equal(healthUrl("https://api.example.com"), "https://api.example.com/health");
  assert.equal(healthUrl("http://localhost:8000/v1"), "http://localhost:8000/health");
});

test("interpretHealthResponse maps /health bodies", () => {
  assert.deepEqual(interpretHealthResponse(true, { status: "ok" }), { online: true, degraded: false });
  assert.deepEqual(interpretHealthResponse(true, { status: "degraded" }), { online: true, degraded: true });
  assert.deepEqual(interpretHealthResponse(true, null), { online: true, degraded: true });
  assert.deepEqual(interpretHealthResponse(false, { status: "ok" }), { online: false, degraded: false });
});

test("failures inside the wake window keep checking, then go offline", () => {
  assert.equal(afterFailure(0), "retry");
  assert.equal(afterFailure(HEALTH_TIMEOUT_MS), "retry");
  assert.equal(afterFailure(50_000), "retry");
  assert.equal(afterFailure(WAKE_WINDOW_MS), "offline");
  assert.equal(afterFailure(90_000), "offline");
  assert.ok(WAKE_WINDOW_MS >= 50_000, "wake window must cover a ~50 s Render cold start");
});

test("polling only while visible and at most once per interval", () => {
  assert.equal(shouldPoll("hidden", null, 0), false);
  assert.equal(shouldPoll("visible", null, 0), true);
  assert.equal(shouldPoll("visible", 1_000, 1_000 + POLL_INTERVAL_MS - 1), false);
  assert.equal(shouldPoll("visible", 1_000, 1_000 + POLL_INTERVAL_MS), true);
  assert.equal(shouldPoll("hidden", 0, 10 * POLL_INTERVAL_MS), false);
  assert.ok(POLL_INTERVAL_MS >= 60_000);
});

test("formatLatency shows only measured values", () => {
  assert.equal(formatLatency(null), null);
  assert.equal(formatLatency(undefined), null);
  assert.equal(formatLatency(Number.NaN), null);
  assert.equal(formatLatency(-5), null);
  assert.equal(formatLatency(182.4), "182 ms");
  assert.equal(formatLatency(41_250), "41.3 s");
});
