import type { AgentWorkActivity, AssistantResponse } from "../types/api";

type StreamEvent = {
  event_type: string;
  activity?: unknown;
  response?: AssistantResponse;
  error_code?: string;
};

export function parseAgentActivity(value: unknown): AgentWorkActivity | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (
    !Number.isInteger(item.sequence) || Number(item.sequence) < 1 ||
    typeof item.skill_name !== "string" || !item.skill_name || item.skill_name.length > 80 ||
    !["model", "tool", "delegation", "routing"].includes(String(item.kind)) ||
    !["started", "completed", "failed", "awaiting_confirmation"].includes(String(item.status)) ||
    (item.tool_name !== null && (typeof item.tool_name !== "string" || item.tool_name.length > 120))
  ) return null;
  return {
    sequence: Number(item.sequence), kind: item.kind as AgentWorkActivity["kind"],
    skill_name: item.skill_name, tool_name: item.tool_name as string | null,
    status: item.status as AgentWorkActivity["status"],
  };
}

export async function consumeAssistantStream(
  body: ReadableStream<Uint8Array>, onActivity: (activity: AgentWorkActivity) => void,
): Promise<AssistantResponse> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let response: AssistantResponse | undefined;
  let activityCount = 0;
  let lastSequence = 0;
  let pendingCR = false;

  // A CRLF separator may span two network chunks.
  function append(text: string) {
    for (const char of text) {
      if (pendingCR) {
        buffer += "\n";
        pendingCR = false;
        if (char === "\n") continue;
      }
      if (char === "\r") pendingCR = true;
      else buffer += char;
    }
    if (buffer.length > 1_048_576) throw new Error("assistant_stream_frame_limit");
  }

  function consume(frame: string) {
    const data = frame.split("\n").filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart()).join("\n");
    if (!data) return;
    const event = JSON.parse(data) as StreamEvent;
    if (event.event_type === "activity") {
      if (++activityCount > 64) throw new Error("assistant_stream_activity_limit");
      const activity = parseAgentActivity(event.activity);
      if (!activity || activity.sequence <= lastSequence) throw new Error("assistant_stream_invalid_activity");
      lastSequence = activity.sequence;
      onActivity(activity);
    } else if (event.event_type === "complete") {
      if (!event.response || typeof event.response.message !== "string" || typeof event.response.request_id !== "string") {
        throw new Error("assistant_stream_invalid_completion");
      }
      response = event.response;
    } else if (event.event_type === "error") {
      throw new Error(event.error_code ?? "assistant_stream_error");
    }
  }

  try {
    while (true) {
      const { value, done } = await reader.read();
      append(decoder.decode(value, { stream: !done }));
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        consume(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (response) return response;
        boundary = buffer.indexOf("\n\n");
      }
      if (done) break;
    }
    if (pendingCR) buffer += "\n";
    if (buffer.trim()) consume(buffer);
    if (!response) throw new Error("Assistant stream ended before completion; reload the conversation before retrying.");
    return response;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
