"use client";

import React, { useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Clock,
  FileCode,
  FileText,
  Folder,
  FolderOpen,
  History,
  Loader2,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  type ProjectFileMetadata,
  type DebugSessionSummary,
} from "@/lib/api-client";
import { type EditorTab } from "./editor-utils";

const CODE_EXTENSIONS = ".c,.cpp,.h,.hpp,.cc,.cxx,.ino";
const LOG_EXTENSIONS = ".log,.txt";
const ALL_EXTENSIONS = `${CODE_EXTENSIONS},${LOG_EXTENSIONS}`;

const ROW =
  "group flex w-full items-center gap-1.5 pr-1.5 text-left text-[13px] lg:text-xs min-h-11 lg:min-h-[22px] cursor-pointer select-none outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/70";
const ROW_IDLE = "text-foreground/80 hover:bg-ide-hover";
const ROW_SELECTED = "bg-ide-selected text-foreground";
const ROW_ACTION =
  "flex h-9 w-9 lg:h-5 lg:w-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-white/10 hover:text-foreground lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/60";

function fileIcon(fileType: string, filename: string) {
  if (fileType === "log") {
    return <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />;
  }
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "h" || ext === "hpp") {
    return <FileCode className="h-3.5 w-3.5 shrink-0 text-[oklch(0.72_0.12_300)]" />;
  }
  if (ext === "ino") {
    return <FileCode className="h-3.5 w-3.5 shrink-0 text-[oklch(0.72_0.12_190)]" />;
  }
  return <FileCode className="h-3.5 w-3.5 shrink-0 text-[oklch(0.70_0.12_250)]" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type FileGroup = { key: string; label: string; files: ProjectFileMetadata[] };

/** Groups by real directory when filenames carry a path, otherwise by file kind. */
function groupFiles(files: ProjectFileMetadata[]): FileGroup[] {
  const groups = new Map<string, FileGroup>();
  const add = (key: string, label: string, f: ProjectFileMetadata) => {
    if (!groups.has(key)) groups.set(key, { key, label, files: [] });
    groups.get(key)!.files.push(f);
  };
  for (const f of files) {
    const slash = f.filename.replace(/\\/g, "/").lastIndexOf("/");
    if (slash > 0) {
      const dir = f.filename.replace(/\\/g, "/").slice(0, slash);
      add(`dir:${dir}`, dir, f);
      continue;
    }
    const ext = f.filename.split(".").pop()?.toLowerCase();
    if (f.file_type === "log") add("kind:logs", "Logs", f);
    else if (ext === "h" || ext === "hpp") add("kind:headers", "Header files", f);
    else add("kind:sources", "Source files", f);
  }
  const order = ["kind:sources", "kind:headers", "kind:logs"];
  return Array.from(groups.values()).sort((a, b) => {
    const ia = order.indexOf(a.key);
    const ib = order.indexOf(b.key);
    if (ia === -1 && ib === -1) return a.label.localeCompare(b.label);
    if (ia === -1) return -1;
    if (ib === -1) return 1;
    return ia - ib;
  });
}

function baseName(filename: string) {
  const normalized = filename.replace(/\\/g, "/");
  return normalized.slice(normalized.lastIndexOf("/") + 1);
}

function SectionHeader({
  label,
  open,
  onToggle,
  count,
  actions,
}: {
  label: string;
  open: boolean;
  onToggle: () => void;
  count?: number;
  actions?: React.ReactNode;
}) {
  return (
    <div className="group sticky top-0 z-10 flex items-center border-t border-ide-border-subtle bg-ide-sidebar first:border-t-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex min-h-11 lg:min-h-[22px] min-w-0 flex-1 items-center gap-0.5 pl-1 text-left text-[11px] font-bold uppercase tracking-wide text-foreground/80 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[var(--accent-purple)]/70"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <span className="truncate">{label}</span>
        {typeof count === "number" && count > 0 && (
          <span className="ml-1.5 rounded-full bg-white/10 px-1.5 text-[10px] font-medium leading-4 text-muted-foreground">
            {count}
          </span>
        )}
      </button>
      {actions && <div className="flex items-center gap-0.5 pr-1.5">{actions}</div>}
    </div>
  );
}

interface ProjectFilesPanelProps {
  files: ProjectFileMetadata[];
  selectedFileId: string | null;
  isUploading: boolean;
  onUpload: (file: File) => void;
  onSelectFile: (fileId: string) => void;
  onDeleteFile: (fileId: string) => void;
  sessions: DebugSessionSummary[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  projectName?: string;
  openTabs?: EditorTab[];
  activeTabId?: string | null;
  onSelectTab?: (id: string) => void;
  onCloseTab?: (id: string) => void;
  className?: string;
}

export function ProjectFilesPanel({
  files,
  selectedFileId,
  isUploading,
  onUpload,
  onSelectFile,
  onDeleteFile,
  sessions,
  activeSessionId,
  onSelectSession,
  onDeleteSession,
  projectName,
  openTabs = [],
  activeTabId = null,
  onSelectTab,
  onCloseTab,
  className = "",
}: ProjectFilesPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [openSections, setOpenSections] = useState({ editors: true, project: true, history: true });
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const groups = useMemo(() => groupFiles(files), [files]);
  const toggleSection = (key: keyof typeof openSections) =>
    setOpenSections((s) => ({ ...s, [key]: !s[key] }));

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onUpload(file);
  };

  const uploadButton = (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="flex h-9 w-9 lg:h-5 lg:w-5 items-center justify-center rounded text-muted-foreground hover:bg-white/10 hover:text-foreground disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/60"
          aria-label="Upload source file or log"
          disabled={isUploading}
          onClick={() => inputRef.current?.click()}
        >
          {isUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{isUploading ? "Uploading…" : "Upload source file or log"}</TooltipContent>
    </Tooltip>
  );

  return (
    <div className={`flex h-full flex-col overflow-hidden bg-ide-sidebar ${className}`}>
      <div className="flex h-11 lg:h-9 shrink-0 items-center justify-between pl-4 pr-2">
        <h2 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Explorer</h2>
        {uploadButton}
        <input
          ref={inputRef}
          type="file"
          accept={ALL_EXTENSIONS}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
      </div>

      <div className="ide-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-2">
        {/* Open editors */}
        <SectionHeader
          label="Open Editors"
          open={openSections.editors}
          onToggle={() => toggleSection("editors")}
          count={openTabs.length}
        />
        {openSections.editors && (
          <ul aria-label="Open editors" className="py-0.5">
            {openTabs.length === 0 ? (
              <li className="px-6 py-1 text-xs text-muted-foreground/70">No open editors</li>
            ) : (
              openTabs.map((tab) => {
                const isActive = tab.id === activeTabId;
                return (
                  <li key={tab.id}>
                    <div className={`${ROW} pl-4 ${isActive ? ROW_SELECTED : ROW_IDLE}`}>
                      <button
                        type="button"
                        onClick={() => onSelectTab?.(tab.id)}
                        aria-current={isActive ? "true" : undefined}
                        className="flex min-w-0 flex-1 items-center gap-1.5 self-stretch text-left focus-visible:outline-none"
                      >
                        {tab.kind === "session" ? (
                          <History className="h-3.5 w-3.5 shrink-0 text-[var(--accent-purple)]/80" />
                        ) : (
                          fileIcon("code", tab.name)
                        )}
                        <span className="truncate font-mono">{tab.name}</span>
                        {tab.modified && (
                          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-foreground/60" aria-label="modified" />
                        )}
                      </button>
                      {onCloseTab && (
                        <button
                          type="button"
                          className={ROW_ACTION}
                          onClick={() => onCloseTab(tab.id)}
                          aria-label={`Close ${tab.name}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        )}

        {/* Project tree */}
        <div
          className={isDraggingOver ? "bg-[var(--accent-purple)]/5 ring-1 ring-inset ring-[var(--accent-purple)]/40" : ""}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <SectionHeader
            label={projectName || "Project"}
            open={openSections.project}
            onToggle={() => toggleSection("project")}
            count={files.length}
          />
          {openSections.project && (
            <nav aria-label="Project files" className="py-0.5">
              {isDraggingOver && (
                <div className="mx-2 my-1 flex items-center justify-center gap-1.5 rounded border border-dashed border-[var(--accent-purple)]/50 py-1.5 text-[11px] text-[oklch(0.80_0.10_290)] pointer-events-none">
                  <Upload className="h-3 w-3" />
                  Drop to upload
                </div>
              )}

              {isUploading && (
                <div className="flex items-center gap-2 px-6 py-1 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Uploading file…
                </div>
              )}

              {files.length === 0 && !isUploading && (
                <div className="px-4 py-2 text-xs text-muted-foreground">
                  <p>No files in this project yet.</p>
                  <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    className="mt-2 flex w-full min-h-11 lg:min-h-8 items-center justify-center gap-1.5 rounded border border-ide-border bg-white/[0.03] text-foreground/85 hover:bg-ide-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/60"
                  >
                    <Upload className="h-3.5 w-3.5" />
                    Upload file
                  </button>
                  <p className="mt-1.5 text-center font-mono text-[10px] text-muted-foreground/60">
                    .c .cpp .h .ino .log .txt — or drag &amp; drop
                  </p>
                </div>
              )}

              {groups.map((group) => {
                const collapsed = collapsedGroups[group.key];
                return (
                  <div key={group.key} role="group" aria-label={group.label}>
                    <button
                      type="button"
                      aria-expanded={!collapsed}
                      onClick={() => setCollapsedGroups((g) => ({ ...g, [group.key]: !g[group.key] }))}
                      className={`${ROW} pl-2 ${ROW_IDLE}`}
                    >
                      {collapsed ? (
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      )}
                      {collapsed ? (
                        <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      ) : (
                        <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      )}
                      <span className="truncate">{group.label}</span>
                      <span className="ml-auto pr-1 text-[10px] text-muted-foreground/60">{group.files.length}</span>
                    </button>

                    {!collapsed && (
                      <div className="relative">
                        <span aria-hidden="true" className="absolute bottom-0 left-[15px] top-0 w-px bg-ide-border-subtle" />
                        {group.files.map((f) => {
                          const isSelected = selectedFileId === f.id;
                          return (
                            <div
                              key={f.id}
                              role="button"
                              aria-pressed={isSelected}
                              aria-label={`Open ${f.filename}`}
                              tabIndex={0}
                              title={`${f.filename} · ${formatSize(f.size_bytes)} · updated ${new Date(f.updated_at).toLocaleString()}`}
                              onClick={() => onSelectFile(f.id)}
                              onKeyDown={(e) => {
                                if (e.target !== e.currentTarget) return;
                                if (e.key === "Enter" || e.key === " ") {
                                  e.preventDefault();
                                  onSelectFile(f.id);
                                } else if (e.key === "Delete") {
                                  e.preventDefault();
                                  onDeleteFile(f.id);
                                }
                              }}
                              className={`${ROW} pl-7 ${isSelected ? ROW_SELECTED : ROW_IDLE}`}
                            >
                              {fileIcon(f.file_type, f.filename)}
                              <span className="min-w-0 flex-1 truncate font-mono">{baseName(f.filename)}</span>
                              <span className="shrink-0 font-mono text-[10px] text-muted-foreground/60 lg:group-hover:hidden lg:group-focus-within:hidden">
                                {formatSize(f.size_bytes)}
                              </span>
                              <button
                                type="button"
                                className={`${ROW_ACTION} hover:!text-[var(--color-error-red)]`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onDeleteFile(f.id);
                                }}
                                aria-label={`Delete ${f.filename}`}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </nav>
          )}
        </div>

        {/* Diagnostic history */}
        <SectionHeader
          label="Diagnostic History"
          open={openSections.history}
          onToggle={() => toggleSection("history")}
          count={sessions.length}
        />
        {openSections.history && (
          <ul aria-label="Diagnostic sessions" className="py-0.5">
            {sessions.length === 0 ? (
              <li className="px-6 py-1 text-xs text-muted-foreground/70">No sessions recorded yet</li>
            ) : (
              sessions.map((s) => {
                const isActive = activeSessionId === s.id;
                return (
                  <li key={s.id}>
                    <div
                      role="button"
                      tabIndex={0}
                      aria-pressed={isActive}
                      title={`${s.title} · ${new Date(s.created_at).toLocaleString()}`}
                      onClick={() => onSelectSession(s.id)}
                      onKeyDown={(e) => {
                        if (e.target !== e.currentTarget) return;
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelectSession(s.id);
                        }
                      }}
                      className={`${ROW} pl-4 ${isActive ? ROW_SELECTED : ROW_IDLE}`}
                    >
                      <Clock
                        className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-[var(--accent-purple)]" : "text-muted-foreground"}`}
                      />
                      <span className="min-w-0 flex-1 truncate">{s.title}</span>
                      <span className="shrink-0 font-mono text-[10px] text-muted-foreground/60 lg:group-hover:hidden lg:group-focus-within:hidden">
                        {new Date(s.created_at).toLocaleDateString()}
                      </span>
                      <button
                        type="button"
                        className={`${ROW_ACTION} hover:!text-[var(--color-error-red)]`}
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(s.id);
                        }}
                        aria-label={`Delete session ${s.title}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
