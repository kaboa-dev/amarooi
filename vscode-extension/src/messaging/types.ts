export type WebviewCommand = "generate" | "preview" | "error";

export interface GenerateMessage {
  command: "generate";
  prompt: string;
  draft: string;
}

export interface PreviewMessage {
  command: "preview";
  draft: string;
}

export interface ErrorMessage {
  command: "error";
  error: string;
}

export type WebviewMessage = GenerateMessage | PreviewMessage | ErrorMessage;

export type ExtensionEvent = "preview" | "generated" | "error";

export interface ExtensionMessage {
  event: ExtensionEvent;
  content: string;
}

export function isWebviewMessage(value: unknown): value is WebviewMessage {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<WebviewMessage>;
  return candidate.command === "generate" || candidate.command === "preview" || candidate.command === "error";
}
