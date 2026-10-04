/**
 * Liquid Glass theme for every Clerk surface (sign-in/up pages, the sign-in
 * modal, and the user menu). Visual only — no auth behaviour is configured here.
 */

const glassSurface = {
  background:
    "linear-gradient(180deg, rgba(255,255,255,0.075), rgba(255,255,255,0.015) 45%, rgba(255,255,255,0)), rgba(24,23,34,0.62)",
  backdropFilter: "blur(28px) saturate(170%)",
  WebkitBackdropFilter: "blur(28px) saturate(170%)",
  border: "0",
  boxShadow:
    "inset 0 0 0 1px rgba(255,255,255,0.09), inset 0 1px 0 rgba(255,255,255,0.13), 0 30px 70px -24px rgba(0,0,0,0.8), 0 2px 8px -2px rgba(0,0,0,0.4)",
  "@media (prefers-reduced-transparency: reduce)": {
    background: "rgb(28,27,38)",
    backdropFilter: "none",
    WebkitBackdropFilter: "none",
  },
};

const glassChip = {
  background: "rgba(255,255,255,0.05)",
  border: "0",
  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.09), inset 0 1px 0 rgba(255,255,255,0.08)",
  transition: "background-color 150ms ease, box-shadow 150ms ease",
  "&:hover": { background: "rgba(255,255,255,0.09)" },
};

const field = {
  background: "rgba(0,0,0,0.28)",
  border: "0",
  boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.1)",
  transition: "box-shadow 150ms ease",
  "&:hover": { boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.16)" },
  "&:focus, &:focus-visible": {
    boxShadow: "inset 0 0 0 1px rgba(52,211,153,0.8), 0 0 0 3px rgba(16,185,129,0.28)",
  },
};

const focusRing = {
  "&:focus-visible": {
    outline: "none",
    boxShadow: "0 0 0 2px rgba(16,24,20,1), 0 0 0 4px rgba(52,211,153,0.85)",
  },
};

export const clerkAppearance = {
  variables: {
    colorPrimary: "#10b981",
    colorPrimaryForeground: "#ffffff",
    colorBackground: "#17161f",
    colorForeground: "#f3f2f8",
    colorMutedForeground: "#a3a1b5",
    colorInput: "#121119",
    colorInputForeground: "#f3f2f8",
    colorNeutral: "#ffffff",
    colorDanger: "#f0616d",
    colorShadow: "#000000",
    borderRadius: "0.875rem",
    fontFamily: "var(--font-geist-sans), var(--font-inter), system-ui, sans-serif",
  },
  elements: {
    rootBox: { width: "100%", display: "flex", justifyContent: "center" },
    cardBox: { ...glassSurface, borderRadius: "26px", width: "25rem", maxWidth: "100%" },
    card: { background: "transparent", boxShadow: "none", border: "0", width: "100%" },
    footer: {
      background: "transparent",
      borderTop: "1px solid rgba(255,255,255,0.06)",
      "& > div": { background: "transparent" },
    },
    headerTitle: { fontWeight: 600, letterSpacing: "-0.015em" },
    headerSubtitle: { color: "#a3a1b5" },
    socialButtonsBlockButton: { ...glassChip, ...focusRing, borderRadius: "999px", minHeight: "44px" },
    socialButtonsIconButton: { ...glassChip, ...focusRing, borderRadius: "14px", minHeight: "44px" },
    dividerLine: { background: "rgba(255,255,255,0.1)" },
    dividerText: { color: "#8e8ca0" },
    formFieldLabel: { color: "#d6d4e2", fontWeight: 500 },
    formFieldInput: { ...field, borderRadius: "12px", minHeight: "44px" },
    otpCodeFieldInput: { ...field, borderRadius: "12px" },
    formButtonPrimary: {
      ...focusRing,
      background: "linear-gradient(180deg, #10b981 0%, #047857 100%)",
      border: "0",
      borderRadius: "999px",
      minHeight: "44px",
      fontWeight: 600,
      textTransform: "none",
      boxShadow:
        "inset 0 1px 0 rgba(255,255,255,0.45), inset 0 0 0 1px rgba(255,255,255,0.16), 0 10px 24px -10px rgba(16,185,129,0.75)",
      transition: "filter 150ms ease, transform 150ms ease",
      "&:hover": { filter: "brightness(1.08)" },
      "&:active": { transform: "scale(0.985)" },
      "&::after": { display: "none" },
    },
    footerActionLink: { color: "#6ee7b7", fontWeight: 500, "&:hover": { color: "#ffffff" } },
    formResendCodeLink: { color: "#6ee7b7" },
    identityPreview: { ...glassChip, borderRadius: "999px" },
    modalBackdrop: {
      background: "rgba(8,8,14,0.55)",
      backdropFilter: "blur(10px)",
      WebkitBackdropFilter: "blur(10px)",
    },
    modalContent: { borderRadius: "26px" },
    userButtonPopoverCard: { ...glassSurface, borderRadius: "20px" },
    userButtonPopoverMain: { background: "transparent" },
    userButtonPopoverFooter: { background: "transparent", borderTop: "1px solid rgba(255,255,255,0.06)" },
    userButtonPopoverActionButton: {
      borderRadius: "12px",
      "&:hover": { background: "rgba(255,255,255,0.06)" },
    },
  },
};
