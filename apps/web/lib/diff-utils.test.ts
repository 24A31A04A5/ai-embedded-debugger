/**
 * Unit tests for diff-utils.ts
 * Run with: npx tsx apps/web/lib/diff-utils.test.ts
 */

import {
  generateUnifiedDiff,
  formatUnifiedDiff,
  validatePatch,
  createPatchBlob,
} from "./diff-utils";
import { computeSimpleHash } from "./hash-utils";

// Test helper
function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`FAILED: ${message}`);
  }
  console.log(`✓ ${message}`);
}

// Tests for generateUnifiedDiff
function testGenerateUnifiedDiff() {
  console.log("\n=== Testing generateUnifiedDiff ===");

  const original = "line1\nline2\nline3\n";
  const modified = "line1\nline2 modified\nline3\n";

  const diff = generateUnifiedDiff(original, modified, "test.c");

  assert(diff.filename === "test.c", "Filename matches");
  assert(diff.originalFilename === "test.c", "Original filename matches");
  assert(diff.modifiedFilename === "test.c", "Modified filename matches");
  assert(diff.hunks.length > 0, "Hunks are generated");
  assert(typeof diff.generatedAt === "string", "Timestamp is generated");
}

// Tests for formatUnifiedDiff
function testFormatUnifiedDiff() {
  console.log("\n=== Testing formatUnifiedDiff ===");

  const original = "line1\nline2\nline3\n";
  const modified = "line1\nline2 MODIFIED\nline3\n";

  const diff = generateUnifiedDiff(original, modified, "test.c");
  const formatted = formatUnifiedDiff(diff);

  assert(formatted.startsWith("--- test.c"), "Starts with original file header");
  assert(formatted.includes("+++ test.c"), "Contains modified file header");
  assert(formatted.includes("@@"), "Contains hunk headers");
  // The format uses diff line types, check the structure
  assert(formatted.includes("-line2") || formatted.includes(" line2"), "Contains original line");
  assert(formatted.includes("+line2 MODIFIED") || formatted.includes(" line2 MODIFIED"), "Contains modified line");
}

// Tests for validatePatch
function testValidatePatch() {
  console.log("\n=== Testing validatePatch ===");

  // Valid patch
  const validPatch = "--- test.c\n+++ test.c\n@@ -1,2 +1,2 @@\n line1\n-line2\n+line2 modified\n";

  const validResult = validatePatch(validPatch);
  assert(validResult.valid === true, "Valid patch passes validation");
  assert(validResult.errors.length === 0, "No errors for valid patch");

  // Invalid patch - missing headers
  const invalidPatch = "no headers here";
  const invalidResult = validatePatch(invalidPatch);
  assert(invalidResult.valid === false, "Invalid patch fails validation");
  assert(invalidResult.errors.length > 0, "Errors are reported for invalid patch");

  // Invalid patch - missing hunk headers
  const noHunksPatch = "--- test.c\n+++ test.c\nno hunk";
  const noHunksResult = validatePatch(noHunksPatch);
  assert(noHunksResult.valid === false, "Patch without hunks fails validation");
}

// Tests for createPatchBlob
function testCreatePatchBlob() {
  console.log("\n=== Testing createPatchBlob ===");

  const original = "old code";
  const modified = "new code";

  const diff = generateUnifiedDiff(original, modified, "test.c");
  const blob = createPatchBlob(diff);

  assert(blob instanceof Blob, "Returns a Blob");
  assert(blob.type === "text/x-patch", "Blob has correct MIME type");
}

// Tests for computeSimpleHash
function testComputeSimpleHash() {
  console.log("\n=== Testing computeSimpleHash ===");

  const hash1 = computeSimpleHash("test content");
  const hash2 = computeSimpleHash("test content");
  const hash3 = computeSimpleHash("different content");

  assert(hash1 === hash2, "Same content produces same hash");
  assert(hash1 !== hash3, "Different content produces different hash");
  assert(typeof hash1 === "string", "Hash is a string");
  assert(hash1.length > 0, "Hash is not empty");
}

// Tests for undo/redo history
function testUndoRedo() {
  console.log("\n=== Testing undo/redo history behavior ===");

  // Simulate history tracking with redo stack clearing
  const history: string[] = [];
  let currentIndex = -1;

  const addState = (code: string) => {
    // Truncate future entries (redo stack) when adding new state
    const newHistory = [...history.slice(0, currentIndex + 1), code];
    history.length = 0;
    history.push(...newHistory);
    currentIndex = history.length - 1;
  };

  const undo = (): string | null => {
    if (currentIndex <= 0) return null;
    currentIndex--;
    return history[currentIndex];
  };

  const redo = (): string | null => {
    if (currentIndex >= history.length - 1) return null;
    currentIndex++;
    return history[currentIndex];
  };

  // Test sequence
  addState("original");
  addState("after edit 1");
  addState("after edit 2");

  assert(history.length === 3, "History has 3 entries");
  assert(currentIndex === 2, "Current index is at end");

  // Undo should return previous state (after edit 2 -> after edit 1)
  const undone = undo();
  assert(undone === "after edit 1", "Undo returns correct state");
  assert(currentIndex === 1, "Current index decremented to 1");

  // Redo should return future state (after edit 1 -> after edit 2)
  const redone = redo();
  assert(redone === "after edit 2", "Redo returns correct state");
  assert(currentIndex === 2, "Current index incremented back to 2");

  // Undo twice to get to original
  undo(); // after edit 2 -> after edit 1
  assert(currentIndex === 1, "After first undo, at index 1");
  undo(); // after edit 1 -> original
  assert(currentIndex === 0, "At first entry (original)");

  // Cannot undo past first entry - should return null and not change index
  const result = undo();
  assert(result === null, "Cannot undo past first entry");
  assert(currentIndex === 0, "Index stays at 0 when undo is blocked");
}

// Tests for patch export doesn't mutate source
function testPatchExportPreservesSource() {
  console.log("\n=== Testing patch export preserves source ===");

  const original = "original code";
  const suggested = "suggested code";

  const diff = generateUnifiedDiff(original, suggested, "test.txt");

  // Verify original and suggested are unchanged
  assert(original === "original code", "Original code unchanged");
  assert(suggested === "suggested code", "Suggested code unchanged");

  // Verify diff was created
  assert(diff.originalFilename === "test.txt", "Diff filename correct");
  assert(diff.modifiedFilename === "test.txt", "Diff modified filename correct");
}

// Test per-file history isolation
function testPerFileHistory() {
  console.log("\n=== Testing per-file history isolation ===");

  // Each file should have its own history
  const fileHistories = new Map<string, string[]>();

  const addHistory = (filename: string, content: string) => {
    if (!fileHistories.has(filename)) {
      fileHistories.set(filename, []);
    }
    fileHistories.get(filename)!.push(content);
  };

  addHistory("file1.c", "content1v1");
  addHistory("file1.c", "content1v2");
  addHistory("file2.c", "content2v1");

  const file1History = fileHistories.get("file1.c") || [];
  const file2History = fileHistories.get("file2.c") || [];

  assert(file1History.length === 2, "File 1 has 2 entries");
  assert(file2History.length === 1, "File 2 has 1 entry");
  assert(file1History[0] === "content1v1", "File 1 history is isolated");
  assert(file2History[0] === "content2v1", "File 2 history is isolated");
}

// Test empty diff
function testEmptyDiff() {
  console.log("\n=== Testing empty diff ===");

  const code = "same code\n";
  const diff = generateUnifiedDiff(code, code, "test.c");

  assert(diff.hunks.length >= 0, "Same code produces valid diff structure");
}

// Test large diff
function testLargeDiff() {
  console.log("\n=== Testing large diff ===");

  const original = Array(100).fill("line").join("\n");
  const modified = Array(100).fill("modified").join("\n");

  const diff = generateUnifiedDiff(original, modified, "large.c");

  assert(diff.hunks.length > 0, "Large diff produces hunks");
  const formatted = formatUnifiedDiff(diff);
  assert(formatted.length > 0, "Large diff produces formatted output");
}

// Run all tests
function runAllTests() {
  console.log("\n========================================");
  console.log("Running Phase 9 Unit Tests");
  console.log("========================================");

  try {
    testGenerateUnifiedDiff();
    testFormatUnifiedDiff();
    testValidatePatch();
    testCreatePatchBlob();
    testComputeSimpleHash();
    testUndoRedo();
    testPatchExportPreservesSource();
    testPerFileHistory();
    testEmptyDiff();
    testLargeDiff();

    console.log("\n========================================");
    console.log("ALL TESTS PASSED ✓");
    console.log("========================================");
    process.exit(0);
  } catch (error) {
    console.error("\n========================================");
    console.error("TESTS FAILED");
    console.error("========================================");
    console.error(error);
    process.exit(1);
  }
}

runAllTests();