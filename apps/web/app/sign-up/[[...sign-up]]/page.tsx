import type { Metadata } from "next";
import { SignUp } from "@clerk/nextjs";

import { AuthShell } from "@/components/auth/AuthShell";

export const metadata: Metadata = { title: "Create account — AI Embedded Debugger" };

export default function SignUpPage() {
  return (
    <AuthShell>
      <SignUp path="/sign-up" routing="path" signInUrl="/sign-in" fallbackRedirectUrl="/workspace" />
    </AuthShell>
  );
}
