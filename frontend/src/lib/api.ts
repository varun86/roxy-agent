import { ChatRequest, ChatResponse, ModelInfo } from "@/types/chat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

interface StreamHandlers {
  onStart?: () => void;
  onDelta: (delta: string) => void;
  onDone?: (payload: { text: string; trace: { steps: number; tool_calls: number; errors: number } }) => void;
  onError?: (error: string) => void;
}

export async function sendMessageStream(request: ChatRequest, handlers: StreamHandlers): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("ReadableStream is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const dataLine = rawEvent
        .split("\n")
        .find((line) => line.startsWith("data:"));

      if (!dataLine) {
        continue;
      }

      const payloadText = dataLine.slice(5).trim();
      if (!payloadText) {
        continue;
      }

      let payload: unknown;
      try {
        payload = JSON.parse(payloadText);
      } catch {
        continue;
      }

      if (!payload || typeof payload !== "object") {
        continue;
      }

      const event = payload as {
        type?: string;
        delta?: string;
        error?: string;
        text?: string;
        trace?: { steps: number; tool_calls: number; errors: number };
      };

      if (event.type === "start") {
        handlers.onStart?.();
      } else if (event.type === "delta" && typeof event.delta === "string") {
        handlers.onDelta(event.delta);
      } else if (event.type === "done" && typeof event.text === "string" && event.trace) {
        handlers.onDone?.({ text: event.text, trace: event.trace });
      } else if (event.type === "error") {
        handlers.onError?.(event.error ?? "Unknown stream error");
        throw new Error(event.error ?? "Unknown stream error");
      }
    }
  }
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const response = await fetch(`${API_BASE_URL}/models`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}