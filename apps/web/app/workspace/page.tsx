"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bug,
  ChevronDown,
  Code2,
  FileCode,
  FileTerminal,
  FolderOpen,
  Lightbulb,
  Loader2,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Terminal,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { UserButton } from "@clerk/nextjs";
import { useApiClient } from "@/lib/api-client";

export type Project = {
  id: string;
  name: string;
  description?: string;
  active?: boolean; // UI state
};

/* ────────────────────────────────────────────────────────────
   Constants — sample data
   ──────────────────────────────────────────────────────────── */

const FIRMWARE_LINES = [
  { num: 1, content: '#include "driver/gpio.h"', tokens: [{ type: "directive" as const, text: "#include" }, { type: "string" as const, text: ' "driver/gpio.h"' }] },
  { num: 2, content: '#include "freertos/FreeRTOS.h"', tokens: [{ type: "directive" as const, text: "#include" }, { type: "string" as const, text: ' "freertos/FreeRTOS.h"' }] },
  { num: 3, content: '#include "freertos/task.h"', tokens: [{ type: "directive" as const, text: "#include" }, { type: "string" as const, text: ' "freertos/task.h"' }] },
  { num: 4, content: "", tokens: [] },
  { num: 5, content: '#define LED_PIN 2', tokens: [{ type: "directive" as const, text: "#define" }, { type: "plain" as const, text: " LED_PIN " }, { type: "number" as const, text: "2" }] },
  { num: 6, content: '#define BLINK_PERIOD_MS 1000', tokens: [{ type: "directive" as const, text: "#define" }, { type: "plain" as const, text: " BLINK_PERIOD_MS " }, { type: "number" as const, text: "1000" }] },
  { num: 7, content: "", tokens: [] },
  { num: 8, content: "void app_main(void) {", tokens: [{ type: "keyword" as const, text: "void" }, { type: "function" as const, text: " app_main" }, { type: "plain" as const, text: "(void) {" }] },
  { num: 9, content: "    gpio_config_t cfg = {", tokens: [{ type: "plain" as const, text: "    gpio_config_t cfg = {" }] },
  { num: 10, content: "        .pin_bit_mask = GPIO_SEL_2,", tokens: [{ type: "plain" as const, text: "        .pin_bit_mask = " }, { type: "error" as const, text: "GPIO_SEL_2" }, { type: "plain" as const, text: "," }], error: true },
  { num: 11, content: "        .mode = GPIO_MODE_OUPUT,", tokens: [{ type: "plain" as const, text: "        .mode = " }, { type: "error" as const, text: "GPIO_MODE_OUPUT" }, { type: "plain" as const, text: "," }], error: true },
  { num: 12, content: "        .pull_up_en = GPIO_PULLUP_DISABLE,", tokens: [{ type: "plain" as const, text: "        .pull_up_en = GPIO_PULLUP_DISABLE," }] },
  { num: 13, content: "        .pull_down_en = GPIO_PULLDOWN_DISABLE,", tokens: [{ type: "plain" as const, text: "        .pull_down_en = GPIO_PULLDOWN_DISABLE," }] },
  { num: 14, content: "        .intr_type = GPIO_INTR_DISABLE,", tokens: [{ type: "plain" as const, text: "        .intr_type = GPIO_INTR_DISABLE," }] },
  { num: 15, content: "    };", tokens: [{ type: "plain" as const, text: "    };" }] },
  { num: 16, content: "    gpio_config(&cfg);", tokens: [{ type: "plain" as const, text: "    " }, { type: "function" as const, text: "gpio_config" }, { type: "plain" as const, text: "(&cfg);" }] },
  { num: 17, content: "", tokens: [] },
  { num: 18, content: "    while (1) {", tokens: [{ type: "plain" as const, text: "    " }, { type: "keyword" as const, text: "while" }, { type: "plain" as const, text: " (1) {" }] },
  { num: 19, content: "        gpio_set_level(LED_PIN, 1);", tokens: [{ type: "plain" as const, text: "        " }, { type: "function" as const, text: "gpio_set_level" }, { type: "plain" as const, text: "(LED_PIN, 1);" }] },
  { num: 20, content: "        vTaskDelay(BLINK_PERIOD_MS);", tokens: [{ type: "plain" as const, text: "        " }, { type: "function" as const, text: "vTaskDelay" }, { type: "plain" as const, text: "(BLINK_PERIOD_MS);" }] },
  { num: 21, content: "        gpio_set_level(LED_PIN, 0);", tokens: [{ type: "plain" as const, text: "        " }, { type: "function" as const, text: "gpio_set_level" }, { type: "plain" as const, text: "(LED_PIN, 0);" }] },
  { num: 22, content: "        vTaskDelay(BLINK_PERIOD_MS);", tokens: [{ type: "plain" as const, text: "        " }, { type: "function" as const, text: "vTaskDelay" }, { type: "plain" as const, text: "(BLINK_PERIOD_MS);" }] },
  { num: 23, content: "    }", tokens: [{ type: "plain" as const, text: "    }" }] },
  { num: 24, content: "}", tokens: [{ type: "plain" as const, text: "}" }] },
];

const COMPILER_OUTPUT = `$ idf.py build
Compiling main/main.c...

main/main.c:10:26: error: use of undeclared identifier 'GPIO_SEL_2'
        .pin_bit_mask = GPIO_SEL_2,
                        ^~~~~~~~~~
main/main.c:11:17: error: use of undeclared identifier 'GPIO_MODE_OUPUT'
        .mode = GPIO_MODE_OUPUT,
                ^~~~~~~~~~~~~~~
main/main.c:11:17: note: did you mean 'GPIO_MODE_OUTPUT'?

2 errors generated.
Build failed.`;

const SERIAL_LOG = `[0;32mI (325) cpu_start: Starting scheduler on PRO CPU.[0m
[0;32mI (0) cpu_start: Starting scheduler on APP CPU.[0m
[0;32mI (345) gpio: GPIO[2]| InputEn: 0| OutputEn: 1| OpenDrain: 0[0m
[0;31mE (346) gpio: gpio_set_level(226): GPIO output gpio_num error[0m
[0;31mE (1346) gpio: gpio_set_level(226): GPIO output gpio_num error[0m
[0;33mW (2347) task_wdt: Task watchdog got triggered.[0m
[0;31mE (2347) task_wdt: - IDLE0 (CPU 0)[0m
Guru Meditation Error: Core  0 panic'ed (LoadProhibited). Exception was unhandled.`;

/* ────────────────────────────────────────────────────────────
   Token color map
   ──────────────────────────────────────────────────────────── */

const TOKEN_COLORS: Record<string, string> = {
  directive: "text-[var(--color-info-blue)]",
  keyword: "text-[var(--color-info-blue)]",
  string: "text-[var(--color-warning-amber)]",
  function: "text-[var(--color-emerald)]",
  number: "text-[var(--color-warning-amber)]",
  error: "text-[var(--color-error-red)] underline underline-offset-2 decoration-[var(--color-error-red)]/40",
  plain: "text-foreground/80",
};

/* ────────────────────────────────────────────────────────────
   Application Header
   ──────────────────────────────────────────────────────────── */

function AppHeader({ 
  sidebarOpen, 
  onToggleSidebar, 
  activeProject 
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
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
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
        <Badge variant="outline" className="hidden border-[var(--color-emerald)]/30 text-[var(--color-emerald)] text-[10px] sm:inline-flex">
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
  onSelectProject 
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
      <nav className="flex-1 overflow-y-auto px-2 py-1.5" aria-label="Project list">
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
   Evidence Tabs
   ──────────────────────────────────────────────────────────── */

type EvidenceTab = "firmware" | "compiler" | "serial";

function EvidenceTabBar({ active, onTabChange }: { active: EvidenceTab; onTabChange: (tab: EvidenceTab) => void }) {
  const tabs: { id: EvidenceTab; label: string; icon: React.ElementType }[] = [
    { id: "firmware", label: "Firmware", icon: FileCode },
    { id: "compiler", label: "Compiler Output", icon: FileTerminal },
    { id: "serial", label: "Serial Logs", icon: Terminal },
  ];

  return (
    <div className="flex items-center border-b border-border/60 bg-[var(--color-code-bg)]" role="tablist" aria-label="Evidence tabs">
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

function FirmwarePanel() {
  return (
    <div className="flex-1 overflow-auto bg-[var(--color-code-bg)] font-mono text-[13px] leading-6">
      {/* File bar */}
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--color-code-border)] bg-[var(--color-code-bg)] px-4 py-1.5">
        <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">main/main.c</span>
        <Badge variant="outline" className="ml-auto border-[var(--color-error-red)]/40 text-[var(--color-error-red)] text-[10px]">
          2 errors
        </Badge>
      </div>

      {/* Code lines */}
      <div className="px-0 py-2">
        {FIRMWARE_LINES.map((line) => (
          <div
            key={line.num}
            className={`flex hover:bg-[var(--color-surface-overlay)]/30 ${
              line.error ? "bg-[var(--color-error-red)]/5" : ""
            }`}
          >
            {/* Line number gutter */}
            <span className="inline-block w-12 shrink-0 select-none pr-4 text-right text-muted-foreground/40">
              {line.num}
            </span>
            {/* Code content */}
            <span className="flex-1 pr-4">
              {line.tokens.length === 0 ? (
                <span>&nbsp;</span>
              ) : (
                line.tokens.map((token, i) => (
                  <span key={i} className={TOKEN_COLORS[token.type] || "text-foreground/80"}>
                    {token.text}
                  </span>
                ))
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Compiler Output Panel
   ──────────────────────────────────────────────────────────── */

function CompilerPanel() {
  return (
    <div className="flex-1 overflow-auto bg-[var(--color-code-bg)] p-4 font-mono text-[12px] leading-6">
      {COMPILER_OUTPUT.split("\n").map((line, i) => {
        let colorClass = "text-muted-foreground/70";
        if (line.includes("error:")) colorClass = "text-[var(--color-error-red)]";
        else if (line.includes("note:")) colorClass = "text-[var(--color-warning-amber)]";
        else if (line.includes("Build failed")) colorClass = "text-[var(--color-error-red)] font-semibold";
        else if (line.startsWith("$")) colorClass = "text-foreground/70";

        return (
          <p key={i} className={colorClass}>
            {line || "\u00A0"}
          </p>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Serial Log Panel
   ──────────────────────────────────────────────────────────── */

function SerialPanel() {
  return (
    <div className="flex-1 overflow-auto bg-[var(--color-code-bg)] p-4 font-mono text-[12px] leading-6">
      {SERIAL_LOG.split("\n").map((line, i) => {
        let colorClass = "text-muted-foreground/70";
        // Strip ANSI codes for display — color by content
        const clean = line.replace(/\[[\d;]*m/g, "");
        if (clean.includes("[0;31m") || line.includes("E (") || line.includes("Error") || line.includes("panic")) {
          colorClass = "text-[var(--color-error-red)]";
        } else if (clean.includes("[0;33m") || line.includes("W (")) {
          colorClass = "text-[var(--color-warning-amber)]";
        } else if (clean.includes("[0;32m") || line.includes("I (")) {
          colorClass = "text-[var(--color-success-green)]";
        }

        return (
          <p key={i} className={colorClass}>
            {clean || "\u00A0"}
          </p>
        );
      })}
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Diagnosis Panel — empty/awaiting state
   ──────────────────────────────────────────────────────────── */

function DiagnosisPanel() {
  return (
    <div className="flex flex-1 flex-col overflow-hidden border-t border-border/60 lg:border-t-0 lg:border-l">
      {/* Panel header */}
      <div className="flex items-center gap-2 border-b border-border/60 bg-[var(--color-code-bg)] px-4 py-2.5">
        <Zap className="h-3.5 w-3.5 text-[var(--color-emerald)]" />
        <span className="text-xs font-medium text-[var(--color-emerald)]">AI Diagnosis</span>
        <Badge variant="outline" className="ml-auto border-border/60 text-muted-foreground/60 text-[10px]">
          Awaiting analysis
        </Badge>
      </div>

      {/* Empty state */}
      <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-background/50 px-8 py-12 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-border/60 bg-[var(--color-surface-overlay)]">
          <Search className="h-6 w-6 text-muted-foreground/50" />
        </div>
        <div className="max-w-xs">
          <h3 className="text-sm font-semibold text-foreground">No analysis yet</h3>
          <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
            Click <span className="font-medium text-[var(--color-emerald)]">&quot;Analyze with AI&quot;</span> to send your
            firmware code, compiler output, and serial logs for evidence‑aware diagnosis.
          </p>
        </div>

        {/* Placeholder sections */}
        <div className="mt-4 w-full max-w-xs space-y-3">
          {[
            { icon: Lightbulb, label: "Diagnosis", desc: "Root cause analysis" },
            { icon: Code2, label: "Evidence", desc: "What the data shows" },
            { icon: Zap, label: "Suggested Fix", desc: "Corrected code & steps" },
          ].map((section) => (
            <div
              key={section.label}
              className="flex items-center gap-3 rounded-lg border border-dashed border-border/60 px-3 py-2.5"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-surface-overlay)]">
                <section.icon className="h-3.5 w-3.5 text-muted-foreground/40" />
              </div>
              <div className="text-left">
                <p className="text-xs font-medium text-muted-foreground/60">{section.label}</p>
                <p className="text-[10px] text-muted-foreground/40">{section.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────
   Main Area
   ──────────────────────────────────────────────────────────── */

function MainArea({ activeProject }: { activeProject?: Project }) {
  const [activeTab, setActiveTab] = useState<EvidenceTab>("firmware");

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
          <h1 className="text-sm font-semibold text-foreground">{activeProject.name}</h1>
          <Badge variant="secondary" className="text-[10px]">
            ESP-IDF v5.1
          </Badge>
        </div>

        <Button size="sm" className="gap-2 text-xs font-semibold" id="analyze-button">
          <Zap className="h-3.5 w-3.5" />
          Analyze with AI
        </Button>
      </div>

      {/* Content — split between evidence + diagnosis */}
      <div className="flex flex-1 flex-col overflow-hidden lg:flex-row">
        {/* Left — evidence input */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <EvidenceTabBar active={activeTab} onTabChange={setActiveTab} />

          {/* Tab panels */}
          <div className="flex flex-1 overflow-hidden" role="tabpanel">
            {activeTab === "firmware" && <FirmwarePanel />}
            {activeTab === "compiler" && <CompilerPanel />}
            {activeTab === "serial" && <SerialPanel />}
          </div>
        </div>

        {/* Right — diagnosis */}
        <DiagnosisPanel />
      </div>
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
      
      const updatedProjects = projects.map(p => ({ ...p, active: false }));
      newProject.active = true;
      setProjects([newProject, ...updatedProjects]);
    } catch (e) {
      console.error("Failed to create project", e);
    }
  };

  const handleSelectProject = (id: string) => {
    setProjects(projects.map(p => ({ ...p, active: p.id === id })));
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
