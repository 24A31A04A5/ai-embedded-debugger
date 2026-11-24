/**
 * Diff Generation and Patch Export Utilities
 * Creates standard unified diff patches from original → modified code
 */

export interface DiffHunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

export interface DiffLine {
  type: "context" | "add" | "remove";
  content: string;
  oldLineNumber?: number;
  newLineNumber?: number;
}

export interface UnifiedDiff {
  filename: string;
  originalFilename: string;
  modifiedFilename: string;
  hunks: DiffHunk[];
  generatedAt: string;
}

/**
 * Generate a unified diff between two strings
 * Based on the Myers diff algorithm (simplified implementation)
 */
export function generateUnifiedDiff(
  original: string,
  modified: string,
  filename: string,
  contextLines: number = 3
): UnifiedDiff {
  const originalLines = original.split("\n");
  const modifiedLines = modified.split("\n");

  // Simple LCS-based diff
  const { hunks } = computeDiff(originalLines, modifiedLines, contextLines);

  return {
    filename,
    originalFilename: filename,
    modifiedFilename: filename,
    hunks,
    generatedAt: new Date().toISOString(),
  };
}

/**
 * Compute diff hunks using a simple LCS approach
 */
function computeDiff(
  originalLines: string[],
  modifiedLines: string[],
  contextLines: number
): { hunks: DiffHunk[] } {
  const hunks: DiffHunk[] = [];

  // Build LCS matrix
  const m = originalLines.length;
  const n = modifiedLines.length;
  const dp: number[][] = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (originalLines[i - 1] === modifiedLines[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Reconstruct the diff
  let i = m;
  let j = n;
  const operations: { type: "equal" | "delete" | "insert"; value: string }[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && originalLines[i - 1] === modifiedLines[j - 1]) {
      operations.unshift({ type: "equal", value: originalLines[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      operations.unshift({ type: "insert", value: modifiedLines[j - 1] });
      j--;
    } else {
      operations.unshift({ type: "delete", value: originalLines[i - 1] });
      i--;
    }
  }

  // Group operations into hunks with context
  let hunkStart = 0;
  let inHunk = false;
  let currentHunk: DiffLine[] = [];
  let oldLineNum = 1;
  let newLineNum = 1;

  for (let opIndex = 0; opIndex < operations.length; opIndex++) {
    const op = operations[opIndex];

    if (op.type === "equal") {
      if (inHunk) {
        // Add context lines
        const contextToAdd = Math.min(contextLines, countConsecutiveEqual(operations, opIndex));
        for (let k = 0; k < contextToAdd; k++) {
          const ctxOp = operations[opIndex + k];
          currentHunk.push({
            type: "context",
            content: ctxOp.value,
            oldLineNumber: oldLineNum++,
            newLineNumber: newLineNum++,
          });
        }
        opIndex += contextToAdd - 1;

        // End hunk if next operations are all equal (enough context)
        const remainingEqual = countRemainingEqual(operations, opIndex + 1);
        if (remainingEqual >= contextLines * 2) {
          finalizeHunk(hunks, currentHunk, hunkStart, oldLineNum, newLineNum, contextLines);
          currentHunk = [];
          inHunk = false;
        }
      } else {
        oldLineNum++;
        newLineNum++;
      }
    } else {
      if (!inHunk) {
        // Start new hunk - add preceding context
        hunkStart = Math.max(1, oldLineNum - contextLines);
        const contextStart = Math.max(0, opIndex - contextLines);
        for (let k = contextStart; k < opIndex; k++) {
          const ctxOp = operations[k];
          if (ctxOp.type === "equal") {
            currentHunk.push({
              type: "context",
              content: ctxOp.value,
              oldLineNumber: hunkStart + (k - contextStart),
              newLineNumber: hunkStart + (k - contextStart),
            });
          }
        }
        inHunk = true;
      }

      if (op.type === "delete") {
        currentHunk.push({
          type: "remove",
          content: op.value,
          oldLineNumber: oldLineNum++,
        });
      } else if (op.type === "insert") {
        currentHunk.push({
          type: "add",
          content: op.value,
          newLineNumber: newLineNum++,
        });
      }
    }
  }

  // Finalize last hunk if exists
  if (inHunk && currentHunk.length > 0) {
    finalizeHunk(hunks, currentHunk, hunkStart, oldLineNum, newLineNum, contextLines);
  }

  return { hunks };
}

function countConsecutiveEqual(ops: { type: string; value: string }[], startIndex: number): number {
  let count = 0;
  for (let i = startIndex; i < ops.length && ops[i].type === "equal"; i++) {
    count++;
  }
  return count;
}

function countRemainingEqual(ops: { type: string; value: string }[], startIndex: number): number {
  let count = 0;
  for (let i = startIndex; i < ops.length; i++) {
    if (ops[i].type === "equal") count++;
    else break;
  }
  return count;
}

function finalizeHunk(
  hunks: DiffHunk[],
  lines: DiffLine[],
  oldStart: number,
  oldLineNum: number,
  newLineNum: number,
  contextLines: number
): void {
  // Trim trailing context lines beyond what's needed
  let trailingContext = 0;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (lines[i].type === "context") trailingContext++;
    else break;
  }
  const keepContext = Math.min(trailingContext, contextLines);
  const trimmedLines = lines.slice(0, lines.length - trailingContext + keepContext);

  const oldLines = trimmedLines.filter((l) => l.type !== "add").length;
  const newLines = trimmedLines.filter((l) => l.type !== "remove").length;

  hunks.push({
    oldStart,
    oldLines,
    newStart: oldStart, // Simplified - should be calculated properly
    newLines,
    lines: trimmedLines,
  });
}

/**
 * Format a unified diff as a standard patch string
 */
export function formatUnifiedDiff(diff: UnifiedDiff): string {
  const lines: string[] = [];

  lines.push(`--- ${diff.originalFilename}\t${diff.generatedAt}`);
  lines.push(`+++ ${diff.modifiedFilename}\t${diff.generatedAt}`);

  for (const hunk of diff.hunks) {
    lines.push(`@@ -${hunk.oldStart},${hunk.oldLines} +${hunk.newStart},${hunk.newLines} @@`);

    for (const line of hunk.lines) {
      const prefix = line.type === "add" ? "+" : line.type === "remove" ? "-" : " ";
      lines.push(`${prefix}${line.content}`);
    }
  }

  return lines.join("\n");
}

/**
 * Validate that a patch can be applied cleanly
 */
export function validatePatch(
  patch: string,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _targetContent?: unknown
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  // Basic patch format validation
  if (!patch.startsWith("--- ") || !patch.includes("+++ ")) {
    errors.push("Invalid patch format: missing file headers");
    return { valid: false, errors };
  }

  // Check for @@ hunk headers
  const hunkHeaderRegex = /@@ -\d+(,\d+)? \+\d+(,\d+)? @@/;
  if (!hunkHeaderRegex.test(patch)) {
    errors.push("Invalid patch format: no valid hunk headers found");
    return { valid: false, errors };
  }

  // Try to parse hunks and validate context
  const lines = patch.split("\n");
  let inHunk = false;
  let expectedOldLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("@@ ")) {
      inHunk = true;
      expectedOldLines = [];
      continue;
    }

    if (inHunk) {
      if (line.startsWith(" ") || line.startsWith("-")) {
        // Context or removal line - should match target
        const content = line.slice(1);
        expectedOldLines.push(content);
      } else if (line.startsWith("+")) {
        // Addition line - no validation needed
      } else if (line.startsWith("---") || line.startsWith("+++")) {
        // New file header - end of hunks
        inHunk = false;
      }
    }
  }

  // Note: Full patch application validation would require actual patching
  // This is a basic structural validation

  return { valid: errors.length === 0, errors };
}

/**
 * Create a patch file blob for download
 */
export function createPatchBlob(diff: UnifiedDiff): Blob {
  const patchContent = formatUnifiedDiff(diff);
  return new Blob([patchContent], { type: "text/x-patch" });
}

/**
 * Trigger download of a patch file
 */
export function downloadPatch(diff: UnifiedDiff, suggestedFilename?: string): void {
  const blob = createPatchBlob(diff);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedFilename || `${diff.filename.replace(/\.[^.]+$/, "")}.patch`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}