/**
 * Platform-aware keyboard shortcut helpers (Phase 8B).
 * Pure functions, no imports, so they can be tested with `node --test`.
 */

export type ShortcutPlatform = "mac" | "other" | "unknown";

type NavigatorLike = {
  platform?: string;
  userAgent?: string;
  userAgentData?: { platform?: string } | null;
};

const APPLE_RE = /mac|iphone|ipad|ipod/i;

export function detectPlatform(nav: NavigatorLike | undefined | null): ShortcutPlatform {
  if (!nav) return "unknown";
  const hint = nav.userAgentData?.platform || nav.platform || nav.userAgent || "";
  if (!hint) return "unknown";
  return APPLE_RE.test(hint) ? "mac" : "other";
}

/** "⌘B" on macOS, "Ctrl+B" elsewhere (and before the platform is known). */
export function shortcutLabel(key: string, platform: ShortcutPlatform): string {
  const k = key.toUpperCase();
  return platform === "mac" ? `⌘${k}` : `Ctrl+${k}`;
}

type KeyEventLike = {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
};

/** True for ⌘<key> on macOS or Ctrl+<key> elsewhere, with no other modifiers. */
export function isShortcutEvent(e: KeyEventLike, key: string, platform: ShortcutPlatform): boolean {
  if (e.altKey || e.shiftKey) return false;
  if (e.key.toLowerCase() !== key.toLowerCase()) return false;
  if (platform === "mac") return e.metaKey && !e.ctrlKey;
  return e.ctrlKey && !e.metaKey;
}
