import { useState, useEffect, useCallback, useRef } from "react";
import type { DiagnosisResult } from "./types";
import { computeSimpleHash } from "@/lib/hash-utils";

export type DiffPreviewMode = "side-by-side" | "inline" | "single";

export type CodeDiffPreviewProps = {
  /** Original code shown in the left pane */
  originalCode: string;
  /** AI-suggested code fix shown in the right pane */
  suggestedCode: string;
  /** Filename displayed in the pane labels */
  filename: string;
  /** Programming language identifier */
  language?: string;
  /** Called when the user closes the preview */
  onClose?: () => void;
  /** Whether the preview is currently loading data */
  isLoading?: boolean;
  /** Error state message */
  error?: string | null;
  /** Whether this is a full-file replacement vs partial snippet (affects UI) */
  isFullFileReplacement?: boolean;
};

export type SuggestionMetadata = {
  filename: string;
  language: string;
};

/**
 * Props passed to useDiffPreviewState hook
 */
export type UseDiffPreviewStateProps = {
  /** The diagnosis result from AI analysis */
  diagnosis: DiagnosisResult | null;
  /** The currently active filename */
  activeFileName?: string;
};

/**
 * Return type for useDiffPreviewState hook
 */
export type UseDiffPreviewStateReturn = {
  /** Whether a valid diff suggestion is available */
  hasSuggestion: boolean;
  /** Props to pass to CodeDiffPreview, or null if no suggestion */
  diffPreviewProps: CodeDiffPreviewProps | null;
  /** Function to close the diff preview */
  closeDiffPreview: () => void;
  /** Whether the suggestion is a full-file replacement */
  isFullFileReplacement: boolean;
};

/**
 * Hook to extract and manage diff preview state from diagnosis results
 *
 * This hook determines if an AI diagnosis contains a code fix suggestion
 * and extracts the necessary data for the CodeDiffPreview component.
 *
 * Data flow:
 * 1. diagnosis.corrected_code - Full code replacement (preferred)
 * 2. diagnosis.proposed_fix - Snippet or description
 * 3. diagnosis.compiler_messages[].suggested_fix - Per-message fix
 */
export function useDiffPreviewState({
  diagnosis,
  activeFileName,
}: UseDiffPreviewStateProps): UseDiffPreviewStateReturn {
  const [diffPreviewProps, setDiffPreviewProps] =
    useState<CodeDiffPreviewProps | null>(null);

  // Extract language from filename
  const getLanguageFromFilename = (filename?: string): string => {
    if (!filename) return "c";
    const lowerName = filename.toLowerCase();
    if (lowerName.endsWith(".cpp") || lowerName.endsWith(".hpp") || lowerName.endsWith(".cc")) {
      return "cpp";
    }
    if (lowerName.endsWith(".c") || lowerName.endsWith(".h")) {
      return "c";
    }
    return "c";
  };

  // Track suggestion type
  const [isFullFileReplacement, setIsFullFileReplacement] = useState<boolean>(false);

  // Extract diff props from diagnosis
  useEffect(() => {
    if (!diagnosis) {
      setDiffPreviewProps(null);
      setIsFullFileReplacement(false);
      return;
    }

    let suggestedCode: string | null = null;
    let originalCode: string = "";
    let fullReplacement = false;
    const filename = activeFileName || "source.c";
    const language = getLanguageFromFilename(activeFileName);

    // Priority 1: corrected_code (full replacement)
    if (diagnosis.corrected_code?.trim()) {
      suggestedCode = diagnosis.corrected_code.trim();
      originalCode = diagnosis.problem_observed || "";
      fullReplacement = true;
    }
    // Priority 2: proposed_fix (may be snippet or description)
    else if (diagnosis.proposed_fix?.trim()) {
      suggestedCode = diagnosis.proposed_fix.trim();
      originalCode = diagnosis.problem_observed || "";
      fullReplacement = false;
    }
    // Priority 3: First compiler message with suggested_fix
    else {
      const messageWithFix = diagnosis.compiler_messages?.find(
        (msg) => msg.suggested_fix && msg.suggested_fix.trim()
      );
      if (messageWithFix) {
        suggestedCode = messageWithFix.suggested_fix!.trim();
        originalCode = diagnosis.problem_observed || "";
        fullReplacement = false;
      }
    }

    if (suggestedCode) {
      setDiffPreviewProps({
        originalCode,
        suggestedCode,
        filename,
        language,
        isFullFileReplacement: fullReplacement,
      });
      setIsFullFileReplacement(fullReplacement);
    } else {
      setDiffPreviewProps(null);
      setIsFullFileReplacement(false);
    }
  }, [diagnosis, activeFileName]);

  const closeDiffPreview = () => {
    setDiffPreviewProps(null);
  };

  const hasSuggestion = Boolean(diffPreviewProps);
  return { hasSuggestion, diffPreviewProps, closeDiffPreview, isFullFileReplacement };
}

// ============================================================================
// Phase 9.4: Code History Types and Hook
// ============================================================================

export type HistoryOperationType = "apply_fix" | "undo" | "redo" | "manual_edit" | "revert";

export interface HistoryEntry {
  id: string;
  timestamp: number;
  filename: string;
  contentHash: string;
  content: string;
  operation: HistoryOperationType;
  previousContentHash?: string; // Hash of content before this operation
  metadata?: {
    fixDescription?: string;
    isAIFix?: boolean;
  };
}

export interface FileHistory {
  filename: string;
  entries: HistoryEntry[];
  currentIndex: number; // Points to current state in entries array
}

export interface UseCodeHistoryProps {
  /** Initial code content */
  initialCode?: string;
  /** Filename for this history */
  filename: string;
  /** Maximum history entries to keep */
  maxHistorySize?: number;
}

export interface UseCodeHistoryReturn {
  /** Current code content */
  currentCode: string;
  /** Set current code (records history entry for manual edits) */
  setCode: (code: string, operation?: HistoryOperationType, metadata?: HistoryEntry["metadata"]) => void;
  /** Apply an AI fix - records both original and new state */
  applyFix: (suggestedCode: string, fixDescription?: string) => void;
  /** Undo last change */
  undo: () => string | null;
  /** Redo last undone change */
  redo: () => string | null;
  /** Revert to a specific history entry */
  revertTo: (entryId: string) => void;
  /** Force revert to original (before any AI fixes) */
  forceRevertToOriginal: () => void;
  /** Check if undo is available */
  canUndo: boolean;
  /** Check if redo is available */
  canRedo: boolean;
  /** Get all history entries */
  getHistory: () => HistoryEntry[];
  /** Check if current content differs from when fix was suggested (stale detection) */
  isStale: (suggestedCodeHash: string) => boolean;
  /** Clear history */
  clearHistory: () => void;
}

/**
 * Hook for managing per-file code history with undo/redo/revert capabilities
 * Uses content fingerprinting (SHA-256) for change detection
 */
export function useCodeHistory({
  initialCode = "",
  filename,
  maxHistorySize = 50,
}: UseCodeHistoryProps): UseCodeHistoryReturn {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const [currentCode, setCurrentCode] = useState<string>(initialCode);
  const initialCodeRef = useRef<string>(initialCode);
  const isInitializing = useRef(true);

  // Use the shared hash function from hash-utils for consistency
  const computeHash = useCallback((content: string): string => {
    return computeSimpleHash(content);
  }, []);

  // Generate unique ID for history entries
  const generateId = useCallback((): string => {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  // Initialize with initial code
  useEffect(() => {
    if (isInitializing.current && initialCode !== undefined) {
      const hash = computeHash(initialCode);
      const entry: HistoryEntry = {
        id: generateId(),
        timestamp: Date.now(),
        filename,
        contentHash: hash,
        content: initialCode,
        operation: "manual_edit",
        metadata: { isAIFix: false },
      };
      setEntries([entry]);
      setCurrentIndex(0);
      setCurrentCode(initialCode);
      initialCodeRef.current = initialCode;
      isInitializing.current = false;
    }
  }, [filename, initialCode, computeHash, generateId]);

  // Trim history to max size
  const trimHistory = useCallback((newEntries: HistoryEntry[], newIndex: number): { entries: HistoryEntry[]; index: number } => {
    if (newEntries.length <= maxHistorySize) {
      return { entries: newEntries, index: newIndex };
    }
    // Remove oldest entries, keeping the current index valid
    const removeCount = newEntries.length - maxHistorySize;
    const trimmedEntries = newEntries.slice(removeCount);
    const adjustedIndex = Math.max(0, newIndex - removeCount);
    return { entries: trimmedEntries, index: adjustedIndex };
  }, [maxHistorySize]);

  // Add a new history entry
  const addEntry = useCallback((
    content: string,
    operation: HistoryOperationType,
    metadata?: HistoryEntry["metadata"],
    previousContentHash?: string
  ) => {
    const hash = computeHash(content);
    const newEntry: HistoryEntry = {
      id: generateId(),
      timestamp: Date.now(),
      filename,
      contentHash: hash,
      content,
      operation,
      previousContentHash,
      metadata,
    };

    setEntries((prevEntries) => {
      // If we're not at the end, truncate future entries (redo stack)
      const truncatedEntries = prevEntries.slice(0, currentIndex + 1);
      const newEntries = [...truncatedEntries, newEntry];
      const { entries: trimmedEntries, index } = trimHistory(newEntries, newEntries.length - 1);
      setCurrentIndex(index);
      return trimmedEntries;
    });
    setCurrentCode(content);
  }, [computeHash, currentIndex, filename, generateId, trimHistory]);

  // Set code (for manual edits)
  const setCode = useCallback((
    code: string,
    operation: HistoryOperationType = "manual_edit",
    metadata?: HistoryEntry["metadata"]
  ) => {
    const previousHash = currentIndex >= 0 ? entries[currentIndex].contentHash : undefined;
    addEntry(code, operation, metadata, previousHash);
  }, [addEntry, currentIndex, entries]);

  // Apply an AI fix
  const applyFix = useCallback((
    suggestedCode: string,
    fixDescription?: string
  ) => {
    const previousHash = currentIndex >= 0 ? entries[currentIndex].contentHash : undefined;
    addEntry(suggestedCode, "apply_fix", {
      fixDescription,
      isAIFix: true,
    }, previousHash);
  }, [addEntry, currentIndex, entries]);

  // Undo last change
  const undo = useCallback((): string | null => {
    if (currentIndex <= 0) return null;
    const newIndex = currentIndex - 1;
    const previousEntry = entries[newIndex];
    setCurrentIndex(newIndex);
    setCurrentCode(previousEntry.content);
    return previousEntry.content;
  }, [currentIndex, entries]);

  // Redo last undone change
  const redo = useCallback((): string | null => {
    if (currentIndex >= entries.length - 1) return null;
    const newIndex = currentIndex + 1;
    const nextEntry = entries[newIndex];
    setCurrentIndex(newIndex);
    setCurrentCode(nextEntry.content);
    return nextEntry.content;
  }, [currentIndex, entries]);

  // Revert to a specific history entry
  const revertTo = useCallback((entryId: string) => {
    const entryIndex = entries.findIndex((e) => e.id === entryId);
    if (entryIndex === -1) return;
    const targetEntry = entries[entryIndex];
    // Add a new entry for the revert operation
    addEntry(targetEntry.content, "revert", {
      fixDescription: `Reverted to ${new Date(targetEntry.timestamp).toLocaleTimeString()}`,
    }, entries[currentIndex]?.contentHash);
  }, [addEntry, currentIndex, entries]);

  // Force revert to original (first entry)
  const forceRevertToOriginal = useCallback(() => {
    if (entries.length === 0) return;
    const originalEntry = entries[0];
    addEntry(originalEntry.content, "revert", {
      fixDescription: "Force reverted to original code",
    }, entries[currentIndex]?.contentHash);
  }, [addEntry, currentIndex, entries]);

  // Check if current content is stale compared to when fix was suggested
  const isStale = useCallback((suggestedCodeHash: string): boolean => {
    if (currentIndex < 0) return false;
    const currentHash = entries[currentIndex].contentHash;
    return currentHash !== suggestedCodeHash;
  }, [currentIndex, entries]);

  // Get all history entries
  const getHistory = useCallback((): HistoryEntry[] => {
    return [...entries];
  }, [entries]);

  // Clear history
  const clearHistory = useCallback(() => {
    const hash = computeHash(currentCode);
    const entry: HistoryEntry = {
      id: generateId(),
      timestamp: Date.now(),
      filename,
      contentHash: hash,
      content: currentCode,
      operation: "manual_edit",
      metadata: { isAIFix: false },
    };
    setEntries([entry]);
    setCurrentIndex(0);
  }, [computeHash, currentCode, filename, generateId]);

  return {
    currentCode,
    setCode,
    applyFix,
    undo,
    redo,
    revertTo,
    forceRevertToOriginal,
    canUndo: currentIndex > 0,
    canRedo: currentIndex < entries.length - 1,
    getHistory,
    isStale,
    clearHistory,
  };
}