import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} font-sans`}
      >
        {children}
      </body>
    </html>
  );
}
