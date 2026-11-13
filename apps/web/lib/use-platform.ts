"use client";

import { useSyncExternalStore } from "react";

import { detectPlatform, type ShortcutPlatform } from "@/lib/platform";

const noopSubscribe = () => () => {};

/**
 * Client platform for shortcut labels. The server snapshot is "unknown", and
 * React re-renders with the client value after hydration, so server and
 * client markup never disagree.
 */
export function useShortcutPlatform(): ShortcutPlatform {
  return useSyncExternalStore(
    noopSubscribe,
    () => detectPlatform(typeof navigator === "undefined" ? undefined : navigator),
    () => "unknown",
  );
}
