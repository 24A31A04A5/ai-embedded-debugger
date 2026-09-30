"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Code2,
  FolderOpen,
  Plus,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  useApiClient,
  type ProjectFileMetadata,
  type DebugSessionSummary,
  type FeedbackResponse,
} from "@/lib/api-client";
import {
  WorkspaceHeader,
  ProjectFilesPanel,
  CodeWorkspace,
  DiagnosticTabs,
  StatusBar,
  getLanguageInfo,
  detectLineEnding,
  type Project,
  type EditorTab,
  type BottomPanelTab,
  type Problem,
  type AIStatus,
} from "@/components/workspace";
import { type CodeEditorHandle, type CursorPosition } from "@/components/CodeEditor";
import { AIAnalysisPanel, type DiagnosisResult } from "@/components/ai";

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
      role="status"
      className="fixed bottom-8 left-4 right-4 z-50 flex items-center gap-2 rounded border border-ide-border bg-[oklch(0.21_0.004_270)] px-3 py-2.5 text-sm shadow-xl sm:left-auto sm:right-4 sm:max-w-md animate-in slide-in-from-bottom-4"
    >
      {type === "success" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--color-emerald)]" />
      ) : (
        <AlertCircle className="h-4 w-4 shrink-0 text-[var(--color-error-red)]" />
      )}
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground">{message}</span>
      <button
        onClick={onClose}
        className="ml-1 flex h-9 w-9 lg:h-6 lg:w-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-ide-hover hover:text-foreground"
        aria-label="Close notification"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────────────────────── */

const UNTITLED_ID = "__untitled__";
const TAB_SIZE = 4;

const normalizeEol = (s: string) => s.replace(/\r\n?/g, "\n");

function toSeverity(level: string): Problem["severity"] {
  if (level === "critical" || level === "high") return "error";
  if (level === "medium") return "warning";
  return "info";
}

function problemsFromDiagnosis(diagnosis: DiagnosisResult | null): Problem[] {
  if (!diagnosis) return [];
  const list: Problem[] = [];
  for (const m of diagnosis.compiler_messages ?? []) {
    list.push({
      severity: m.message_type.includes("error") ? "error" : m.message_type.includes("warning") ? "warning" : "info",
      message: m.message,
      source: m.message_type.startsWith("linker") ? "linker" : "compiler",
      file: m.file,
      line: m.line,
      column: m.column,
    });
  }
  for (const issue of diagnosis.code_issues ?? []) {
    const lineMatch = issue.location?.match(/(?:line\s*|:)(\d+)/i);
    list.push({
      severity: toSeverity(issue.severity),
      message: issue.description,
      source: "AI analysis",
      location: issue.location,
      line: lineMatch ? Number(lineMatch[1]) : null,
    });
  }
  return list;
}

const isDesktopViewport = () =>
  typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;

/* ────────────────────────────────────────────────────────────
   Workspace Page Root
   ──────────────────────────────────────────────────────────── */

export default function WorkspacePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isDiagnosticsCollapsed, setIsDiagnosticsCollapsed] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomPanelTab>("output");
  const [activeMobileView, setActiveMobileView] = useState<
    "code" | "diagnostics" | "ai" | "files"
  >("code");

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  // Active Project Content State
  const [firmwareCode, setFirmwareCode] = useState("");
  const [compilerOutput, setCompilerOutput] = useState("");
  const [serialLogs, setSerialLogs] = useState("");

  // Editor tabs: the active buffer lives in `firmwareCode`; inactive buffers are stashed.
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const buffersRef = useRef(new Map<string, string>());
  const originalsRef = useRef(new Map<string, string>());
  const firmwareCodeRef = useRef(firmwareCode);
  firmwareCodeRef.current = firmwareCode;
  const activeTabIdRef = useRef(activeTabId);
  activeTabIdRef.current = activeTabId;
  const [cursor, setCursor] = useState<CursorPosition>({ line: 1, column: 1, selected: 0 });
  const desktopEditorRef = useRef<CodeEditorHandle>(null);
  const mobileEditorRef = useRef<CodeEditorHandle>(null);

  // AI & Session State
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResult | null>(null);
  const [sessions, setSessions] = useState<DebugSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null);

  // Files State
  const [files, setFiles] = useState<ProjectFileMetadata[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
  const showToast = useCallback(
    (message: string, type: ToastType) => setToast({ message, type }),
    []
  );

  const api = useApiClient();

  // Load projects on initial mount
  useEffect(() => {
    async function loadProjects() {
      try {
        const data = await api.getProjects();
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

  const activeProject = projects.find((p) => p.active);

  // Load files and sessions when active project changes
  useEffect(() => {
    if (!activeProject) {
      setFiles([]);
      setSessions([]);
      setSelectedFileId(null);
      setActiveSessionId(null);
      setDiagnosis(null);
      setAnalysisError(null);
      setFeedback(null);
      return;
    }

    let cancelled = false;
    async function loadProjectData() {
      try {
        const [filesData, sessionsData] = await Promise.all([
          api.listFiles(activeProject!.id),
          api.listSessions(activeProject!.id),
        ]);
        if (!cancelled) {
          setFiles(filesData);
          setSessions(sessionsData);
        }
      } catch (e) {
        console.error("Failed to load project data", e);
      }
    }
    loadProjectData();
    return () => {
      cancelled = true;
    };
  }, [activeProject, api]);

  // Editor tabs belong to a project; the current buffer stays as an untitled document.
  const activeProjectId = activeProject?.id;
  useEffect(() => {
    buffersRef.current.clear();
    originalsRef.current.clear();
    setTabs([]);
    setActiveTabId(null);
  }, [activeProjectId]);

  /* ── Editor tab management ── */

  const stashActiveBuffer = useCallback(() => {
    const current = activeTabIdRef.current;
    const code = firmwareCodeRef.current;
    if (current) {
      buffersRef.current.set(current, code);
    } else if (code.trim()) {
      buffersRef.current.set(UNTITLED_ID, code);
      setTabs((prev) =>
        prev.some((t) => t.id === UNTITLED_ID)
          ? prev
          : [...prev, { id: UNTITLED_ID, name: "Untitled", kind: "scratch" }]
      );
    }
  }, []);

  const openTab = useCallback(
    (tab: EditorTab, content: string) => {
      if (activeTabIdRef.current === tab.id) return;
      stashActiveBuffer();
      setTabs((prev) => (prev.some((t) => t.id === tab.id) ? prev : [...prev, tab]));
      const existing = buffersRef.current.get(tab.id);
      setActiveTabId(tab.id);
      setFirmwareCode(existing ?? content);
    },
    [stashActiveBuffer]
  );

  const activateTab = useCallback(
    (id: string) => {
      if (activeTabIdRef.current === id) return;
      stashActiveBuffer();
      setActiveTabId(id);
      setFirmwareCode(buffersRef.current.get(id) ?? "");
      setSelectedFileId(id.startsWith("session:") || id === UNTITLED_ID ? null : id);
    },
    [stashActiveBuffer]
  );

  const closeTab = useCallback(
    (id: string) => {
      const idx = tabs.findIndex((t) => t.id === id);
      if (idx === -1) return;
      const remaining = tabs.filter((t) => t.id !== id);
      if (activeTabIdRef.current === id) {
        const next = remaining[idx] ?? remaining[idx - 1];
        setActiveTabId(next ? next.id : null);
        setFirmwareCode(next ? buffersRef.current.get(next.id) ?? "" : "");
        setSelectedFileId(next && next.kind === "file" ? next.id : null);
      }
      setTabs(remaining);
      buffersRef.current.delete(id);
      originalsRef.current.delete(id);
    },
    [tabs]
  );

  const displayTabs = useMemo<EditorTab[]>(
    () =>
      tabs.map((t) => {
        const original = originalsRef.current.get(t.id);
        if (original === undefined) return t;
        const current = t.id === activeTabId ? firmwareCode : buffersRef.current.get(t.id) ?? "";
        return { ...t, modified: normalizeEol(current) !== normalizeEol(original) };
      }),
    [tabs, activeTabId, firmwareCode]
  );

  // Project Actions
  const handleCreateProject = async () => {
    try {
      const name = `Project ${projects.length + 1}`;
      const newProject = await api.createProject(name, "Embedded debug project");
      const updatedProjects = projects.map((p) => ({ ...p, active: false }));
      newProject.active = true;
      setProjects([newProject, ...updatedProjects]);
      showToast(`Created ${name}`, "success");
    } catch (e) {
      console.error("Failed to create project", e);
      showToast("Failed to create project", "error");
    }
  };

  const handleSelectProject = (id: string) => {
    setProjects(projects.map((p) => ({ ...p, active: p.id === id })));
  };

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
        const msg = e instanceof Error ? e.message : "Upload failed. Please try again.";
        showToast(msg, "error");
      } finally {
        setIsUploading(false);
      }
    },
    [activeProject, api, showToast]
  );

  // Select file → open in editor or load into logs
  const handleSelectFile = useCallback(
    async (fileId: string) => {
      if (!activeProject) return;
      setSelectedFileId(fileId);

      if (tabs.some((t) => t.id === fileId)) {
        activateTab(fileId);
        setActiveMobileView("code");
        return;
      }

      try {
        const result = await api.getFileContent(activeProject.id, fileId);
        const { metadata, content } = result;

        if (metadata.file_type === "code") {
          originalsRef.current.set(fileId, content);
          openTab({ id: fileId, name: metadata.filename, kind: "file" }, content);
          setActiveMobileView("code");
        } else {
          const looksLikeCompiler =
            /error:|warning:|undefined reference|linker|gcc|g\+\+/i.test(
              content.slice(0, 500)
            );
          if (looksLikeCompiler) {
            setCompilerOutput(content);
            setBottomTab("output");
          } else {
            setSerialLogs(content);
            setBottomTab("serial");
          }
          setIsDiagnosticsCollapsed(false);
          setActiveMobileView("diagnostics");
        }
      } catch (e) {
        console.error("Failed to load file content", e);
        showToast("Failed to load file content", "error");
      }
    },
    [activeProject, api, showToast, tabs, activateTab, openTab]
  );

  // Delete file
  const handleDeleteFile = useCallback(
    async (fileId: string) => {
      if (!activeProject) return;
      try {
        await api.deleteFile(activeProject.id, fileId);
        setFiles((prev) => prev.filter((f) => f.id !== fileId));
        if (selectedFileId === fileId) setSelectedFileId(null);
        closeTab(fileId);
        showToast("File deleted", "success");
      } catch (e) {
        console.error("Failed to delete file", e);
        showToast("Failed to delete file", "error");
      }
    },
    [activeProject, api, selectedFileId, showToast, closeTab]
  );

  // AI Diagnostic Analysis
  const handleAnalyze = async () => {
    if (!activeProject) return;
    if (!firmwareCode.trim() && !compilerOutput.trim() && !serialLogs.trim()) return;

    setIsAnalyzing(true);
    setAnalysisError(null);
    setDiagnosis(null);
    setFeedback(null);
    setActiveSessionId(null);

    try {
      const session = await api.createSession(
        activeProject.id,
        firmwareCode,
        compilerOutput,
        serialLogs
      );

      setSessions((prev) => [
        {
          id: session.id,
          project_id: session.project_id,
          title: session.title,
          created_at: session.created_at,
          updated_at: session.updated_at,
        },
        ...prev,
      ]);
      setActiveSessionId(session.id);

      const aiMsg = session.messages.find((m) => m.role === "assistant");
      if (aiMsg) {
        setDiagnosis(JSON.parse(aiMsg.content));
        // Switch to AI analysis view on mobile/tablet so the result is immediately seen
        setActiveMobileView("ai");
      }
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : "Analysis failed. Please try again.";
      setAnalysisError(msg);
      showToast(msg, "error");
      setActiveMobileView("ai");
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Select Historical Session
  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      if (!activeProject) return;
      setActiveSessionId(sessionId);
      setDiagnosis(null);
      setAnalysisError(null);
      setFeedback(null);

      try {
        const [sessionData, feedbackData] = await Promise.all([
          api.getSession(activeProject.id, sessionId),
          api.getFeedback(sessionId).catch(() => null),
        ]);

        const userMsg = sessionData.messages.find((m) => m.role === "user");
        if (userMsg) {
          const content = userMsg.content;
          const getSection = (marker: string) => {
            const start = content.indexOf(`[${marker}]`);
            if (start === -1) return "";
            const textStart = start + `[${marker}]\n`.length;
            const nextBracket = content.indexOf("\n\n[", textStart);
            return nextBracket === -1
              ? content.slice(textStart)
              : content.slice(textStart, nextBracket);
          };
          const sessionCode = getSection("firmware_code");
          if (sessionCode) {
            openTab(
              { id: `session:${sessionId}`, name: sessionData.title || "Session snapshot", kind: "session" },
              sessionCode
            );
          } else {
            stashActiveBuffer();
            setActiveTabId(null);
            setFirmwareCode("");
          }
          setSelectedFileId(null);
          setCompilerOutput(getSection("compiler_output"));
          setSerialLogs(getSection("serial_logs"));
        }

        const aiMsg = sessionData.messages.find((m) => m.role === "assistant");
        if (aiMsg) {
          setDiagnosis(JSON.parse(aiMsg.content));
          setActiveMobileView("ai");
        }

        setFeedback(feedbackData);
      } catch (e) {
        console.error("Failed to load session", e);
        showToast("Failed to load session", "error");
      }
    },
    [activeProject, api, showToast, openTab, stashActiveBuffer]
  );

  // Delete Session
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      if (!activeProject) return;
      try {
        await api.deleteSession(activeProject.id, sessionId);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
          setDiagnosis(null);
          setFeedback(null);
        }
        showToast("Session deleted", "success");
      } catch (e) {
        console.error("Failed to delete session", e);
        showToast("Failed to delete session", "error");
      }
    },
    [activeProject, api, activeSessionId, showToast]
  );

  // Submit Feedback
  const handleSubmitFeedback = useCallback(
    async (rating: number) => {
      if (!activeSessionId) return;
      try {
        const res = await api.submitFeedback(activeSessionId, rating);
        setFeedback(res);
        showToast("Feedback recorded", "success");
      } catch (e) {
        console.error("Failed to submit feedback", e);
        showToast("Failed to submit feedback", "error");
      }
    },
    [activeSessionId, api, showToast]
  );

  const problems = useMemo(() => problemsFromDiagnosis(diagnosis), [diagnosis]);
  const errorCount = problems.filter((p) => p.severity === "error").length;
  const warningCount = problems.filter((p) => p.severity === "warning").length;

  const handleSelectProblem = useCallback(
    (problem: Problem) => {
      if (typeof problem.line !== "number") return;
      const desktop = isDesktopViewport();
      if (problem.file) {
        const base = problem.file.replace(/\\/g, "/").split("/").pop();
        const match = tabs.find((t) => t.kind === "file" && t.name.split("/").pop() === base);
        if (match) activateTab(match.id);
      }
      if (!desktop) setActiveMobileView("code");
      // Wait for a possible tab switch / view change to render before moving the caret.
      setTimeout(() => {
        const editor = desktop ? desktopEditorRef.current : mobileEditorRef.current;
        editor?.revealPosition(problem.line!, problem.column ?? 1);
      }, 50);
    },
    [tabs, activateTab]
  );

  const showProblems = () => {
    setBottomTab("problems");
    setIsDiagnosticsCollapsed(false);
    if (!isDesktopViewport()) setActiveMobileView("diagnostics");
  };

  const canAnalyze = Boolean(
    firmwareCode.trim() || compilerOutput.trim() || serialLogs.trim()
  );
  const activeTab = displayTabs.find((t) => t.id === activeTabId);
  const aiStatus: AIStatus = isAnalyzing ? "analyzing" : analysisError ? "error" : diagnosis ? "complete" : "idle";
  const analysisInputs = {
    source: Boolean(firmwareCode.trim()),
    compiler: Boolean(compilerOutput.trim()),
    serial: Boolean(serialLogs.trim()),
  };

  const explorerProps = {
    files,
    selectedFileId,
    isUploading,
    onUpload: handleUpload,
    onDeleteFile: handleDeleteFile,
    sessions,
    activeSessionId,
    onDeleteSession: handleDeleteSession,
    projectName: activeProject?.name,
    openTabs: displayTabs,
    activeTabId,
    onCloseTab: closeTab,
  };

  const renderCodeWorkspace = (editorRef: React.Ref<CodeEditorHandle>) => (
    <CodeWorkspace
      value={firmwareCode}
      onChange={setFirmwareCode}
      tabs={displayTabs}
      activeTabId={activeTabId}
      onSelectTab={activateTab}
      onCloseTab={closeTab}
      onClear={() => setFirmwareCode("")}
      projectName={activeProject?.name}
      onCursorChange={setCursor}
      editorRef={editorRef}
    />
  );

  const renderDiagnostics = (collapsible: boolean) => (
    <DiagnosticTabs
      compilerOutput={compilerOutput}
      onCompilerChange={setCompilerOutput}
      serialLogs={serialLogs}
      onSerialChange={setSerialLogs}
      isCollapsed={collapsible ? isDiagnosticsCollapsed : false}
      onToggleCollapse={() => setIsDiagnosticsCollapsed(!isDiagnosticsCollapsed)}
      collapsible={collapsible}
      activeTab={bottomTab}
      onActiveTabChange={setBottomTab}
      problems={problems}
      hasDiagnosis={Boolean(diagnosis)}
      onSelectProblem={handleSelectProblem}
      className="h-full"
    />
  );

  const renderAIPanel = () => (
    <AIAnalysisPanel
      diagnosis={diagnosis}
      isAnalyzing={isAnalyzing}
      sessionId={activeSessionId}
      feedback={feedback}
      onSubmitFeedback={handleSubmitFeedback}
      error={analysisError}
      onRetry={handleAnalyze}
      inputs={analysisInputs}
    />
  );

  const mobileTabs = [
    {
      id: "code" as const,
      label: "Editor",
      icon: <Code2 className="h-3.5 w-3.5" />,
      indicator: firmwareCode.trim() ? "bg-foreground/60" : null,
    },
    {
      id: "diagnostics" as const,
      label: "Logs & Output",
      icon: <Terminal className="h-3.5 w-3.5" />,
      indicator: compilerOutput.trim() || serialLogs.trim() ? "bg-[var(--color-warning-amber)]" : null,
    },
    {
      id: "ai" as const,
      label: "AI Debug",
      icon: <Sparkles className="h-3.5 w-3.5 text-[var(--accent-purple)]" />,
      indicator: diagnosis ? "bg-[var(--color-success-green)]" : null,
    },
    {
      id: "files" as const,
      label: "Files",
      icon: <FolderOpen className="h-3.5 w-3.5" />,
      indicator: null,
    },
  ];

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-ide-bg">
      {/* 1. Toolbar */}
      <WorkspaceHeader
        sidebarOpen={sidebarOpen}
        mobileSidebarOpen={mobileSidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleMobileSidebar={() => setMobileSidebarOpen(!mobileSidebarOpen)}
        activeProject={activeProject}
        projects={projects}
        onSelectProject={handleSelectProject}
        onCreateProject={handleCreateProject}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        isAnalyzing={isAnalyzing}
        onAnalyze={handleAnalyze}
        canAnalyze={canAnalyze}
        hasDiagnosis={Boolean(diagnosis)}
      />

      {/* 2. Mobile / tablet Explorer drawer */}
      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent side="left" className="w-72 border-ide-border bg-ide-sidebar p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Explorer</SheetTitle>
          </SheetHeader>
          <ProjectFilesPanel
            {...explorerProps}
            onSelectFile={(id) => {
              handleSelectFile(id);
              setMobileSidebarOpen(false);
            }}
            onSelectTab={(id) => {
              activateTab(id);
              setActiveMobileView("code");
              setMobileSidebarOpen(false);
            }}
            onSelectSession={(id) => {
              handleSelectSession(id);
              setMobileSidebarOpen(false);
            }}
          />
        </SheetContent>
      </Sheet>

      {/* 3. Workbench */}
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {!activeProject && !loading ? (
          <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
            <FolderOpen className="mb-3 h-8 w-8 text-muted-foreground/60" />
            <h2 className="text-sm font-semibold text-foreground">No project selected</h2>
            <p className="mt-1 max-w-xs text-xs text-muted-foreground">
              Select an embedded firmware project from the toolbar, or create a new one.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4 min-h-11 lg:min-h-8 gap-1.5 rounded border-ide-border bg-transparent text-xs"
              onClick={handleCreateProject}
            >
              <Plus className="h-3.5 w-3.5" />
              Create Project
            </Button>
          </div>
        ) : (
          <>
            {/* Tablet & mobile (< lg): one primary view at a time */}
            <div className="flex min-w-0 flex-1 flex-col overflow-hidden lg:hidden">
              <div
                className="flex shrink-0 items-stretch overflow-x-auto border-b border-ide-border bg-ide-tabbar [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                role="tablist"
                aria-label="Workspace views"
              >
                {mobileTabs.map((tab) => {
                  const selected = activeMobileView === tab.id;
                  return (
                    <button
                      key={tab.id}
                      id={`tab-${tab.id}`}
                      type="button"
                      role="tab"
                      aria-selected={selected}
                      aria-controls={`tabpanel-${tab.id}`}
                      onClick={() => setActiveMobileView(tab.id)}
                      className={`relative flex min-h-11 min-w-[80px] flex-1 items-center justify-center gap-1.5 px-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/60 ${
                        selected ? "bg-ide-editor text-foreground" : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {selected && (
                        <span aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-[var(--accent-purple)]" />
                      )}
                      {tab.icon}
                      <span className="whitespace-nowrap">{tab.label}</span>
                      {tab.id === "files" && files.length + sessions.length > 0 ? (
                        <span
                          className="rounded-full bg-white/10 px-1.5 font-mono text-[10px] leading-4"
                          aria-label={`${files.length + sessions.length} items`}
                        >
                          {files.length + sessions.length}
                        </span>
                      ) : (
                        tab.indicator && (
                          <span className={`h-1.5 w-1.5 rounded-full ${tab.indicator}`} aria-hidden="true" />
                        )
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex min-h-0 flex-1 overflow-hidden">
                {activeMobileView === "code" && (
                  <div id="tabpanel-code" role="tabpanel" aria-labelledby="tab-code" className="flex min-w-0 flex-1 flex-col">
                    {renderCodeWorkspace(mobileEditorRef)}
                  </div>
                )}
                {activeMobileView === "diagnostics" && (
                  <div id="tabpanel-diagnostics" role="tabpanel" aria-labelledby="tab-diagnostics" className="flex min-w-0 flex-1 flex-col">
                    {renderDiagnostics(false)}
                  </div>
                )}
                {activeMobileView === "ai" && (
                  <div id="tabpanel-ai" role="tabpanel" aria-labelledby="tab-ai" className="flex min-w-0 flex-1 flex-col">
                    {renderAIPanel()}
                  </div>
                )}
                {activeMobileView === "files" && (
                  <div id="tabpanel-files" role="tabpanel" aria-labelledby="tab-files" className="flex min-w-0 flex-1 flex-col">
                    <ProjectFilesPanel
                      {...explorerProps}
                      onSelectFile={(id) => {
                        handleSelectFile(id);
                        setActiveMobileView("code");
                      }}
                      onSelectTab={(id) => {
                        activateTab(id);
                        setActiveMobileView("code");
                      }}
                      onSelectSession={(id) => {
                        handleSelectSession(id);
                        setActiveMobileView("ai");
                      }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Desktop (>= lg): Explorer | Editor | AI, with the panel spanning below */}
            <div className="hidden min-w-0 flex-1 flex-col overflow-hidden lg:flex">
              <div className="flex min-h-0 flex-1 overflow-hidden">
                {sidebarOpen && (
                  <aside aria-label="Explorer" className="flex w-60 xl:w-64 shrink-0 flex-col overflow-hidden border-r border-ide-border">
                    <ProjectFilesPanel
                      {...explorerProps}
                      onSelectFile={handleSelectFile}
                      onSelectTab={activateTab}
                      onSelectSession={handleSelectSession}
                    />
                  </aside>
                )}

                <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
                  {renderCodeWorkspace(desktopEditorRef)}
                </main>

                <aside
                  aria-label="AI debug"
                  className="flex w-[340px] xl:w-[380px] 2xl:w-[420px] shrink-0 flex-col overflow-hidden border-l border-ide-border"
                >
                  {renderAIPanel()}
                </aside>
              </div>

              <div
                className={`shrink-0 overflow-hidden border-t border-ide-border transition-[height] duration-200 motion-reduce:transition-none ${
                  isDiagnosticsCollapsed ? "h-9" : "h-52 xl:h-60"
                }`}
              >
                {renderDiagnostics(true)}
              </div>
            </div>
          </>
        )}
      </div>

      {/* 4. Status bar */}
      <StatusBar
        className="hidden sm:flex"
        aiStatus={aiStatus}
        projectName={activeProject?.name}
        errorCount={errorCount}
        warningCount={warningCount}
        onShowProblems={showProblems}
        cursor={cursor}
        tabSize={TAB_SIZE}
        lineEnding={detectLineEnding(firmwareCode)}
        languageLabel={activeTab?.kind === "file" ? getLanguageInfo(activeTab.name).label : "C/C++"}
      />

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
