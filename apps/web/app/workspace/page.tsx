"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Bug,
  CheckCircle2,
  ChevronDown,
  Code2,
  FileCode,
  FileTerminal,
  FileText,
  FolderOpen,
  Lightbulb,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Terminal,
  Trash2,
  Upload,
  X,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { UserButton } from "@clerk/nextjs";
import { useApiClient, type ProjectFileMetadata } from "@/lib/api-client";

export type Project = {
  id: string;
  name: string;
  description?: string;
  active?: boolean; // UI state
};

type DiagnosisResult = {
  problem_observed: string;
  evidence_used: string[];
  likely_causes: { cause: string; plausibility: "high" | "medium" | "low" }[];
  recommended_steps: string[];
  proposed_fix: string;
  corrected_code?: string | null;
  risks_limitations?: string | null;
  follow_up_required?: string | null;
};

const CODE_EXTENSIONS = ".c,.cpp,.h,.hpp,.cc,.cxx,.ino";
const LOG_EXTENSIONS = ".log,.txt";
const ALL_EXTENSIONS = `${CODE_EXTENSIONS},${LOG_EXTENSIONS}`;

/* ────────────────────────────────────────────────────────────
   Toast Notification
   ──────────────────────────────────────────────────────────── */

type ToastType = "success" | "error";

function Toast({
  message,
  type,
  onClose,
}: {
  message: string;
  type: ToastType;
  onClose: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur-sm animate-in slide-in-from-bottom-4 ${
        type === "success"
          ? "border-[var(--color-emerald)]/30 bg-[var(--color-emerald)]/10 text-[var(--color-emerald)]"
          : "border-[var(--color-error-red)]/30 bg-[var(--color-error-red)]/10 text-[var(--color-error-red)]"
      }`}
    >
      {type === "success" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0" />
      ) : (
        <AlertCircle className="h-4 w-4 shrink-0" />
      )}
      <span className="max-w-xs truncate">{message}</span>
      <button onClick={onClose} className="ml-1 opacity-60 hover:opacity-100">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Application Header
   ──────────────────────────────────────────────────────────── */

function AppHeader({
  sidebarOpen,
  onToggleSidebar,
  activeProject,
}: {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  activeProject?: Project;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center border-b border-border/60 bg-[var(--color-code-bg)] px-3">
      {/* Left — branding + sidebar toggle */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
        >
          {sidebarOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeftOpen className="h-4 w-4" />
          )}
        </Button>

        <Separator orientation="vertical" className="mx-1 h-5" />

        <Link href="/" className="flex items-center gap-2" aria-label="Home">
          <div className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-emerald)]">
            <Bug className="h-3 w-3 text-[var(--color-code-bg)]" />
          </div>
          <span className="hidden text-sm font-semibold text-foreground sm:inline">
            AI Embedded Debugger
          </span>
        </Link>
      </div>

      {/* Center — project name */}
      <div className="ml-4 flex items-center gap-2">
        <FolderOpen className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-sm text-foreground/90">
          {activeProject ? activeProject.name : "Select a project"}
        </span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </div>

      {/* Right — status + avatar */}
      <div className="ml-auto flex items-center gap-3">
        <Badge
          variant="outline"
          className="hidden border-[var(--color-emerald)]/30 text-[var(--color-emerald)] text-[10px] sm:inline-flex"
        >
          Ready
        </Badge>
        <Separator orientation="vertical" className="h-5" />
        <UserButton />
      </div>
    </header>
  );
}

/* ────────────────────────────────────────────────────────────
   Sidebar
   ──────────────────────────────────────────────────────────── */

function Sidebar({
  open,
  projects,
  onCreateProject,
  onSelectProject,
}: {
  open: boolean;
  projects: Project[];
  onCreateProject: () => void;
  onSelectProject: (id: string) => void;
}) {
  if (!open) return null;

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border/60 bg-[var(--color-code-bg)]">
      {/* Projects header */}
      <div className="flex items-center justify-between px-3 py-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Projects
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-[var(--color-emerald)]"
          aria-label="New project"
          onClick={onCreateProject}
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      <Separator />

      {/* Project list */}
      <nav
        className="flex-1 overflow-y-auto px-2 py-1.5"
        aria-label="Project list"
      >
        {projects.length === 0 ? (
          <div className="px-2 py-4 text-center text-xs text-muted-foreground">
            No projects yet. Create one!
          </div>
        ) : (
          projects.map((project) => (
            <button
              key={project.id}
              onClick={() => onSelectProject(project.id)}
              className={`flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                project.active
                  ? "bg-[var(--color-surface-overlay)] text-foreground"
                  : "text-muted-foreground hover:bg-[var(--color-surface-overlay)]/50 hover:text-foreground"
              }`}
            >
              <FolderOpen className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{project.name}</span>
              {project.active && (
                <div className="ml-auto h-1.5 w-1.5 rounded-full bg-[var(--color-emerald)]" />
              )}
            </button>
          ))
        )}
      </nav>

      {/* Bottom nav */}
      <Separator />
      <div className="px-2 py-2">
        <button className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm text-muted-foreground transition-colors hover:bg-[var(--color-surface-overlay)]/50 hover:text-foreground">
          <Settings className="h-3.5 w-3.5" />
          <span>Settings</span>
        </button>
      </div>
    </aside>
  );
}

/* ────────────────────────────────────────────────────────────
   Project Files Panel (sidebar sub-panel in main area)
   ──────────────────────────────────────────────────────────── */

function fileIcon(fileType: string, filename: string) {
  if (fileType === "log") return <FileText className="h-3.5 w-3.5 shrink-0" />;
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "ino") return <FileCode className="h-3.5 w-3.5 shrink-0 text-[var(--color-emerald)]" />;
  return <FileCode className="h-3.5 w-3.5 shrink-0" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ProjectFilesPanel({
  files,
  selectedFileId,
  isUploading,
  onUpload,
  onSelectFile,
  onDeleteFile,
}: {
  files: ProjectFileMetadata[];
  selectedFileId: string | null;
  isUploading: boolean;
  onUpload: (file: File) => void;
  onSelectFile: (fileId: string) => void;
  onDeleteFile: (fileId: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex w-52 shrink-0 flex-col border-r border-border/60 bg-[var(--color-code-bg)]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Files
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-[var(--color-emerald)]"
          aria-label="Upload file"
          disabled={isUploading}
          onClick={() => inputRef.current?.click()}
        >
          {isUploading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Upload className="h-3.5 w-3.5" />
          )}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={ALL_EXTENSIONS}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            // Reset so the same file can be re-uploaded
            e.target.value = "";
          }}
        />
      </div>

      <Separator />

      {/* File list */}
      <nav className="flex-1 overflow-y-auto px-1.5 py-1" aria-label="File list">
        {files.length === 0 && !isUploading && (
          <button
            className="mt-2 flex w-full flex-col items-center gap-2 rounded-lg border border-dashed border-border/60 px-3 py-4 text-center text-muted-foreground/50 transition-colors hover:border-[var(--color-emerald)]/40 hover:text-muted-foreground"
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-5 w-5" />
            <span className="text-[10px] leading-tight">
              Upload C/C++ source
              <br />
              or log files
            </span>
          </button>
        )}

        {isUploading && (
          <div className="flex items-center gap-2 rounded-md px-2 py-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span>Uploading…</span>
          </div>
        )}

        {files.map((f) => (
          <div
            key={f.id}
            className={`group flex items-center gap-1.5 rounded-md px-2 py-1.5 text-left transition-colors cursor-pointer ${
              selectedFileId === f.id
                ? "bg-[var(--color-surface-overlay)] text-foreground"
                : "text-muted-foreground hover:bg-[var(--color-surface-overlay)]/50 hover:text-foreground"
            }`}
            onClick={() => onSelectFile(f.id)}
          >
            {fileIcon(f.file_type, f.filename)}
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-xs">{f.filename}</span>
              <span className="text-[10px] text-muted-foreground/60">
                {formatSize(f.size_bytes)}
              </span>
            </div>
            <button
              className="ml-auto hidden h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground/40 hover:text-[var(--color-error-red)] group-hover:flex"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteFile(f.id);
              }}
              aria-label={`Delete ${f.filename}`}
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        ))}
      </nav>

      {/* Upload button at bottom */}
      {files.length > 0 && (
        <>
          <Separator />
          <div className="px-2 py-2">
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start gap-2 text-xs text-muted-foreground hover:text-[var(--color-emerald)]"
              onClick={() => inputRef.current?.click()}
              disabled={isUploading}
            >
              <Upload className="h-3 w-3" />
              Upload file
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Evidence Tabs
   ──────────────────────────────────────────────────────────── */

type EvidenceTab = "firmware" | "compiler" | "serial";

function EvidenceTabBar({
  active,
  onTabChange,
}: {
  active: EvidenceTab;
  onTabChange: (tab: EvidenceTab) => void;
}) {
  const tabs: { id: EvidenceTab; label: string; icon: React.ElementType }[] = [
    { id: "firmware", label: "Firmware", icon: FileCode },
    { id: "compiler", label: "Compiler Output", icon: FileTerminal },
    { id: "serial", label: "Serial Logs", icon: Terminal },
  ];

  return (
    <div
      className="flex items-center border-b border-border/60 bg-[var(--color-code-bg)]"
      role="tablist"
      aria-label="Evidence tabs"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          className={`flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-medium transition-colors ${
            active === tab.id
              ? "border-[var(--color-emerald)] text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground/80"
          }`}
          onClick={() => onTabChange(tab.id)}
        >
          <tab.icon className="h-3.5 w-3.5" />
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Firmware Panel — code viewer
   ──────────────────────────────────────────────────────────── */

function FirmwarePanel({
  value,
  onChange,
  activeFileName,
}: {
  value: string;
  onChange: (v: string) => void;
  activeFileName?: string;
}) {
  return (
    <div className="flex flex-1 flex-col bg-[var(--color-code-bg)] font-mono text-[13px] leading-6">
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--color-code-border)] bg-[var(--color-code-bg)] px-4 py-1.5">
        <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          {activeFileName || "main.c"}
        </span>
      </div>
      <textarea
        className="flex-1 w-full resize-none bg-transparent p-4 text-foreground/80 outline-none placeholder:text-muted-foreground/30"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste C/C++ firmware code here, or upload a file from the Files panel…"
        spellCheck={false}
      />
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Compiler Output Panel
   ──────────────────────────────────────────────────────────── */

function CompilerPanel({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col bg-[var(--color-code-bg)] font-mono text-[13px] leading-6">
      <textarea
        className="flex-1 w-full resize-none bg-transparent p-4 text-foreground/80 outline-none placeholder:text-muted-foreground/30"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste compiler output here…"
        spellCheck={false}
      />
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Serial Log Panel
   ──────────────────────────────────────────────────────────── */

function SerialPanel({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col bg-[var(--color-code-bg)] font-mono text-[13px] leading-6">
      <textarea
        className="flex-1 w-full resize-none bg-transparent p-4 text-foreground/80 outline-none placeholder:text-muted-foreground/30"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Paste serial logs here…"
        spellCheck={false}
      />
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Diagnosis Panel
   ──────────────────────────────────────────────────────────── */

function DiagnosisPanel({
  diagnosis,
  isAnalyzing,
}: {
  diagnosis: DiagnosisResult | null;
  isAnalyzing: boolean;
}) {
  return (
    <div className="flex flex-1 flex-col overflow-hidden border-t border-border/60 lg:border-t-0 lg:border-l">
      {/* Panel header */}
      <div className="flex items-center gap-2 border-b border-border/60 bg-[var(--color-code-bg)] px-4 py-2.5">
        <Zap className="h-3.5 w-3.5 text-[var(--color-emerald)]" />
        <span className="text-xs font-medium text-[var(--color-emerald)]">
          AI Diagnosis
        </span>
        <Badge
          variant="outline"
          className="ml-auto border-border/60 text-muted-foreground/60 text-[10px]"
        >
          {isAnalyzing
            ? "Analyzing..."
            : diagnosis
              ? "Complete"
              : "Awaiting analysis"}
        </Badge>
      </div>

      <div className="flex-1 overflow-y-auto bg-[var(--color-code-bg)]">
        {isAnalyzing && (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin" />
            <p className="text-sm">Analyzing firmware and logs...</p>
          </div>
        )}

        {!isAnalyzing && !diagnosis && (
          <div className="flex h-full flex-col items-center justify-center gap-4 px-8 py-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border/60 bg-[var(--color-surface-overlay)]">
              <Search className="h-6 w-6 text-muted-foreground/50" />
            </div>
            <div className="max-w-xs">
              <h3 className="text-sm font-semibold text-foreground">
                No analysis yet
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                Click{" "}
                <span className="font-medium text-[var(--color-emerald)]">
                  &quot;Analyze with AI&quot;
                </span>{" "}
                to send your firmware code, compiler output, and serial logs for
                evidence‑aware diagnosis.
              </p>
            </div>

            {/* Placeholder sections */}
            <div className="mt-4 w-full max-w-xs space-y-3">
              {[
                {
                  icon: Lightbulb,
                  label: "Diagnosis",
                  desc: "Root cause analysis",
                },
                {
                  icon: Code2,
                  label: "Evidence",
                  desc: "What the data shows",
                },
                {
                  icon: Zap,
                  label: "Suggested Fix",
                  desc: "Corrected code & steps",
                },
              ].map((section) => (
                <div
                  key={section.label}
                  className="flex items-center gap-3 rounded-lg border border-dashed border-border/60 px-3 py-2.5"
                >
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-surface-overlay)]">
                    <section.icon className="h-3.5 w-3.5 text-muted-foreground/40" />
                  </div>
                  <div className="text-left">
                    <p className="text-xs font-medium text-muted-foreground/60">
                      {section.label}
                    </p>
                    <p className="text-[10px] text-muted-foreground/40">
                      {section.desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!isAnalyzing && diagnosis && (
          <div className="flex flex-col gap-6 p-6">
            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Lightbulb className="h-4 w-4 text-[var(--color-emerald)]" />{" "}
                Problem Observed
              </h3>
              <p className="text-sm leading-relaxed text-foreground/80">
                {diagnosis.problem_observed}
              </p>
            </section>

            <Separator className="bg-border/60" />

            <section>
              <h3 className="mb-2 text-sm font-semibold text-foreground">
                Likely Causes
              </h3>
              <ul className="space-y-2">
                {diagnosis.likely_causes.map((lc, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 rounded-md bg-[var(--color-surface-overlay)] p-3"
                  >
                    <Badge
                      variant="outline"
                      className={`shrink-0 text-[10px] ${
                        lc.plausibility === "high"
                          ? "border-[var(--color-error-red)]/50 text-[var(--color-error-red)]"
                          : lc.plausibility === "medium"
                            ? "border-[var(--color-warning-amber)]/50 text-[var(--color-warning-amber)]"
                            : "border-muted-foreground/50 text-muted-foreground"
                      }`}
                    >
                      {lc.plausibility.toUpperCase()}
                    </Badge>
                    <span className="text-sm text-foreground/80">
                      {lc.cause}
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Code2 className="h-4 w-4" /> Evidence Used
              </h3>
              <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                {diagnosis.evidence_used.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </section>

            <Separator className="bg-border/60" />

            <section>
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Zap className="h-4 w-4 text-[var(--color-warning-amber)]" />{" "}
                Proposed Fix & Steps
              </h3>
              <p className="mb-3 text-sm leading-relaxed text-foreground/80">
                {diagnosis.proposed_fix}
              </p>

              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Recommended Steps
                </h4>
                <ol className="list-inside list-decimal space-y-1 text-sm text-foreground/80">
                  {diagnosis.recommended_steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            </section>

            {diagnosis.corrected_code && (
              <section>
                <h4 className="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Corrected Code
                </h4>
                <pre className="overflow-x-auto rounded-md border border-[var(--color-code-border)] bg-[#0d1117] p-4 font-mono text-[13px] text-foreground/80">
                  <code>{diagnosis.corrected_code}</code>
                </pre>
              </section>
            )}

            {(diagnosis.risks_limitations || diagnosis.follow_up_required) && (
              <section className="rounded-lg border border-[var(--color-warning-amber)]/20 bg-[var(--color-warning-amber)]/5 p-4">
                {diagnosis.risks_limitations && (
                  <div className="mb-2">
                    <h4 className="text-xs font-semibold text-[var(--color-warning-amber)] uppercase tracking-wider">
                      Risks & Limitations
                    </h4>
                    <p className="mt-1 text-sm text-[var(--color-warning-amber)]/90">
                      {diagnosis.risks_limitations}
                    </p>
                  </div>
                )}
                {diagnosis.follow_up_required && (
                  <div>
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Follow-up Info Needed
                    </h4>
                    <p className="mt-1 text-sm text-muted-foreground/90">
                      {diagnosis.follow_up_required}
                    </p>
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Main Area
   ──────────────────────────────────────────────────────────── */

function MainArea({ activeProject }: { activeProject?: Project }) {
  const [activeTab, setActiveTab] = useState<EvidenceTab>("firmware");

  const [firmwareCode, setFirmwareCode] = useState("");
  const [compilerOutput, setCompilerOutput] = useState("");
  const [serialLogs, setSerialLogs] = useState("");
  const [activeFileName, setActiveFileName] = useState<string | undefined>(
    undefined
  );

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);

  // Files state
  const [files, setFiles] = useState<ProjectFileMetadata[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoadingFile, setIsLoadingFile] = useState(false);

  // Toast
  const [toast, setToast] = useState<{
    message: string;
    type: ToastType;
  } | null>(null);
  const showToast = useCallback(
    (message: string, type: ToastType) => setToast({ message, type }),
    []
  );

  const api = useApiClient();

  // Load files when project changes
  useEffect(() => {
    if (!activeProject) {
      setFiles([]);
      setSelectedFileId(null);
      return;
    }

    let cancelled = false;
    async function loadFiles() {
      try {
        const data = await api.listFiles(activeProject!.id);
        if (!cancelled) setFiles(data);
      } catch (e) {
        console.error("Failed to load files", e);
      }
    }
    loadFiles();
    return () => {
      cancelled = true;
    };
  }, [activeProject, api]);

  // Upload handler
  const handleUpload = useCallback(
    async (file: File) => {
      if (!activeProject) return;
      setIsUploading(true);
      try {
        const uploaded = await api.uploadFile(activeProject.id, file);
        setFiles((prev) => [uploaded, ...prev]);
        showToast(`Uploaded ${file.name}`, "success");
      } catch (e) {
        console.error("Upload failed", e);
        const msg =
          e instanceof Error ? e.message : "Upload failed. Please try again.";
        showToast(msg, "error");
      } finally {
        setIsUploading(false);
      }
    },
    [activeProject, api, showToast]
  );

  // Select file → load content into appropriate tab
  const handleSelectFile = useCallback(
    async (fileId: string) => {
      if (!activeProject) return;
      setSelectedFileId(fileId);
      setIsLoadingFile(true);

      try {
        const result = await api.getFileContent(activeProject.id, fileId);
        const { metadata, content } = result;

        if (metadata.file_type === "code") {
          setFirmwareCode(content);
          setActiveFileName(metadata.filename);
          setActiveTab("firmware");
        } else {
          // Log files — determine if it looks like compiler output or serial
          const looksLikeCompiler =
            /error:|warning:|undefined reference|linker|gcc|g\+\+/i.test(
              content.slice(0, 500)
            );
          if (looksLikeCompiler) {
            setCompilerOutput(content);
            setActiveTab("compiler");
          } else {
            setSerialLogs(content);
            setActiveTab("serial");
          }
        }
      } catch (e) {
        console.error("Failed to load file content", e);
        showToast("Failed to load file content", "error");
      } finally {
        setIsLoadingFile(false);
      }
    },
    [activeProject, api, showToast]
  );

  // Delete file
  const handleDeleteFile = useCallback(
    async (fileId: string) => {
      if (!activeProject) return;
      try {
        await api.deleteFile(activeProject.id, fileId);
        setFiles((prev) => prev.filter((f) => f.id !== fileId));
        if (selectedFileId === fileId) setSelectedFileId(null);
        showToast("File deleted", "success");
      } catch (e) {
        console.error("Failed to delete file", e);
        showToast("Failed to delete file", "error");
      }
    },
    [activeProject, api, selectedFileId, showToast]
  );

  const handleAnalyze = async () => {
    if (!activeProject) return;
    if (
      !firmwareCode.trim() &&
      !compilerOutput.trim() &&
      !serialLogs.trim()
    )
      return;

    setIsAnalyzing(true);
    setDiagnosis(null);
    try {
      const res = await api.analyzeDebug(
        activeProject.id,
        firmwareCode,
        compilerOutput,
        serialLogs
      );
      setDiagnosis(res);
    } catch (e) {
      console.error(e);
      showToast("Analysis failed. Please try again.", "error");
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!activeProject) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-[var(--color-surface-raised)] text-muted-foreground">
        <FolderOpen className="h-10 w-10 opacity-20 mb-4" />
        <p>Select or create a project from the sidebar.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Main header */}
      <div className="flex items-center justify-between border-b border-border/60 bg-[var(--color-surface-raised)] px-4 py-2.5">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-4 w-4 text-[var(--color-emerald)]" />
          <h1 className="text-sm font-semibold text-foreground">
            {activeProject.name}
          </h1>
          {isLoadingFile && (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
          )}
        </div>

        <Button
          size="sm"
          className="gap-2 text-xs font-semibold"
          onClick={handleAnalyze}
          disabled={
            isAnalyzing ||
            (!firmwareCode.trim() &&
              !compilerOutput.trim() &&
              !serialLogs.trim())
          }
        >
          {isAnalyzing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="h-3.5 w-3.5" />
          )}
          {isAnalyzing ? "Analyzing..." : "Analyze with AI"}
        </Button>
      </div>

      {/* Content — files panel + evidence + diagnosis */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left — files sidebar */}
        <div className="hidden lg:contents">
          <ProjectFilesPanel
            files={files}
            selectedFileId={selectedFileId}
            isUploading={isUploading}
            onUpload={handleUpload}
            onSelectFile={handleSelectFile}
            onDeleteFile={handleDeleteFile}
          />
        </div>

        {/* Center — evidence input */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <EvidenceTabBar active={activeTab} onTabChange={setActiveTab} />

          {/* Tab panels */}
          <div className="flex flex-1 overflow-hidden" role="tabpanel">
            {activeTab === "firmware" && (
              <FirmwarePanel
                value={firmwareCode}
                onChange={setFirmwareCode}
                activeFileName={activeFileName}
              />
            )}
            {activeTab === "compiler" && (
              <CompilerPanel
                value={compilerOutput}
                onChange={setCompilerOutput}
              />
            )}
            {activeTab === "serial" && (
              <SerialPanel value={serialLogs} onChange={setSerialLogs} />
            )}
          </div>
        </div>

        {/* Right — diagnosis */}
        <DiagnosisPanel diagnosis={diagnosis} isAnalyzing={isAnalyzing} />
      </div>

      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Workspace Page
   ──────────────────────────────────────────────────────────── */

export default function WorkspacePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  const api = useApiClient();

  useEffect(() => {
    async function loadProjects() {
      try {
        const data = await api.getProjects();
        // Set first project active by default if available
        if (data.length > 0) {
          data[0].active = true;
        }
        setProjects(data);
      } catch (e) {
        console.error("Failed to load projects", e);
      } finally {
        setLoading(false);
      }
    }
    loadProjects();
  }, [api]);

  const handleCreateProject = async () => {
    try {
      const name = `New Project ${projects.length + 1}`;
      const newProject = await api.createProject(name, "Autogenerated project");

      const updatedProjects = projects.map((p) => ({ ...p, active: false }));
      newProject.active = true;
      setProjects([newProject, ...updatedProjects]);
    } catch (e) {
      console.error("Failed to create project", e);
    }
  };

  const handleSelectProject = (id: string) => {
    setProjects(projects.map((p) => ({ ...p, active: p.id === id })));
  };

  const activeProject = projects.find((p) => p.active);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <AppHeader
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        activeProject={activeProject}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — hidden on mobile via CSS, toggled on desktop */}
        <div className="hidden md:contents">
          {loading ? (
            <aside className="flex w-56 shrink-0 items-center justify-center border-r border-border/60 bg-[var(--color-code-bg)] text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
            </aside>
          ) : (
            <Sidebar
              open={sidebarOpen}
              projects={projects}
              onCreateProject={handleCreateProject}
              onSelectProject={handleSelectProject}
            />
          )}
        </div>

        <MainArea activeProject={activeProject} />
      </div>
    </div>
  );
}
