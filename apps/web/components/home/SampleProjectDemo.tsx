import Link from "next/link";
import { ArrowRight, BookOpen, Bug, FileText, Terminal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SAMPLE_PROJECT as S } from "@/lib/sample-project";

/**
 * Static sample (Phase 8B). Renders hard-coded data only: no API calls, no
 * database writes, and it never appears in a user's project list.
 */
export function SampleProjectDemo() {
  return (
    <section
      id="demo"
      aria-labelledby="sample-project-heading"
      className="py-16 px-4 sm:px-6 max-w-7xl mx-auto border-t border-border/40"
    >
      <div className="flex flex-col lg:flex-row items-start justify-between gap-8">
        <div className="max-w-xl">
          <div className="flex items-center gap-2 mb-3">
            <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-white/40 text-white">
              Sample
            </Badge>
            <Badge
              variant="outline"
              className="text-[10px] border-[var(--color-emerald)]/40 text-[var(--color-emerald)]"
            >
              Static demo · not your data
            </Badge>
          </div>
          <h2
            id="sample-project-heading"
            className="text-2xl sm:text-3xl font-bold font-display tracking-tight text-foreground"
          >
            Sample project: {S.name}
          </h2>
          <p className="text-sm text-muted-foreground mt-2 leading-relaxed">
            A worked example of what a debug session looks like: a real-world bug, the datasheet
            section the answer leans on, and the fix. It is a fixed illustration on {S.board}: it
            is not saved to any account and does not appear in your projects.
          </p>

          <div className="lg-card mt-5 p-3 text-xs space-y-1.5">
            <p className="flex items-center gap-1.5 font-semibold text-foreground/90">
              <Bug className="lg-green h-3.5 w-3.5" /> The bug
            </p>
            <p className="text-muted-foreground">{S.bug.title}</p>
          </div>

          <div className="lg-card mt-3 p-3 text-xs space-y-1.5">
            <p className="flex items-center gap-1.5 font-semibold text-foreground/90">
              <BookOpen className="lg-white h-3.5 w-3.5" /> Datasheet reference
            </p>
            <p className="text-foreground/85">
              {S.datasheet.document}, {S.datasheet.section}
            </p>
            <blockquote className="border-l-2 border-[var(--color-emerald)]/50 pl-2 text-muted-foreground italic">
              {S.datasheet.excerpt}
            </blockquote>
            <p className="text-[10px] text-muted-foreground/70">{S.datasheet.note}</p>
          </div>

          <div className="mt-6 flex items-center gap-3">
            <Button variant="ai" size="sm" asChild>
              <Link href="/workspace">
                <span>Debug your own firmware</span>
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>

        <div className="lg-well w-full max-w-lg overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--color-code-border)] px-4 py-2.5 text-xs text-muted-foreground">
            <span className="font-mono flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" /> {S.bug.file}
            </span>
            <Badge variant="outline" className="text-[10px] border-white/40 text-white">
              Sample session
            </Badge>
          </div>
          <div className="p-4 font-mono text-[12px] leading-6 overflow-x-auto text-muted-foreground">
            <pre className="whitespace-pre text-foreground/80">{S.bug.code.join("\n")}</pre>

            <div className="mt-3 pt-2 border-t border-border/40">
              <p className="flex items-center gap-1.5 text-foreground/80">
                <Terminal className="h-3.5 w-3.5" /> Serial monitor
              </p>
              {S.bug.serialLog.map((line) => (
                <p key={line} className="text-muted-foreground">
                  {line}
                </p>
              ))}
            </div>

            <div className="mt-3 pt-2 border-t border-border/40 font-sans text-xs leading-5 space-y-2">
              <p className="font-semibold text-foreground/90">Session: {S.session.title}</p>
              <p className="text-muted-foreground">
                <span className="text-foreground/80">Root cause: </span>
                {S.session.rootCause}
              </p>
              <div className="font-mono text-[12px] leading-6">
                {S.session.fixDiff.map((line) => (
                  <p
                    key={line}
                    className={
                      line.startsWith("+")
                        ? "text-[var(--color-success-green)] font-semibold"
                        : "text-muted-foreground"
                    }
                  >
                    {line}
                  </p>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground/80">{S.session.confidence}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
