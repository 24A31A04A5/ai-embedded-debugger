"use client";

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import hljs from "highlight.js";
import "highlight.js/styles/github-dark.css";

export type CursorPosition = {
  line: number;
  column: number;
  selected: number;
};

export interface CodeEditorHandle {
  focus: () => void;
  revealPosition: (line: number, column?: number) => void;
}

interface CodeEditorProps {
  value: string;
  onChange: (val: string) => void;
  language?: string;
  placeholder?: string;
  ariaLabel?: string;
  lineNumbers?: boolean;
  tabSize?: number;
  onCursorChange?: (pos: CursorPosition) => void;
  /** Changes whenever a different document is loaded into the editor. */
  documentKey?: string;
  className?: string;
}

const LINE_HEIGHT = 20;
const PAD_Y = 8;
const PAD_X = 14;
const MAX_HIGHLIGHT_CHARS = 250_000;

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function highlight(text: string, language: string) {
  if (text.length > MAX_HIGHLIGHT_CHARS || !hljs.getLanguage(language)) {
    return escapeHtml(text);
  }
  try {
    return hljs.highlight(text, { language, ignoreIllegals: true }).value;
  } catch {
    return escapeHtml(text);
  }
}

function visualColumn(lineText: string, tabSize: number) {
  let col = 0;
  for (const ch of lineText) {
    col = ch === "\t" ? col + tabSize - (col % tabSize) : col + 1;
  }
  return col;
}

export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor(
  {
    value,
    onChange,
    language = "c",
    placeholder = "",
    ariaLabel = "Code editor",
    lineNumbers = true,
    tabSize = 4,
    onCursorChange,
    documentKey,
    className = "",
  },
  ref
) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const gutterRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLSpanElement>(null);
  const charWidthRef = useRef(7.8);
  const tabMovesFocusRef = useRef(false);
  const lastCursorRef = useRef<CursorPosition>({ line: 1, column: 1, selected: 0 });
  const hintId = useId();

  const [activeLine, setActiveLine] = useState(1);
  const [focused, setFocused] = useState(false);

  // The DOM normalises CRLF to LF inside a textarea. Both layers must use the normalised text,
  // otherwise React sees a value mismatch on every render and resets the caret.
  const text = useMemo(() => value.replace(/\r\n?/g, "\n"), [value]);
  const lineCount = useMemo(() => {
    let n = 1;
    for (let i = 0; i < text.length; i++) if (text.charCodeAt(i) === 10) n++;
    return n;
  }, [text]);
  const html = useMemo(() => highlight(text, language), [text, language]);
  const gutterText = useMemo(
    () => Array.from({ length: lineCount }, (_, i) => i + 1).join("\n"),
    [lineCount]
  );
  const gutterDigits = Math.max(2, String(lineCount).length);

  useLayoutEffect(() => {
    const measure = () => {
      const el = measureRef.current;
      if (el) charWidthRef.current = el.getBoundingClientRect().width / 32 || charWidthRef.current;
    };
    measure();
    if (typeof document !== "undefined" && document.fonts) {
      document.fonts.ready.then(measure).catch(() => {});
    }
  }, []);

  const scrollCaretIntoView = useCallback((line: number, col: number) => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const top = PAD_Y + (line - 1) * LINE_HEIGHT;
    const bottom = top + LINE_HEIGHT;
    if (top < scroller.scrollTop) scroller.scrollTop = top;
    else if (bottom > scroller.scrollTop + scroller.clientHeight) {
      scroller.scrollTop = bottom - scroller.clientHeight + PAD_Y;
    }

    const gw = gutterRef.current?.offsetWidth ?? 0;
    const x = gw + PAD_X + col * charWidthRef.current;
    const visibleLeft = scroller.scrollLeft + gw;
    const visibleRight = scroller.scrollLeft + scroller.clientWidth;
    if (x < visibleLeft + PAD_X) scroller.scrollLeft = Math.max(0, x - gw - PAD_X * 2);
    else if (x > visibleRight - PAD_X) scroller.scrollLeft = x - scroller.clientWidth + PAD_X * 2;
  }, []);

  const reportCursor = useCallback(
    (reveal: boolean) => {
      const ta = textareaRef.current;
      if (!ta) return;
      const { selectionStart, selectionEnd, selectionDirection } = ta;
      const head = selectionDirection === "backward" ? selectionStart : selectionEnd;
      const before = ta.value.slice(0, head);
      const lineStart = before.lastIndexOf("\n") + 1;
      let line = 1;
      for (let i = 0; i < lineStart; i++) if (before.charCodeAt(i) === 10) line++;
      const col = visualColumn(before.slice(lineStart), tabSize);

      const selected = Math.abs(selectionEnd - selectionStart);
      const last = lastCursorRef.current;
      if (last.line !== line || last.column !== col + 1 || last.selected !== selected) {
        lastCursorRef.current = { line, column: col + 1, selected };
        setActiveLine(line);
        onCursorChange?.(lastCursorRef.current);
        if (reveal) scrollCaretIntoView(line, col);
      }
    },
    [onCursorChange, scrollCaretIntoView, tabSize]
  );

  useEffect(() => {
    const onSelectionChange = () => {
      if (document.activeElement === textareaRef.current) {
        setFocused(true);
        reportCursor(true);
      }
    };
    document.addEventListener("selectionchange", onSelectionChange);
    return () => document.removeEventListener("selectionchange", onSelectionChange);
  }, [reportCursor]);

  useImperativeHandle(
    ref,
    () => ({
      focus: () => textareaRef.current?.focus(),
      revealPosition: (line: number, column = 1) => {
        const ta = textareaRef.current;
        if (!ta) return;
        const lines = ta.value.split("\n");
        const targetLine = Math.min(Math.max(1, line), lines.length);
        const colIndex = Math.min(Math.max(0, column - 1), lines[targetLine - 1].length);
        let offset = colIndex;
        for (let i = 0; i < targetLine - 1; i++) offset += lines[i].length + 1;
        ta.focus({ preventScroll: true });
        ta.setSelectionRange(offset, offset);
        reportCursor(false);
        scrollCaretIntoView(targetLine, visualColumn(lines[targetLine - 1].slice(0, colIndex), tabSize));
      },
    }),
    [reportCursor, scrollCaretIntoView, tabSize]
  );

  // A new document starts at the top with the caret at 1:1.
  useEffect(() => {
    lastCursorRef.current = { line: 1, column: 1, selected: 0 };
    setActiveLine(1);
    onCursorChange?.(lastCursorRef.current);
    textareaRef.current?.setSelectionRange(0, 0);
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
      scrollRef.current.scrollLeft = 0;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentKey]);

  const insertAtSelection = (insert: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.focus();
    const ok = typeof document.execCommand === "function" && document.execCommand("insertText", false, insert);
    if (!ok) {
      ta.setRangeText(insert, ta.selectionStart, ta.selectionEnd, "end");
      onChange(ta.value);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Escape") {
      tabMovesFocusRef.current = true;
      return;
    }
    if (e.key === "Tab" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      if (tabMovesFocusRef.current) {
        tabMovesFocusRef.current = false;
        return;
      }
      e.preventDefault();
      const ta = e.currentTarget;
      const lineStart = ta.value.lastIndexOf("\n", ta.selectionStart - 1) + 1;
      const col = visualColumn(ta.value.slice(lineStart, ta.selectionStart), tabSize);
      insertAtSelection(" ".repeat(tabSize - (col % tabSize)));
      return;
    }
    tabMovesFocusRef.current = false;
  };

  const handleScroll = () => {
    // The textarea is sized to its content; any internal scroll would desync it from the display layer.
    const ta = textareaRef.current;
    if (ta && (ta.scrollTop !== 0 || ta.scrollLeft !== 0)) {
      ta.scrollTop = 0;
      ta.scrollLeft = 0;
    }
  };

  return (
    <div className={`relative flex-1 min-h-0 min-w-0 bg-ide-editor ${className}`}>
      <div ref={scrollRef} className="ide-scroll absolute inset-0 overflow-auto overscroll-contain">
        <div className="relative flex min-h-full w-max min-w-full">
          {lineNumbers && (
            <div
              ref={gutterRef}
              aria-hidden="true"
              className="sticky left-0 z-20 shrink-0 select-none border-r border-ide-border-subtle bg-ide-gutter"
            >
              <pre
                className="code-editor-layer relative text-muted-foreground/45"
                style={{
                  paddingLeft: 16,
                  paddingRight: 12,
                  paddingBottom: PAD_Y + LINE_HEIGHT * 4,
                  textAlign: "right",
                  minWidth: `calc(${gutterDigits}ch + 28px)`,
                }}
              >
                {gutterText}
              </pre>
              <span
                className="code-editor-layer pointer-events-none absolute right-0 text-right text-foreground/85"
                style={{
                  top: PAD_Y + (activeLine - 1) * LINE_HEIGHT,
                  padding: 0,
                  paddingRight: 12,
                  display: activeLine <= lineCount ? "block" : "none",
                }}
              >
                {activeLine}
              </span>
            </div>
          )}

          <div className="relative flex-1">
            {text.length > 0 && (
              <div
                aria-hidden="true"
                className={`pointer-events-none absolute left-0 right-0 ${
                  focused ? "bg-ide-active-line border-y border-white/[0.04]" : "bg-transparent"
                }`}
                style={{ top: PAD_Y + (activeLine - 1) * LINE_HEIGHT, height: LINE_HEIGHT }}
              />
            )}

            <pre
              aria-hidden="true"
              className="code-editor-layer pointer-events-none relative z-[1] text-[#d4d7dd]"
              style={{ paddingRight: PAD_X + 48, paddingBottom: PAD_Y + LINE_HEIGHT * 4 }}
            >
              <code
                className={`language-${language}`}
                dangerouslySetInnerHTML={{ __html: html + (text.endsWith("\n") || text === "" ? " " : "") }}
              />
            </pre>

            <textarea
              ref={textareaRef}
              className="code-editor-layer absolute inset-0 z-[2] h-full w-full resize-none overflow-hidden bg-transparent text-transparent caret-[#e6e6e6] outline-none placeholder:text-muted-foreground/40 selection:bg-[oklch(0.55_0.12_285/0.35)] selection:text-transparent"
              style={{ WebkitTextFillColor: "transparent" }}
              value={text}
              onChange={(e) => onChange(e.target.value)}
              onSelect={() => reportCursor(true)}
              onKeyUp={() => reportCursor(true)}
              onMouseUp={() => reportCursor(false)}
              onKeyDown={handleKeyDown}
              onScroll={handleScroll}
              onFocus={() => {
                setFocused(true);
                reportCursor(false);
              }}
              onBlur={() => {
                setFocused(false);
                tabMovesFocusRef.current = false;
              }}
              placeholder={placeholder}
              aria-label={ariaLabel}
              aria-describedby={hintId}
              aria-multiline="true"
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              autoComplete="off"
              data-gramm="false"
              data-enable-grammarly="false"
              wrap="off"
            />
          </div>
        </div>

        <span
          ref={measureRef}
          aria-hidden="true"
          className="code-editor-layer pointer-events-none invisible absolute left-0 top-0"
          style={{ padding: 0 }}
        >
          {"0".repeat(32)}
        </span>
      </div>

      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 z-30 transition-shadow duration-150 ${
          focused ? "shadow-[inset_0_0_0_1px_oklch(0.6_0.14_285/0.45)]" : ""
        }`}
      />

      <span id={hintId} className="sr-only">
        Tab inserts indentation. Press Escape, then Tab, to move focus out of the editor.
      </span>
    </div>
  );
});
