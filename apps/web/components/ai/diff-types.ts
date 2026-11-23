import { useState, useEffect } from "react";
import type { DiagnosisResult } from "./types";

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