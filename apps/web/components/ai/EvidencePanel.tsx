"use client";

import * as React from "react";
import { useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, FileCode, FileTerminal, FileText, Terminal } from "lucide-react";
import { type DocumentCitation } from "./types";

interface EvidencePanelProps {
  evidence: string[];
  citations?: DocumentCitation[] | null;
  groundedSummary?: string | null;
}

type EvidenceKind = "source" | "compiler" | "serial" | "other";

const KIND_META: Record<EvidenceKind, { label: string; icon: React.ReactNode }> = {
  source: { label: "Source", icon: <FileCode className="h-3.5 w-3.5 text-[oklch(0.70_0.12_250)]" /> },
  compiler: { label: "Compiler", icon: <FileTerminal className="h-3.5 w-3.5 text-[var(--color-warning-amber)]" /> },
  serial: { label: "Serial", icon: <Terminal className="h-3.5 w-3.5 text-[oklch(0.72_0.12_190)]" /> },
  other: { label: "Other signals", icon: <FileText className="h-3.5 w-3.5 text-muted-foreground" /> },
};

function classify(item: string): EvidenceKind {
  const lower = item.toLowerCase();
  if (/serial|uart|log|panic|backtrace|guru|watchdog|reset|boot/.test(lower)) return "serial";
  if (/compiler|gcc|clang|linker|error:|warning:|undefined reference|build/.test(lower)) return "compiler";
  if (/\.(c|h|cpp|hpp|ino)\b|line \d|source|function|variable|code/.test(lower)) return "source";
  return "other";
}

const COLLAPSE_THRESHOLD = 3;

function Group({
  label,
  icon,
  count,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full min-h-11 lg:min-h-7 items-center gap-1.5 rounded px-1 text-left text-xs font-medium text-foreground/85 hover:bg-ide-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-purple)]/60"
      >
        {open ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        {icon}
        <span className="flex-1">{label}</span>
        <span className="font-mono text-[10px] text-muted-foreground/70">{count}</span>
      </button>
      {open && <div className="ml-[18px] mt-0.5 space-y-1 border-l border-ide-border-subtle pl-3">{children}</div>}
    </div>
  );
}

function ShowMore({ hidden, onClick }: { hidden: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="min-h-11 lg:min-h-0 text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:underline"
    >
      Show {hidden} more
    </button>
  );
}

export function EvidencePanel({ evidence, citations, groundedSummary }: EvidencePanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const hasCitations = Boolean(citations && citations.length > 0);

  if ((!evidence || evidence.length === 0) && !hasCitations && !groundedSummary) return null;

  const grouped: Record<EvidenceKind, string[]> = { source: [], compiler: [], serial: [], other: [] };
  for (const item of evidence ?? []) grouped[classify(item)].push(item);

  const visible = <T,>(key: string, items: T[]) =>
    expanded[key] || items.length <= COLLAPSE_THRESHOLD + 1 ? items : items.slice(0, COLLAPSE_THRESHOLD);
  const expand = (key: string) => setExpanded((e) => ({ ...e, [key]: true }));

  return (
    <div className="space-y-1.5">
      {(Object.keys(grouped) as EvidenceKind[])
        .filter((k) => grouped[k].length > 0)
        .map((kind) => {
          const items = grouped[kind];
          const shown = visible(kind, items);
          return (
            <Group key={kind} label={KIND_META[kind].label} icon={KIND_META[kind].icon} count={items.length}>
              {shown.map((item, idx) => (
                <p key={idx} className="py-0.5 font-mono text-[11px] leading-relaxed text-foreground/80 [overflow-wrap:anywhere]">
                  {item}
                </p>
              ))}
              {shown.length < items.length && (
                <ShowMore hidden={items.length - shown.length} onClick={() => expand(kind)} />
              )}
            </Group>
          );
        })}

      {(hasCitations || groundedSummary) && (
        <Group
          label="Datasheet / RAG"
          icon={<BookOpen className="h-3.5 w-3.5 text-[var(--accent-purple)]" />}
          count={citations?.length ?? 0}
        >
          {groundedSummary && (
            <p className="py-0.5 text-[11px] leading-relaxed text-foreground/80">{groundedSummary}</p>
          )}
          {hasCitations &&
            visible("citations", citations!).map((cite, idx) => (
              <div key={cite.chunk_id || idx} className="space-y-1 py-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[11px] font-medium text-foreground/90" title={cite.document_name}>
                    {cite.document_name}
                  </span>
                  {typeof cite.page_number === "number" && (
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">p. {cite.page_number}</span>
                  )}
                </div>
                {cite.relevance_explanation && (
                  <p className="text-[11px] leading-relaxed text-muted-foreground">{cite.relevance_explanation}</p>
                )}
                {cite.relevant_snippet && (
                  <p className="line-clamp-3 rounded bg-black/25 px-2 py-1 font-mono text-[11px] text-foreground/75 [overflow-wrap:anywhere]">
                    {cite.relevant_snippet}
                  </p>
                )}
              </div>
            ))}
          {hasCitations && visible("citations", citations!).length < citations!.length && (
            <ShowMore
              hidden={citations!.length - visible("citations", citations!).length}
              onClick={() => expand("citations")}
            />
          )}
        </Group>
      )}
    </div>
  );
}
