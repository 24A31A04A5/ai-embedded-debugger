import * as React from "react";
import Image from "next/image";

export const BRAND_LOGO_SRC = "/brand/ai-embedded-debugger-logo.png";

interface WelcomeAnimationProps {
  onExited?: () => void;
}

/**
 * Hidden by default; shown and animated while `<html data-welcome="play">`
 * is set (see globals.css and welcome-boot.ts).
 */
export function WelcomeAnimation({ onExited }: WelcomeAnimationProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="welcome-overlay fixed inset-0 z-[100] items-center justify-center overflow-hidden bg-[#0b0d0c] px-6"
      onAnimationEnd={(event) => {
        if (event.target === event.currentTarget && event.animationName === "welcome-exit") {
          onExited?.();
        }
      }}
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_42%,rgba(16,185,129,0.12)_0%,rgba(16,185,129,0.04)_35%,transparent_65%)]"
      />

      <div className="welcome-stage relative flex w-full max-w-sm flex-col items-center text-center">
        <div className="relative flex items-center justify-center">
          <div
            aria-hidden="true"
            className="welcome-glow pointer-events-none absolute left-1/2 top-1/2 h-[min(18rem,72vw)] w-[min(18rem,72vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(52,211,153,0.22)_0%,rgba(16,185,129,0.08)_40%,transparent_70%)]"
          />
          <Image
            src={BRAND_LOGO_SRC}
            alt=""
            width={1536}
            height={1024}
            loading="eager"
            sizes="(max-width: 640px) 60vw, 240px"
            className="welcome-logo relative h-auto w-[min(15rem,60vw)] object-contain"
          />
        </div>

        <div className="mt-5">
          <p className="welcome-title text-2xl font-semibold tracking-[0.14em] text-white sm:text-3xl">
            <span className="text-[#34D399]">AI</span> EMBEDDED
          </p>
          <p className="welcome-subtitle mt-1.5 pl-[0.55em] text-xs font-medium tracking-[0.55em] text-white/75 sm:text-sm">
            DEBUGGER
          </p>
          <div
            aria-hidden="true"
            className="welcome-subtitle mx-auto mt-4 h-px w-14 bg-gradient-to-r from-transparent via-[#10B981] to-transparent"
          />
        </div>

        <p className="welcome-status mt-5 text-[11px] tracking-wide text-white/45 sm:text-xs">
          Initializing workspace…
        </p>
      </div>
    </div>
  );
}
