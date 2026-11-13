// Run with: pnpm --filter web test  (node --test, Node >= 22.18 strips TS types)
import { test } from "node:test";
import assert from "node:assert/strict";

import { detectPlatform, isShortcutEvent, shortcutLabel } from "../platform.ts";

test("detectPlatform recognises Apple platforms", () => {
  assert.equal(detectPlatform({ platform: "MacIntel" }), "mac");
  assert.equal(detectPlatform({ userAgentData: { platform: "macOS" } }), "mac");
  assert.equal(detectPlatform({ platform: "iPad" }), "mac");
  assert.equal(detectPlatform({ platform: "Win32" }), "other");
  assert.equal(detectPlatform({ userAgentData: { platform: "Windows" } }), "other");
  assert.equal(detectPlatform({ platform: "Linux x86_64" }), "other");
  assert.equal(detectPlatform({ platform: "", userAgent: "" }), "unknown");
  assert.equal(detectPlatform(undefined), "unknown");
});

test("shortcutLabel: ⌘B on macOS, Ctrl+B elsewhere", () => {
  assert.equal(shortcutLabel("b", "mac"), "⌘B");
  assert.equal(shortcutLabel("b", "other"), "Ctrl+B");
  assert.equal(shortcutLabel("b", "unknown"), "Ctrl+B");
});

const ev = (over) => ({ key: "b", metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...over });

test("isShortcutEvent matches the platform modifier only", () => {
  assert.equal(isShortcutEvent(ev({ metaKey: true }), "b", "mac"), true);
  assert.equal(isShortcutEvent(ev({ ctrlKey: true }), "b", "mac"), false);
  assert.equal(isShortcutEvent(ev({ ctrlKey: true }), "b", "other"), true);
  assert.equal(isShortcutEvent(ev({ ctrlKey: true, key: "B" }), "b", "other"), true);
  assert.equal(isShortcutEvent(ev({ metaKey: true }), "b", "other"), false);
  assert.equal(isShortcutEvent(ev({ ctrlKey: true, shiftKey: true }), "b", "other"), false);
  assert.equal(isShortcutEvent(ev({ ctrlKey: true, key: "k" }), "b", "other"), false);
});
