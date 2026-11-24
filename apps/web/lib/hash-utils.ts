/**
 * Content Fingerprinting Utilities
 * SHA-256 based content hashing for change detection and history tracking
 */

// Browser-compatible SHA-256 using Web Crypto API
export async function computeSHA256(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Synchronous fallback using simple hash (for non-critical uses)
export function computeSimpleHash(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    const char = input.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(16);
}

// Compute content fingerprint (async SHA-256 preferred)
export async function fingerprintContent(content: string): Promise<string> {
  try {
    return await computeSHA256(content);
  } catch {
    return computeSimpleHash(content);
  }
}

// Check if two content pieces are identical using fingerprint
export async function contentsEqual(contentA: string, contentB: string): Promise<boolean> {
  const hashA = await fingerprintContent(contentA);
  const hashB = await fingerprintContent(contentB);
  return hashA === hashB;
}

// Synchronous version for quick checks
export function contentsEqualSync(contentA: string, contentB: string): boolean {
  return computeSimpleHash(contentA) === computeSimpleHash(contentB);
}