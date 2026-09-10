"use client";

import React, { useRef, useState } from "react";
import {
  Clock,
  FileCode,
  FileText,
  FolderOpen,
  History,
  Loader2,
  Trash2,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  type ProjectFileMetadata,
  type DebugSessionSummary,
} from "@/lib/api-client";

const CODE_EXTENSIONS = ".c,.cpp,.h,.hpp,.cc,.cxx,.ino";
const LOG_EXTENSIONS = ".log,.txt";
const ALL_EXTENSIONS = `${CODE_EXTENSIONS},${LOG_EXTENSIONS}`;

function fileIcon(fileType: string, filename: string) {
  if (fileType === "log") {
    return <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--accent-indigo)]" />;
  }
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "ino") {
    return <FileCode className="h-3.5 w-3.5 shrink-0 text-[var(--color-emerald)]" />;
  }
  return <FileCode className="h-3.5 w-3.5 shrink-0 text-[var(--accent-purple)]" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
  className = "",
}: ProjectFilesPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

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

  return (
    <div className={`flex flex-col h-full bg-[oklch(0.12_0.015_260/0.7)] backdrop-blur-md overflow-hidden ${className}`}>
      {/* 1. Project Files Section */}
      <div
        className={`flex flex-1 flex-col min-h-0 border-b border-border/40 transition-all duration-150 ${
          isDraggingOver ? "ring-1 ring-inset ring-[var(--accent-purple)]/50 bg-[var(--accent-purple)]/5" : ""
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 bg-card/40 border-b border-border/30">
          <div className="flex items-center gap-1.5 min-w-0">
            <FolderOpen className="h-3.5 w-3.5 text-[var(--accent-purple)] shrink-0" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground font-mono">
              Source &amp; Logs
            </span>
            {files.length > 0 && (
              <Badge variant="outline" className="text-[9px] px-1 py-0 h-3.5 font-mono text-muted-foreground border-border/50">
                {files.length}
              </Badge>
            )}
          </div>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-[var(--accent-purple)] hover:bg-[var(--accent-purple)]/10 rounded transition-all duration-150 active:scale-95"
                aria-label="Upload source file"
                disabled={isUploading}
                onClick={() => inputRef.current?.click()}
              >
                {isUploading ? (
                  <Loader2 className="h-3 w-3 animate-spin text-[var(--accent-purple)]" />
                ) : (
                  <Upload className="h-3 w-3" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">
              {isUploading ? "Uploading..." : "Upload source file or log"}
            </TooltipContent>
          </Tooltip>
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

        {/* Drag-over indicator */}
        {isDraggingOver && (
          <div className="mx-2 mt-2 flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-[var(--accent-purple)]/60 bg-[var(--accent-purple)]/5 py-2 text-[11px] text-[var(--accent-purple)] font-medium pointer-events-none">
            <Upload className="h-3 w-3" />
            <span>Drop to upload</span>
          </div>
        )}

        {/* File list */}
        <nav className="flex-1 overflow-y-auto p-1.5 space-y-0.5" aria-label="File list">
          {files.length === 0 && !isUploading && (
            <button
              type="button"
              className="group mt-2 flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/50 bg-card/20 px-3 py-5 text-center transition-all duration-150 hover:border-[var(--accent-purple)]/50 hover:bg-[var(--accent-purple)]/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-purple)]/50"
              onClick={() => inputRef.current?.click()}
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/5 border border-border/40 group-hover:border-[var(--accent-purple)]/40 text-muted-foreground group-hover:text-[var(--accent-purple)] transition-all duration-150">
                <Upload className="h-4 w-4" />
              </div>
              <span className="text-[11px] text-muted-foreground leading-snug">
                Upload firmware or logs<br />
                <span className="text-[9px] text-muted-foreground/60 font-mono">.c, .cpp, .ino, .log</span>
              </span>
            </button>
          )}

          {isUploading && (
            <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-muted-foreground bg-card/40 border border-[var(--accent-purple)]/20 animate-pulse">
              <Loader2 className="h-3 w-3 animate-spin text-[var(--accent-purple)]" />
              <span>Uploading file...</span>
            </div>
          )}

          {files.map((f) => {
            const isSelected = selectedFileId === f.id;
            return (
              <div
                key={f.id}
                className={`group flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-all duration-150 cursor-pointer border ${
                  isSelected
                    ? "bg-[var(--accent-purple)]/15 border-[var(--accent-purple)]/30 text-foreground font-medium shadow-sm"
                    : "border-transparent text-muted-foreground hover:bg-card/50 hover:text-foreground hover:border-border/30"
                }`}
                onClick={() => onSelectFile(f.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelectFile(f.id); }}
                aria-pressed={isSelected}
              >
                {fileIcon(f.file_type, f.filename)}
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-xs font-medium text-foreground/90 font-mono" title={f.filename}>
                    {f.filename}
                  </span>
                  <span className="text-[10px] text-muted-foreground/60 font-mono">
                    {formatSize(f.size_bytes)}
                  </span>
                </div>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="ml-auto flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground/40 hover:text-[var(--color-error-red)] hover:bg-[var(--color-error-red)]/10 opacity-0 group-hover:opacity-100 transition-all duration-150 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-error-red)]/50"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteFile(f.id);
                      }}
                      aria-label={`Delete ${f.filename}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right">Delete {f.filename}</TooltipContent>
                </Tooltip>
              </div>
            );
          })}
        </nav>
      </div>

      {/* 2. Debug Sessions History Section */}
      <div className="flex flex-1 flex-col min-h-0">
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 bg-card/40 border-b border-border/30">
          <div className="flex items-center gap-1.5 min-w-0">
            <History className="h-3.5 w-3.5 text-[var(--accent-indigo)] shrink-0" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground font-mono">
              Diagnostic History
            </span>
            {sessions.length > 0 && (
              <Badge variant="outline" className="text-[9px] px-1 py-0 h-3.5 font-mono text-muted-foreground border-border/50">
                {sessions.length}
              </Badge>
            )}
          </div>
        </div>

        {/* Sessions list */}
        <nav className="flex-1 overflow-y-auto p-1.5 space-y-0.5" aria-label="Session list">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-muted-foreground/50">
              No sessions recorded yet.
            </div>
          ) : (
            sessions.map((s) => {
              const isActive = activeSessionId === s.id;
              return (
                <div
                  key={s.id}
                  className={`group flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-all duration-150 cursor-pointer border ${
                    isActive
                      ? "bg-[var(--accent-purple)]/15 border-[var(--accent-purple)]/30 text-foreground font-medium shadow-sm"
                      : "border-transparent text-muted-foreground hover:bg-card/50 hover:text-foreground hover:border-border/30"
                  }`}
                  onClick={() => onSelectSession(s.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelectSession(s.id); }}
                  aria-pressed={isActive}
                >
                  <Clock className={`h-3 w-3 shrink-0 ${isActive ? "text-[var(--accent-purple)]" : "text-muted-foreground/60"}`} />
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-xs font-medium text-foreground/90" title={s.title}>
                      {s.title}
                    </span>
                    <span className="text-[9px] text-muted-foreground/60 font-mono">
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        className="ml-auto flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted-foreground/40 hover:text-[var(--color-error-red)] hover:bg-[var(--color-error-red)]/10 opacity-0 group-hover:opacity-100 transition-all duration-150 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-error-red)]/50"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteSession(s.id);
                        }}
                        aria-label={`Delete session ${s.title}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="right">Delete session</TooltipContent>
                  </Tooltip>
                </div>
              );
            })
          )}
        </nav>
      </div>
    </div>
  );
}
