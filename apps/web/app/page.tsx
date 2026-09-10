"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Bug,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  ExternalLink,
  FileCode,
  FileTerminal,
  FileText,
  FolderOpen,
  Layers,
  Menu,
  Plus,
  ShieldCheck,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Show, SignInButton, UserButton, useAuth, useUser } from "@clerk/nextjs";
import {
  useApiClient,
  getApiBaseUrl,
  type ProjectFileMetadata,
  type DebugSessionSummary,
  type DocumentMetadata,
} from "@/lib/api-client";

type Project = {
  id: string;
  name: string;
  description?: string;
  created_at?: string;
};

/* ────────────────────────────────────────────────────────────
   Helper: Format Relative Time
   ──────────────────────────────────────────────────────────── */

function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return "recently";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHours = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString();
  } catch {
    return dateStr;
  }
}

function formatBytes(bytes?: number): string {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ────────────────────────────────────────────────────────────
   Navbar
   ──────────────────────────────────────────────────────────── */

function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-[oklch(0.13_0.015_260/0.85)] backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand / Logo */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 group" aria-label="AI Embedded Debugger Home">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-indigo)] shadow-sm shadow-[var(--accent-purple)]/25 border border-purple-400/30 transition-transform duration-200 group-hover:scale-105">
            <Bug className="h-4 w-4 text-white" />
          </div>
          <span className="font-semibold tracking-tight text-foreground flex items-center gap-1.5">
            <span className="rounded bg-[var(--accent-purple)]/20 px-1.5 py-0.5 text-[10px] font-bold text-purple-200 border border-[var(--accent-purple)]/30 tracking-wide">
              AI
            </span>
            <span className="text-[14px] sm:text-[15px] text-foreground/95">
              Embedded Debugger
            </span>
          </span>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main navigation">
          <a
            href="#bento-dashboard"
            className="rounded-md px-3 py-1.5 text-xs sm:text-sm font-medium text-foreground bg-white/5 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
          >
            Dashboard
          </a>
          <a
            href="#problem"
            className="rounded-md px-3 py-1.5 text-xs sm:text-sm font-medium text-muted-foreground transition-all hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
          >
            Capabilities
          </a>
          <a
            href="#how-it-works"
            className="rounded-md px-3 py-1.5 text-xs sm:text-sm font-medium text-muted-foreground transition-all hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
          >
            Architecture
          </a>
          <a
            href="#demo"
            className="rounded-md px-3 py-1.5 text-xs sm:text-sm font-medium text-muted-foreground transition-all hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
          >
            Diagnostic Demo
          </a>
        </nav>

        {/* Action Controls */}
        <div className="flex items-center gap-2 sm:gap-3">
          <Show when="signed-out">
            <SignInButton mode="modal">
              <Button variant="ghost" size="sm" className="hidden text-xs sm:text-sm sm:inline-flex text-muted-foreground hover:text-foreground">
                Sign In
              </Button>
            </SignInButton>
            <SignInButton mode="modal">
              <Button variant="ai" size="sm" className="hidden text-xs sm:text-sm sm:inline-flex shadow-sm">
                Get Started
              </Button>
            </SignInButton>
          </Show>
          <Show when="signed-in">
            <Button variant="ai" size="sm" className="hidden text-xs sm:text-sm sm:inline-flex shadow-sm" asChild>
              <Link href="/workspace">Open Workspace</Link>
            </Button>
            <UserButton />
          </Show>

          {/* Mobile Sheet Navigation */}
          <div className="md:hidden">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 border-border/60 text-muted-foreground hover:text-foreground"
                  aria-label="Open navigation menu"
                >
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[280px] sm:w-[320px] bg-[oklch(0.13_0.015_260/0.95)] backdrop-blur-2xl border-border/60 p-6 flex flex-col justify-between">
                <div>
                  <SheetHeader className="text-left pb-4 border-b border-border/40">
                    <SheetTitle className="flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-indigo)]">
                        <Bug className="h-3.5 w-3.5 text-white" />
                      </div>
                      <span className="text-sm font-semibold text-foreground">
                        AI Embedded Debugger
                      </span>
                    </SheetTitle>
                  </SheetHeader>
                  <nav className="flex flex-col gap-2 pt-4" aria-label="Mobile navigation">
                    <a
                      href="#bento-dashboard"
                      className="rounded-lg px-3 py-2.5 text-sm font-medium text-foreground bg-white/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Dashboard
                    </a>
                    <a
                      href="#problem"
                      className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Capabilities
                    </a>
                    <a
                      href="#how-it-works"
                      className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Architecture
                    </a>
                    <a
                      href="#demo"
                      className="rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/60"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      Diagnostic Demo
                    </a>
                  </nav>
                </div>

                <div className="flex flex-col gap-2.5 pt-4 border-t border-border/40">
                  <Show when="signed-out">
                    <SignInButton mode="modal">
                      <Button variant="outline" size="sm" className="w-full justify-center text-sm">
                        Sign In
                      </Button>
                    </SignInButton>
                    <SignInButton mode="modal">
                      <Button variant="ai" size="sm" className="w-full justify-center text-sm">
                        Get Started
                      </Button>
                    </SignInButton>
                  </Show>
                  <Show when="signed-in">
                    <Button variant="ai" size="sm" className="w-full justify-center text-sm" asChild>
                      <Link href="/workspace" onClick={() => setMobileMenuOpen(false)}>
                        Open Workspace
                      </Link>
                    </Button>
                  </Show>
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </div>
    </header>
  );
}

/* ────────────────────────────────────────────────────────────
   Create Project Dialog
   ──────────────────────────────────────────────────────────── */

function CreateProjectDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (name: string, description?: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      await onCreate(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Debugging Project</DialogTitle>
          <DialogDescription>
            Organize firmware code, reference datasheets, and error diagnosis sessions.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1.5">
            <label htmlFor="bento-proj-name" className="text-xs font-medium text-foreground">
              Project Name
            </label>
            <Input
              id="bento-proj-name"
              placeholder="e.g., ESP32-S3 Motor Controller"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="bento-proj-desc" className="text-xs font-medium text-foreground">
              Description (Optional)
            </label>
            <Input
              id="bento-proj-desc"
              placeholder="e.g., FreeRTOS firmware debugging with CAN bus"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" variant="ai" disabled={submitting || !name.trim()}>
              {submitting ? "Creating..." : "Create Project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ────────────────────────────────────────────────────────────
   Bento Grid Dashboard Section
   ──────────────────────────────────────────────────────────── */

function BentoDashboard() {
  const { isSignedIn } = useAuth();
  const { user } = useUser();
  const api = useApiClient();

  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<DebugSessionSummary[]>([]);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [files, setFiles] = useState<ProjectFileMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiHealth, setApiHealth] = useState<"checking" | "healthy" | "offline">("checking");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  // 1. Live Health Check
  useEffect(() => {
    let isMounted = true;
    async function checkHealth() {
      try {
        const baseUrl = getApiBaseUrl().replace(/\/v1\/?$/, "");
        const res = await fetch(`${baseUrl}/health`, {
          signal: AbortSignal.timeout(3000),
        });
        if (!isMounted) return;
        if (res.ok) {
          setApiHealth("healthy");
        } else {
          setApiHealth("offline");
        }
      } catch {
        if (isMounted) setApiHealth("offline");
      }
    }
    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch Projects when signed in
  useEffect(() => {
    if (!isSignedIn) {
      setLoading(false);
      return;
    }
    let isMounted = true;
    async function loadProjects() {
      setLoading(true);
      try {
        const projs = await api.getProjects();
        if (!isMounted) return;
        setProjects(projs);
        if (projs.length > 0) {
          setActiveProjectId((prev) => prev || projs[0].id);
        }
      } catch (e) {
        console.error("Failed to load projects", e);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadProjects();
    return () => {
      isMounted = false;
    };
  }, [isSignedIn, api]);

  // 3. Fetch Project Details when active project changes
  useEffect(() => {
    if (!activeProjectId || !isSignedIn) {
      setSessions([]);
      setDocuments([]);
      setFiles([]);
      return;
    }
    const projectId = activeProjectId;
    let isMounted = true;
    async function loadDetails() {
      try {
        const [sessList, docList, fileList] = await Promise.allSettled([
          api.listSessions(projectId),
          api.listDocuments(projectId),
          api.listFiles(projectId),
        ]);
        if (!isMounted) return;
        if (sessList.status === "fulfilled") setSessions(sessList.value);
        if (docList.status === "fulfilled") setDocuments(docList.value);
        if (fileList.status === "fulfilled") setFiles(fileList.value);
      } catch (e) {
        console.error("Failed to load project details", e);
      }
    }
    loadDetails();
    return () => {
      isMounted = false;
    };
  }, [activeProjectId, isSignedIn, api]);

  const handleCreateProject = async (name: string, description?: string) => {
    try {
      const newProj = await api.createProject(name, description);
      setProjects((prev) => [newProj, ...prev]);
      setActiveProjectId(newProj.id);
    } catch (e) {
      console.error("Failed to create project", e);
    }
  };

  const activeProject = projects.find((p) => p.id === activeProjectId);

  return (
    <section id="bento-dashboard" className="pt-20 pb-16 px-4 sm:px-6 max-w-7xl mx-auto">
      {/* Platform Control Strip */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-4 border-b border-border/40">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="ai" className="text-[10px] tracking-wider uppercase font-semibold">
              <Sparkles className="h-3 w-3 mr-1" />
              Control Center
            </Badge>
            <span className="text-xs text-muted-foreground font-mono">
              v1.0.0-prod
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground font-display">
            {isSignedIn && user?.firstName ? (
              <>Welcome back, <span className="gradient-text-accent">{user.firstName}</span></>
            ) : (
              <>AI Embedded <span className="gradient-text-accent">Diagnostic Platform</span></>
            )}
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Real-time firmware diagnostic engine, RAG datasheet grounding, and session management.
          </p>
        </div>

        {/* Project Selector & Actions */}
        <div className="flex items-center flex-wrap gap-2.5">
          {isSignedIn && projects.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 gap-2 px-3 text-xs font-medium border-border/60 bg-card/60 hover:bg-white/5"
                >
                  <FolderOpen className="h-3.5 w-3.5 text-[var(--accent-purple)] shrink-0" />
                  <span className="max-w-[140px] truncate">{activeProject ? activeProject.name : "Select Project"}</span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 bg-[oklch(0.16_0.015_260/0.95)] backdrop-blur-xl border-border/80">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  Active Projects
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {projects.map((p) => (
                  <DropdownMenuItem
                    key={p.id}
                    onClick={() => setActiveProjectId(p.id)}
                    className={`flex items-center justify-between text-xs cursor-pointer ${
                      p.id === activeProjectId ? "text-[var(--accent-purple)] font-medium bg-[var(--accent-purple)]/10" : ""
                    }`}
                  >
                    <span className="truncate">{p.name}</span>
                    {p.id === activeProjectId && (
                      <div className="h-1.5 w-1.5 rounded-full bg-[var(--accent-purple)] shadow-[0_0_6px_var(--accent-purple)] shrink-0" />
                    )}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => setCreateDialogOpen(true)}
                  className="flex items-center gap-2 text-xs text-[var(--accent-purple)] cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>New Project</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {isSignedIn && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateDialogOpen(true)}
              className="h-8 gap-1.5 text-xs border-border/60 hover:bg-white/5"
            >
              <Plus className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
              <span>New Project</span>
            </Button>
          )}

          <Button variant="ai" size="sm" asChild className="h-8 shadow-sm">
            <Link href="/workspace">
              <span>Open Workspace</span>
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      </div>

      {/* ────────────────────────────────────────────────────────────
         12-Column Asymmetric Bento Grid
         ──────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 sm:gap-6 items-stretch">

        {/* ── CARD 1: PRIMARY "NEW DEBUG SESSION" HERO CARD (Col 8) ── */}
        <Card variant="ai" className="md:col-span-12 lg:col-span-8 flex flex-col justify-between overflow-hidden relative group interactive-card">
          <div className="absolute -right-20 -top-20 w-60 h-60 bg-[var(--accent-purple)]/10 rounded-full blur-3xl pointer-events-none transition-opacity duration-300 group-hover:opacity-100 opacity-60" />

          <CardHeader className="pb-3 relative z-10">
            <div className="flex items-center justify-between gap-2 mb-2">
              <Badge variant="ai" className="gap-1.5">
                <Sparkles className="h-3 w-3 transition-transform duration-200 group-hover:rotate-12 motion-reduce:group-hover:rotate-0" />
                <span>Autonomous Diagnostic Engine</span>
              </Badge>
              <span className="text-[11px] font-mono text-muted-foreground hidden sm:inline">
                ESP32 • STM32 • Arduino • FreeRTOS
              </span>
            </div>
            <CardTitle className="text-xl sm:text-2xl font-bold font-display text-foreground leading-tight">
              Start Evidence-Aware Firmware Diagnosis
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm leading-relaxed text-muted-foreground max-w-2xl">
              Paste compiler errors, stream serial panic logs, or inspect register lockups. The AI engine cross-references your uploaded hardware datasheets to isolate root causes and produce exact C/C++ patch diffs.
            </CardDescription>
          </CardHeader>

          {/* Diagnostic Code Snippet Preview */}
          <CardContent className="pb-4 relative z-10">
            <div className="rounded-lg border border-[var(--color-code-border)] bg-[var(--color-code-bg)] p-3 font-mono text-xs overflow-hidden shadow-inner group-hover:border-[var(--accent-purple)]/40 transition-colors">
              <div className="flex items-center justify-between border-b border-[var(--color-code-border)]/60 pb-2 mb-2 text-muted-foreground text-[11px]">
                <div className="flex items-center gap-1.5">
                  <Terminal className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
                  <span>main.c — assertion failed (GPIO_SEL_2 undeclared)</span>
                </div>
                <Badge variant="error" className="text-[10px] py-0 px-1.5">
                  Syntax Error
                </Badge>
              </div>
              <div className="space-y-1 text-muted-foreground/90 font-mono text-[11px] leading-5">
                <p className="text-[var(--color-error-red)] line-through opacity-70">
                  - .pin_bit_mask = GPIO_SEL_2; // Unknown identifier
                </p>
                <p className="text-[var(--color-success-green)] font-semibold">
                  + .pin_bit_mask = (1ULL &lt;&lt; 2); // Correct bitmask macro
                </p>
              </div>
            </div>
          </CardContent>

          <CardFooter className="pt-2 flex flex-wrap items-center justify-between gap-3 relative z-10 border-t border-border/40">
            <div className="flex items-center gap-2">
              <Button variant="ai-glow" size="sm" asChild className="hover:scale-[1.02] active:scale-[0.98] transition-transform">
                <Link href="/workspace">
                  <span>Start Debugging</span>
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5 transition-transform duration-150 group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0" />
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild className="hidden sm:inline-flex hover:bg-white/5 active:scale-[0.98]">
                <Link href="/workspace">Open Full IDE</Link>
              </Button>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
                Zero Hallucinations Guarantee
              </span>
            </div>
          </CardFooter>
        </Card>

        {/* ── CARD 6: SYSTEM / AI ENGINE STATUS (Col 4) ── */}
        <Card variant="glass" className="md:col-span-6 lg:col-span-4 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Cpu className="h-4 w-4 text-[var(--accent-purple)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
                System & AI Engine Status
              </CardTitle>
              <div className="flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${
                  apiHealth === "healthy" ? "bg-[var(--color-success-green)] shadow-[0_0_8px_var(--color-success-green)]" :
                  apiHealth === "checking" ? "bg-[var(--color-warning-amber)]" : "bg-[var(--color-error-red)]"
                }`} aria-hidden="true" />
                <span className="text-[10px] text-muted-foreground font-mono uppercase">
                  {apiHealth}
                </span>
              </div>
            </div>
            <CardDescription className="text-xs">
              Live service status and embedded reasoning telemetry.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border/40 hover:border-border/70 transition-colors">
              <span className="text-muted-foreground">API Gateway</span>
              <Badge variant={apiHealth === "healthy" ? "success" : "outline"} className="text-[10px]">
                {apiHealth === "healthy" ? "Online (v1)" : apiHealth === "checking" ? "Verifying" : "Unreachable"}
              </Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border/40 hover:border-border/70 transition-colors">
              <span className="text-muted-foreground">AI Diagnostic Model</span>
              <Badge variant="ai" className="text-[10px]">
                Gemini 2.5 Flash
              </Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border/40 hover:border-border/70 transition-colors">
              <span className="text-muted-foreground">RAG Vector Index</span>
              <Badge variant="outline" className="text-[10px] border-[var(--accent-purple)]/40 text-purple-300">
                ChromaDB Active
              </Badge>
            </div>

            <div className="flex items-center justify-between p-2 rounded-lg bg-card/60 border border-border/40 hover:border-border/70 transition-colors">
              <span className="text-muted-foreground">Code Sanitizer</span>
              <Badge variant="outline" className="text-[10px] text-[var(--color-success-green)] border-[var(--color-success-green)]/30">
                Enforced
              </Badge>
            </div>
          </CardContent>

          <CardFooter className="pt-2 text-[11px] text-muted-foreground/80 border-t border-border/30">
            Target support: ESP-IDF, STM32 HAL, FreeRTOS, Arduino
          </CardFooter>
        </Card>

        {/* ── CARD 3: PROJECTS (Col 4) ── */}
        <Card variant="default" className="md:col-span-6 lg:col-span-4 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <FolderOpen className="h-4 w-4 text-[var(--accent-purple)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
                Projects Workspace
              </CardTitle>
              {isSignedIn && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 text-muted-foreground hover:text-foreground active:scale-95"
                  onClick={() => setCreateDialogOpen(true)}
                  aria-label="Create project"
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
            <CardDescription className="text-xs">
              {isSignedIn ? `${projects.length} project${projects.length === 1 ? "" : "s"} configured` : "Sign in to manage projects"}
            </CardDescription>
          </CardHeader>

          <CardContent className="flex-1 space-y-2 text-xs overflow-y-auto max-h-56">
            {!isSignedIn ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <FolderOpen className="h-6 w-6 mx-auto mb-2 text-muted-foreground/60" />
                <p className="text-muted-foreground font-medium">Sign in to access projects</p>
                <p className="text-[11px] text-muted-foreground/70 mt-1 mb-3">Group firmware repositories and datasheets</p>
                <SignInButton mode="modal">
                  <Button variant="outline" size="sm" className="text-xs">Sign In</Button>
                </SignInButton>
              </div>
            ) : loading ? (
              <div className="space-y-2">
                <Skeleton className="h-9 w-full" />
                <Skeleton className="h-9 w-full" />
              </div>
            ) : projects.length === 0 ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <p className="text-muted-foreground">No projects yet.</p>
                <Button
                  variant="ai"
                  size="sm"
                  className="mt-2 text-xs"
                  onClick={() => setCreateDialogOpen(true)}
                >
                  Create First Project
                </Button>
              </div>
            ) : (
              projects.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setActiveProjectId(p.id)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-lg border transition-all text-left cursor-pointer active:scale-[0.99] ${
                    p.id === activeProjectId
                      ? "bg-[var(--accent-purple)]/10 border-[var(--accent-purple)]/50 text-foreground shadow-xs"
                      : "bg-card/40 border-border/40 text-muted-foreground hover:bg-white/5 hover:text-foreground hover:border-border/80"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FolderOpen className={`h-3.5 w-3.5 shrink-0 transition-colors ${p.id === activeProjectId ? "text-[var(--accent-purple)]" : ""}`} />
                    <span className="truncate font-medium">{p.name}</span>
                  </div>
                  {p.id === activeProjectId && (
                    <div className="h-1.5 w-1.5 rounded-full bg-[var(--accent-purple)] shadow-[0_0_6px_var(--accent-purple)] shrink-0" />
                  )}
                </button>
              ))
            )}
          </CardContent>

          <CardFooter className="pt-2 border-t border-border/30 flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{activeProject ? activeProject.name : "None selected"}</span>
            <Link href="/workspace" className="text-[var(--accent-purple)] hover:underline flex items-center gap-1 group">
              <span>IDE Files</span>
              <ChevronRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform motion-reduce:group-hover:translate-x-0" />
            </Link>
          </CardFooter>
        </Card>

        {/* ── CARD 2: RECENT DEBUG SESSIONS (Col 5) ── */}
        <Card variant="default" className="md:col-span-6 lg:col-span-5 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Terminal className="h-4 w-4 text-[var(--color-emerald)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
                Recent Debug Sessions
              </CardTitle>
              <Badge variant="outline" className="text-[10px]">
                {sessions.length} recorded
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Previous compiler & serial log analyses.
            </CardDescription>
          </CardHeader>

          <CardContent className="flex-1 space-y-2 text-xs overflow-y-auto max-h-56">
            {!isSignedIn ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <Terminal className="h-6 w-6 mx-auto mb-2 text-muted-foreground/60" />
                <p className="text-muted-foreground font-medium">Session history protected</p>
                <p className="text-[11px] text-muted-foreground/70 mt-1 mb-3">Sign in to view evidence-backed diagnosis sessions</p>
                <SignInButton mode="modal">
                  <Button variant="outline" size="sm" className="text-xs">Sign In</Button>
                </SignInButton>
              </div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <p className="text-muted-foreground">No sessions for this project yet.</p>
                <p className="text-[11px] text-muted-foreground/70 mt-0.5 mb-2">Paste compiler errors in the workspace to record diagnostics.</p>
                <Button variant="ai-outline" size="sm" asChild className="text-xs">
                  <Link href="/workspace">Start Session</Link>
                </Button>
              </div>
            ) : (
              sessions.slice(0, 4).map((s) => (
                <Link
                  key={s.id}
                  href="/workspace"
                  className="flex items-center justify-between p-2.5 rounded-lg bg-card/40 border border-border/40 hover:border-[var(--accent-purple)]/40 hover:bg-white/5 transition-all text-left group active:scale-[0.99]"
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <p className="font-medium text-foreground/90 truncate group-hover:text-[var(--accent-purple)] transition-colors">
                      {s.title || "Untitled Session"}
                    </p>
                    <div className="flex items-center gap-2 mt-0.5 text-[10px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>{formatRelativeTime(s.updated_at || s.created_at)}</span>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-[10px] shrink-0 border-border/60">
                    Diagnosed
                  </Badge>
                </Link>
              ))
            )}
          </CardContent>

          <CardFooter className="pt-2 border-t border-border/30 flex items-center justify-between text-[11px] text-muted-foreground">
            <span>Synchronized with cloud</span>
            <Link href="/workspace" className="text-[var(--accent-purple)] hover:underline flex items-center gap-1 group">
              <span>Open in Workspace</span>
              <ChevronRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform motion-reduce:group-hover:translate-x-0" />
            </Link>
          </CardFooter>
        </Card>

        {/* ── CARD 7: QUICK ACTIONS (Col 3) ── */}
        <Card variant="glassCard" className="md:col-span-6 lg:col-span-3 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Zap className="h-4 w-4 text-[var(--accent-purple)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
              Quick Actions
            </CardTitle>
            <CardDescription className="text-xs">
              Frequently accessed developer tasks.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-2 text-xs">
            <Button
              variant="outline"
              size="sm"
              asChild
              className="w-full justify-start gap-2 h-9 text-xs border-border/60 hover:border-[var(--accent-purple)]/50 hover:bg-[var(--accent-purple)]/10 active:scale-[0.99] transition-all"
            >
              <Link href="/workspace">
                <Zap className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
                <span>New Debug Session</span>
              </Link>
            </Button>

            <Button
              variant="outline"
              size="sm"
              asChild
              className="w-full justify-start gap-2 h-9 text-xs border-border/60 hover:border-[var(--color-emerald)]/50 hover:bg-[var(--color-emerald)]/10 active:scale-[0.99] transition-all"
            >
              <Link href="/workspace">
                <FileCode className="h-3.5 w-3.5 text-[var(--color-emerald)]" />
                <span>Upload Firmware (.c, .ino)</span>
              </Link>
            </Button>

            <Button
              variant="outline"
              size="sm"
              asChild
              className="w-full justify-start gap-2 h-9 text-xs border-border/60 hover:border-[var(--color-info-blue)]/50 hover:bg-[var(--color-info-blue)]/10 active:scale-[0.99] transition-all"
            >
              <Link href="/workspace">
                <FileText className="h-3.5 w-3.5 text-[var(--color-info-blue)]" />
                <span>Upload Datasheet (.pdf)</span>
              </Link>
            </Button>

            <Button
              variant="outline"
              size="sm"
              asChild
              className="w-full justify-start gap-2 h-9 text-xs border-border/60 hover:bg-white/5 active:scale-[0.99] transition-all"
            >
              <Link href="/workspace">
                <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                <span>Open IDE Workspace</span>
              </Link>
            </Button>
          </CardContent>

          <CardFooter className="pt-2 border-t border-border/30 text-[10px] text-muted-foreground">
            Fast keyboard shortcut: <kbd className="px-1 py-0.5 bg-muted rounded text-[9px] font-mono ml-1">⌘B</kbd>
          </CardFooter>
        </Card>

        {/* ── CARD 5: DEBUG ACTIVITY & TELEMETRY (Col 7) ── */}
        <Card variant="default" className="md:col-span-12 lg:col-span-7 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Layers className="h-4 w-4 text-[var(--accent-purple)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
                Project Activity & Evidence Telemetry
              </CardTitle>
              <Badge variant="outline" className="text-[10px]">
                {activeProject ? activeProject.name : "All Projects"}
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Real repository metrics and evidence documents loaded in current scope.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 text-xs">
            {/* Real Stats Grid */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-card/60 border border-border/40 text-center">
                <span className="text-[10px] uppercase font-semibold text-muted-foreground">Sessions</span>
                <p className="text-xl sm:text-2xl font-bold font-display text-foreground mt-0.5">
                  {sessions.length}
                </p>
                <span className="text-[10px] text-muted-foreground/80">Diagnostic runs</span>
              </div>

              <div className="p-3 rounded-lg bg-card/60 border border-border/40 text-center">
                <span className="text-[10px] uppercase font-semibold text-muted-foreground">Firmware Files</span>
                <p className="text-xl sm:text-2xl font-bold font-display text-foreground mt-0.5">
                  {files.length}
                </p>
                <span className="text-[10px] text-muted-foreground/80">Code & logs indexed</span>
              </div>

              <div className="p-3 rounded-lg bg-card/60 border border-border/40 text-center">
                <span className="text-[10px] uppercase font-semibold text-muted-foreground">Datasheets</span>
                <p className="text-xl sm:text-2xl font-bold font-display text-foreground mt-0.5">
                  {documents.length}
                </p>
                <span className="text-[10px] text-muted-foreground/80">Hardware manuals</span>
              </div>
            </div>

            {/* Evidence details */}
            <div className="p-3 rounded-lg bg-muted/20 border border-border/40">
              <p className="text-[11px] font-semibold text-foreground/90 mb-1.5">
                Active Project Files ({files.length}):
              </p>
              {files.length === 0 ? (
                <p className="text-[11px] text-muted-foreground">
                  No firmware source files uploaded for this project yet. Upload .c/.cpp/.h files in the workspace to view syntax trees and AST diagnostics.
                </p>
              ) : (
                <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                  {files.map((f) => (
                    <span
                      key={f.id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-card border border-border/60 text-[11px] text-foreground/80"
                    >
                      <FileCode className="h-3 w-3 text-[var(--color-emerald)]" />
                      <span className="truncate max-w-[140px]">{f.filename}</span>
                      <span className="text-[9px] text-muted-foreground">({formatBytes(f.size_bytes)})</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </CardContent>

          <CardFooter className="pt-2 border-t border-border/30 text-[11px] text-muted-foreground flex items-center justify-between">
            <span>Grounded on ChromaDB + Neon PostgreSQL</span>
            <Link href="/workspace" className="text-[var(--accent-purple)] hover:underline flex items-center gap-1">
              <span>Manage Repository</span>
              <ChevronRight className="h-3 w-3" />
            </Link>
          </CardFooter>
        </Card>

        {/* ── CARD 4: DOCUMENTS & DATASHEETS (Col 5) ── */}
        <Card variant="default" className="md:col-span-12 lg:col-span-5 flex flex-col justify-between interactive-card group">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <FileText className="h-4 w-4 text-[var(--accent-indigo)] group-hover:scale-105 transition-transform motion-reduce:group-hover:scale-100" />
                Hardware Datasheets (RAG)
              </CardTitle>
              <Badge variant="outline" className="text-[10px]">
                {documents.length} attached
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Hardware reference manuals indexed to verify pinouts and peripheral registers.
            </CardDescription>
          </CardHeader>

          <CardContent className="flex-1 space-y-2 text-xs overflow-y-auto max-h-56">
            {!isSignedIn ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <p className="text-muted-foreground font-medium">Datasheet repository</p>
                <p className="text-[11px] text-muted-foreground/70 mt-1 mb-2">Sign in to connect ESP32, STM32, and custom MCU datasheets</p>
                <SignInButton mode="modal">
                  <Button variant="outline" size="sm" className="text-xs">Sign In</Button>
                </SignInButton>
              </div>
            ) : documents.length === 0 ? (
              <div className="p-4 text-center rounded-lg border border-dashed border-border/60 bg-muted/20">
                <FileText className="h-5 w-5 mx-auto mb-1.5 text-muted-foreground/60" />
                <p className="text-muted-foreground">No datasheets attached.</p>
                <p className="text-[11px] text-muted-foreground/70 mt-0.5 mb-2">
                  Upload MCU technical reference manuals (PDF) to ground fixes in register maps.
                </p>
                <Button variant="outline" size="sm" asChild className="text-xs">
                  <Link href="/workspace">Upload Datasheet</Link>
                </Button>
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-card/40 border border-border/40 hover:border-border/70 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-3.5 w-3.5 text-[var(--accent-indigo)] shrink-0" />
                    <div className="truncate">
                      <p className="font-medium text-foreground truncate">{doc.filename}</p>
                      <p className="text-[10px] text-muted-foreground">{formatBytes(doc.size_bytes)} {doc.page_count ? `• ${doc.page_count} pages` : ""}</p>
                    </div>
                  </div>
                  <Badge variant={doc.extraction_status === "ready" ? "success" : "outline"} className="text-[10px] shrink-0">
                    {doc.extraction_status}
                  </Badge>
                </div>
              ))
            )}
          </CardContent>

          <CardFooter className="pt-2 border-t border-border/30 text-[11px] text-muted-foreground flex items-center justify-between">
            <span>RAG context auto-injected during diagnosis</span>
            <Link href="/workspace" className="text-[var(--accent-purple)] hover:underline flex items-center gap-1 group">
              <span>Upload Manual</span>
              <ChevronRight className="h-3 w-3 group-hover:translate-x-0.5 transition-transform motion-reduce:group-hover:translate-x-0" />
            </Link>
          </CardFooter>
        </Card>

      </div>

      <CreateProjectDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={handleCreateProject}
      />
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Architectural Capabilities Section (#problem / #how-it-works)
   ──────────────────────────────────────────────────────────── */

function CapabilitiesOverview() {
  return (
    <section id="problem" className="py-16 px-4 sm:px-6 max-w-7xl mx-auto border-t border-border/40">
      <div className="text-center max-w-2xl mx-auto mb-12">
        <Badge variant="ai" className="mb-3 text-[10px]">Core Architecture</Badge>
        <h2 className="text-2xl sm:text-3xl font-bold font-display tracking-tight text-foreground">
          Engineered for Embedded Developers
        </h2>
        <p className="text-sm text-muted-foreground mt-2">
          General AI models hallucinate register names and pin numbers. Our specialized architecture grounds every diagnosis in verified firmware syntax and hardware reference manuals.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card variant="default" className="p-6 interactive-card group border-border/40 hover:border-[var(--accent-purple)]/30">
          <div className="h-10 w-10 rounded-lg bg-[var(--accent-purple)]/15 flex items-center justify-center text-[var(--accent-purple)] mb-4 group-hover:bg-[var(--accent-purple)]/25 transition-colors">
            <Terminal className="h-5 w-5 group-hover:scale-110 transition-transform motion-reduce:group-hover:scale-100" />
          </div>
          <h3 className="font-semibold text-base mb-1.5 text-foreground">Compiler Error Disassembly</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Parses GCC, Clang, and idf.py error cascades. Isolates missing declarations, linker symbol clashes, and header cycle faults down to exact file lines.
          </p>
        </Card>

        <Card variant="default" className="p-6 interactive-card group border-border/40 hover:border-[var(--color-emerald)]/30">
          <div className="h-10 w-10 rounded-lg bg-[var(--color-emerald)]/15 flex items-center justify-center text-[var(--color-emerald)] mb-4 group-hover:bg-[var(--color-emerald)]/25 transition-colors">
            <FileTerminal className="h-5 w-5 group-hover:scale-110 transition-transform motion-reduce:group-hover:scale-100" />
          </div>
          <h3 className="font-semibold text-base mb-1.5 text-foreground">Serial Panic Trace Analysis</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Ingests UART and serial crash dumps. Decodes ESP32 backtraces, Guru Meditation Errors, FreeRTOS stack overflows, and HardFault handler records.
          </p>
        </Card>

        <Card variant="default" className="p-6 interactive-card group border-border/40 hover:border-[var(--accent-indigo)]/30">
          <div className="h-10 w-10 rounded-lg bg-[var(--accent-indigo)]/15 flex items-center justify-center text-[var(--accent-indigo)] mb-4 group-hover:bg-[var(--accent-indigo)]/25 transition-colors">
            <FileText className="h-5 w-5 group-hover:scale-110 transition-transform motion-reduce:group-hover:scale-100" />
          </div>
          <h3 className="font-semibold text-base mb-1.5 text-foreground">Datasheet RAG Grounding</h3>
          <p className="text-xs text-muted-foreground leading-relaxed">
            ChromaDB vector embeddings index your hardware datasheets. Proposed code fixes cite confirmed register bitmasks, peripheral clocks, and pinout specs.
          </p>
        </Card>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Diagnostic Demo Reference (#demo)
   ──────────────────────────────────────────────────────────── */

function InteractiveDemoReference() {
  return (
    <section id="demo" className="py-16 px-4 sm:px-6 max-w-7xl mx-auto border-t border-border/40">
      <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
        <div className="max-w-xl">
          <Badge variant="outline" className="mb-3 text-[10px] border-[var(--color-emerald)]/40 text-[var(--color-emerald)]">
            Live Diagnostic Example
          </Badge>
          <h2 className="text-2xl sm:text-3xl font-bold font-display tracking-tight text-foreground">
            From Build Failure to Verified Patch
          </h2>
          <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
            Watch how the platform parses an idf.py build failure, matches against FreeRTOS GPIO driver documentation, and generates a ready-to-commit code diff.
          </p>
          <div className="mt-6 flex items-center gap-3">
            <Button variant="ai" size="sm" asChild>
              <Link href="/workspace">
                <span>Try in Workspace</span>
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>

        <div className="w-full max-w-lg rounded-xl border border-[var(--color-code-border)] bg-[var(--color-code-bg)] overflow-hidden shadow-2xl">
          <div className="flex items-center justify-between border-b border-[var(--color-code-border)] px-4 py-2.5 text-xs text-muted-foreground">
            <span className="font-mono">idf.py build — ESP32-S3</span>
            <Badge variant="error" className="text-[10px]">Error 1</Badge>
          </div>
          <div className="p-4 font-mono text-[12px] leading-6 space-y-1 overflow-x-auto text-muted-foreground">
            <p className="text-foreground/80">$ idf.py build</p>
            <p className="text-[var(--color-error-red)]">main.c:6:21: error: use of undeclared identifier &apos;GPIO_SEL_2&apos;</p>
            <p className="text-[var(--color-warning-amber)]">main.c:7:13: note: did you mean &apos;GPIO_MODE_OUTPUT&apos;?</p>
            <div className="mt-3 pt-2 border-t border-border/40">
              <p className="text-[var(--color-success-green)] font-semibold">AI Recommended Fix:</p>
              <p className="text-[var(--color-success-green)]">+ .pin_bit_mask = (1ULL &lt;&lt; 2);</p>
              <p className="text-[var(--color-success-green)]">+ .mode = GPIO_MODE_OUTPUT;</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────────────────────────────────
   Footer
   ──────────────────────────────────────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border/40 bg-[oklch(0.11_0.015_260)]">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 py-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-br from-[var(--accent-purple)] to-[var(--accent-indigo)]">
              <Bug className="h-3 w-3 text-white" />
            </div>
            <span className="text-xs font-semibold text-foreground">
              AI Embedded Debugger
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} AI Embedded Debugger. Grounded firmware intelligence.
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ────────────────────────────────────────────────────────────
   Main Page Export
   ──────────────────────────────────────────────────────────── */

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <Navbar />
      <main className="flex-1">
        <BentoDashboard />
        <CapabilitiesOverview />
        <InteractiveDemoReference />
      </main>
      <Footer />
    </div>
  );
}
