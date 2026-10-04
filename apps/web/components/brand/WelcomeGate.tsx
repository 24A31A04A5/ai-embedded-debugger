"use client";

import * as React from "react";
import { useAuth } from "@clerk/nextjs";

import { WelcomeAnimation } from "./WelcomeAnimation";
import {
  WELCOME_ATTR,
  WELCOME_ELAPSED_VAR,
  WELCOME_PENDING,
  WELCOME_PLAY_PREFIX,
  WELCOME_STORAGE_KEY,
  WELCOME_TOTAL_MS,
} from "./welcome-boot";

function getSessionStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function playStartedAt(value: string | null): number | null {
  if (!value?.startsWith(WELCOME_PLAY_PREFIX)) return null;
  const start = Number(value.slice(WELCOME_PLAY_PREFIX.length));
  return Number.isFinite(start) ? start : null;
}

function finishWelcome() {
  const root = document.documentElement;
  root.removeAttribute(WELCOME_ATTR);
  root.style.removeProperty(WELCOME_ELAPSED_VAR);
  try {
    getSessionStorage()?.removeItem(WELCOME_STORAGE_KEY);
  } catch {
    // Storage unavailable; nothing to clean up.
  }
}

export function WelcomeGate() {
  const { isLoaded, isSignedIn } = useAuth();
  const timerRef = React.useRef<number | null>(null);

  const scheduleFinish = React.useCallback((remainingMs: number) => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    // Fallback for when `animationend` never fires (e.g. backgrounded tab).
    timerRef.current = window.setTimeout(finishWelcome, Math.max(0, remainingMs) + 150);
  }, []);

  React.useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  // Pick up an animation the boot script started before hydration.
  React.useEffect(() => {
    if (!document.documentElement.hasAttribute(WELCOME_ATTR)) return;
    const start = playStartedAt(getSessionStorage()?.getItem(WELCOME_STORAGE_KEY) ?? null);
    scheduleFinish(start === null ? WELCOME_TOTAL_MS : WELCOME_TOTAL_MS - (Date.now() - start));
  }, [scheduleFinish]);

  React.useEffect(() => {
    if (!isLoaded) return;
    const storage = getSessionStorage();
    if (!storage) return;
    const root = document.documentElement;

    try {
      if (!isSignedIn) {
        if (root.hasAttribute(WELCOME_ATTR)) finishWelcome();
        storage.setItem(WELCOME_STORAGE_KEY, WELCOME_PENDING);
        return;
      }
      // Client-side sign-in (modal or in-app navigation): no reload, so the
      // boot script never ran. Start playing right away.
      if (storage.getItem(WELCOME_STORAGE_KEY) !== WELCOME_PENDING) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        storage.removeItem(WELCOME_STORAGE_KEY);
        return;
      }
      storage.setItem(WELCOME_STORAGE_KEY, `${WELCOME_PLAY_PREFIX}${Date.now()}`);
    } catch {
      return;
    }

    root.style.setProperty(WELCOME_ELAPSED_VAR, "0ms");
    root.setAttribute(WELCOME_ATTR, "play");
    scheduleFinish(WELCOME_TOTAL_MS);
  }, [isLoaded, isSignedIn, scheduleFinish]);

  return <WelcomeAnimation onExited={finishWelcome} />;
}
