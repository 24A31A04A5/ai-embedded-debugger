import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";

import { AuthShell } from "@/components/auth/AuthShell";

export const metadata: Metadata = { title: "Sign in — AI Embedded Debugger" };

export default function SignInPage() {
  return (
    <AuthShell>
      <SignIn path="/sign-in" routing="path" signUpUrl="/sign-up" fallbackRedirectUrl="/workspace" />
    </AuthShell>
  );
}
