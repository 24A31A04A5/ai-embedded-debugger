import type { Metadata } from "next";
import { Geist, Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Embedded Debugger — AI-Powered Debugging for Embedded Developers",
  description:
    "Debug C/C++ firmware faster with AI-powered compiler error analysis, serial log diagnosis, and evidence-aware fixes. Built for embedded developers and students.",
  keywords: [
    "embedded debugging",
    "firmware debugger",
    "C/C++ debugging",
    "compiler error analysis",
    "serial log analysis",
    "AI debugging",
    "embedded development",
    "IoT debugging",
    "ESP32",
    "Arduino",
    "STM32",
  ],
  openGraph: {
    title: "AI Embedded Debugger",
    description:
      "AI-powered debugging for embedded developers. Analyze compiler errors, serial logs, and get evidence-aware diagnosis.",
    type: "website",
  },
};

import { ClerkProvider } from "@clerk/nextjs";
import { TooltipProvider } from "@/components/ui/tooltip";
import { WelcomeGate } from "@/components/brand/WelcomeGate";
import { welcomeBootScript } from "@/components/brand/welcome-boot";
import { clerkAppearance } from "@/lib/clerk-appearance";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider appearance={clerkAppearance} signInUrl="/sign-in" signUpUrl="/sign-up">
      <html lang="en" className="dark" suppressHydrationWarning>
        <body
          className={`${geistSans.variable} ${geistMono.variable} ${inter.variable} font-sans min-h-screen bg-background text-foreground antialiased selection:bg-[var(--accent-purple)]/30 selection:text-white relative`}
        >
          <script dangerouslySetInnerHTML={{ __html: welcomeBootScript }} />
          <WelcomeGate />

          {/* Ambient atmospheric glow in top background */}
          <div
            className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
            aria-hidden="true"
          >
            <div className="absolute -top-40 left-1/2 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle_at_center,oklch(0.62_0.16_158/0.12)_0%,oklch(0.96_0.01_155/0.04)_40%,transparent_70%)] blur-3xl" />
            <div className="absolute -top-20 -right-20 h-[350px] w-[350px] rounded-full bg-[radial-gradient(circle_at_center,oklch(0.9_0.02_155/0.06)_0%,transparent_70%)] blur-3xl" />
          </div>

          <TooltipProvider delayDuration={200}>
            <div className="relative z-10 flex min-h-screen flex-col">
              {children}
            </div>
          </TooltipProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
