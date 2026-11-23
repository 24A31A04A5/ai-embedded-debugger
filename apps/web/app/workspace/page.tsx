"use client";

import React, { useCallback, useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FolderOpen, Plus, X } from "lucide-react";

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
  type Project,
} from "@/components/workspace";
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
      className={`fixed bottom-4 left-4 right-4 sm:left-auto sm:right-4 z-50 flex items-center gap-2 rounded-xl border px-4 py-3 text-sm shadow-xl backdrop-blur-xl sm:max-w-md animate-in slide-in-from-bottom-4 ${
        type === "success"
          ? "border-[var(--color-emerald)]/40 bg-[oklch(0.16_0.02_270/0.9)] text-[var(--color-emerald)]"
          : "border-[var(--color-error-red)]/40 bg-[oklch(0.16_0.02_270/0.9)] text-[var(--color-error-red)]"
      }`}
    >
      {type === "success" ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--color-emerald)]" />
      ) : (
        <AlertCircle className="h-4 w-4 shrink-0 text-[var(--color-error-red)]" />
      )}
      <span className="min-w-0 flex-1 truncate text-xs sm:text-sm font-medium text-foreground">
        {message}
      </span>
      <button
        onClick={onClose}
        className="ml-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-white/5"
        aria-label="Close notification"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Workspace Page Root
   ──────────────────────────────────────────────────────────── */

export default function WorkspacePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isDiagnosticsCollapsed, setIsDiagnosticsCollapsed] = useState(false);

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  // Active Project Content State
  const [firmwareCode, setFirmwareCode] = useState("");
  const [compilerOutput, setCompilerOutput] = useState("");
  const [serialLogs, setSerialLogs] = useState("");
  const [activeFileName, setActiveFileName] = useState<string | undefined>(undefined);

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

  // Select file → populate editor or logs
  const handleSelectFile = useCallback(
    async (fileId: string) => {
      if (!activeProject) return;
      setSelectedFileId(fileId);

      try {
        const result = await api.getFileContent(activeProject.id, fileId);
        const { metadata, content } = result;

        if (metadata.file_type === "code") {
          setFirmwareCode(content);
          setActiveFileName(metadata.filename);
        } else {
          const looksLikeCompiler =
            /error:|warning:|undefined reference|linker|gcc|g\+\+/i.test(
              content.slice(0, 500)
            );
          if (looksLikeCompiler) {
            setCompilerOutput(content);
          } else {
            setSerialLogs(content);
          }
        }
      } catch (e) {
        console.error("Failed to load file content", e);
        showToast("Failed to load file content", "error");
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
      }
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : "Analysis failed. Please try again.";
      setAnalysisError(msg);
      showToast(msg, "error");
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
          setFirmwareCode(getSection("firmware_code"));
          setCompilerOutput(getSection("compiler_output"));
          setSerialLogs(getSection("serial_logs"));
        }

        const aiMsg = sessionData.messages.find((m) => m.role === "assistant");
        if (aiMsg) {
          setDiagnosis(JSON.parse(aiMsg.content));
        }

        setFeedback(feedbackData);
      } catch (e) {
        console.error("Failed to load session", e);
        showToast("Failed to load session", "error");
      }
    },
    [activeProject, api, showToast]
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

  const canAnalyze = Boolean(
    firmwareCode.trim() || compilerOutput.trim() || serialLogs.trim()
  );

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* 1. Workspace Header */}
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

      {/* 2. Mobile Drawer for Explorer */}
      <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
        <SheetContent
          side="left"
          className="w-80 p-0 bg-[oklch(0.10_0.015_260/0.98)] backdrop-blur-2xl border-border/50"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>Project Files &amp; Sessions</SheetTitle>
          </SheetHeader>
          <ProjectFilesPanel
            files={files}
            selectedFileId={selectedFileId}
            isUploading={isUploading}
            onUpload={handleUpload}
            onSelectFile={(id) => {
              handleSelectFile(id);
              setMobileSidebarOpen(false);
            }}
            onDeleteFile={handleDeleteFile}
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelectSession={(id) => {
              handleSelectSession(id);
              setMobileSidebarOpen(false);
            }}
            onDeleteSession={handleDeleteSession}
          />
        </SheetContent>
      </Sheet>

      {/* 3. Main Multi-Panel Workspace */}
      <div className="flex flex-1 overflow-hidden bg-[radial-gradient(circle_at_top,oklch(0.16_0.02_260)_0%,oklch(0.10_0.015_260)_48%,oklch(0.09_0.015_260)_100%)]">
        {!activeProject && !loading ? (
          <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-border/60 bg-card/60 text-muted-foreground shadow-sm mb-3">
              <FolderOpen className="h-6 w-6" />
            </div>
            <h2 className="text-base font-semibold text-foreground">
              No Project Selected
            </h2>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs">
              Select an existing embedded firmware project from the header or create a new one.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4 text-xs gap-1.5 border-border/60"
              onClick={handleCreateProject}
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create Project</span>
            </Button>
          </div>
        ) : (
          <div className="flex flex-1 overflow-hidden">
            {/* Explorer */}
            {sidebarOpen && (
              <aside className="hidden lg:flex w-72 shrink-0 flex-col border-r border-[oklch(0.30_0.015_260)] bg-[oklch(0.10_0.015_260/0.98)] overflow-hidden">
                <ProjectFilesPanel
                  files={files}
                  selectedFileId={selectedFileId}
                  isUploading={isUploading}
                  onUpload={handleUpload}
                  onSelectFile={handleSelectFile}
                  onDeleteFile={handleDeleteFile}
                  sessions={sessions}
                  activeSessionId={activeSessionId}
                  onSelectSession={handleSelectSession}
                  onDeleteSession={handleDeleteSession}
                  activeFileName={activeFileName}
                  compilerOutput={compilerOutput}
                  serialLogs={serialLogs}
                />
              </aside>
            )}

            <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
              <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_390px] xl:grid-cols-[minmax(0,1fr)_440px]">
                <div className="flex min-w-0 flex-1 flex-col overflow-hidden border-r border-[oklch(0.30_0.015_260)]">
                  <div className="flex-1 min-h-0 overflow-hidden border-b border-[oklch(0.30_0.015_260)] p-2 sm:p-3">
                    <CodeWorkspace
                      value={firmwareCode}
                      onChange={setFirmwareCode}
                      activeFileName={activeFileName}
                      onClear={() => setFirmwareCode("")}
                    />
                  </div>

                  <div
                    className={`border-t border-[oklch(0.30_0.015_260)] bg-[oklch(0.09_0.015_260/0.98)] transition-[height] duration-200 ${
                      isDiagnosticsCollapsed ? "h-10" : "h-60 xl:h-68"
                    }`}
                  >
                    <DiagnosticTabs
                      compilerOutput={compilerOutput}
                      onCompilerChange={setCompilerOutput}
                      serialLogs={serialLogs}
                      onSerialChange={setSerialLogs}
                      isCollapsed={isDiagnosticsCollapsed}
                      onToggleCollapse={() =>
                        setIsDiagnosticsCollapsed(!isDiagnosticsCollapsed)
                      }
                      className="h-full rounded-none border-0"
                    />
                  </div>
                </div>

                <div className="hidden lg:flex min-w-0 flex-col overflow-hidden border-l border-[var(--accent-purple)]/35 bg-[oklch(0.095_0.015_260)]">
                  <AIAnalysisPanel
                    diagnosis={diagnosis}
                    isAnalyzing={isAnalyzing}
                    sessionId={activeSessionId}
                    feedback={feedback}
                    onSubmitFeedback={handleSubmitFeedback}
                    error={analysisError}
                    onRetry={handleAnalyze}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4. Toast Notification */}
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
