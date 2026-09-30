export type EditorTab = {
  id: string;
  name: string;
  kind: "file" | "session" | "scratch";
  modified?: boolean;
};

export type LanguageInfo = {
  /** highlight.js language id */
  id: string;
  label: string;
};

export function getLanguageInfo(filename?: string | null): LanguageInfo {
  const ext = filename?.split(".").pop()?.toLowerCase() ?? "";
  switch (ext) {
    case "cpp":
    case "cc":
    case "cxx":
    case "hpp":
    case "hh":
      return { id: "cpp", label: "C++" };
    case "ino":
      return { id: "cpp", label: "Arduino" };
    case "h":
    case "c":
      return { id: "c", label: "C" };
    case "log":
    case "txt":
      return { id: "plaintext", label: "Plain Text" };
    default:
      return { id: "c", label: "C/C++" };
  }
}

export function detectLineEnding(text: string): "CRLF" | "LF" {
  return text.includes("\r\n") ? "CRLF" : "LF";
}
