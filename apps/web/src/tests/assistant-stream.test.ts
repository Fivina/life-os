import { describe, expect, it, vi } from "vitest";
import { consumeAssistantStream, parseAgentActivity } from "../services/assistantStream";

function makeStream(chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({ start(controller) { chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk))); controller.close(); } });
}

const response = { message: "done", role_used: "GENERAL_ASSISTANT", response_type: "INFORMATION", entity_references: [], request_id: "r1", model_tier: "STANDARD" } as const;

describe("assistant SSE stream", () => {
  it("handles CRLF and chunk boundaries", async () => {
    const onActivity = vi.fn();
    const result = await consumeAssistantStream(makeStream([
      "data: {\"event_type\":\"start\"}\r",
      "\n\r\ndata: {\"event_type\":\"activity\",\"activity\":{\"sequence\":1,\"kind\":\"tool\",\"skill_name\":\"chef\",\"tool_name\":null,\"status\":\"started\"}}\r\n\r\n",
      `data: {\"event_type\":\"complete\",\"response\":${JSON.stringify(response)}}\r\n\r\n`
    ]), onActivity);
    expect(onActivity).toHaveBeenCalledWith(expect.objectContaining({ sequence: 1 }));
    expect(result.message).toBe("done");
  });
  it("rejects a dropped stream", async () => {
    await expect(consumeAssistantStream(makeStream(["data: {\"event_type\":\"start\"}\n\n"]), () => undefined)).rejects.toThrow("ended before completion");
  });
  it("surfaces error events", async () => {
    await expect(consumeAssistantStream(makeStream(["data: {\"event_type\":\"error\",\"error_code\":\"provider_failed\"}\n\n"]), () => undefined)).rejects.toThrow("provider_failed");
  });
  it("rejects invalid or oversized activity without exposing extra payload", () => {
    const activity = { sequence: 1, kind: "tool", skill_name: "chef", tool_name: null, status: "started" };
    expect(parseAgentActivity({ ...activity, sequence: 0 })).toBeNull();
    expect(parseAgentActivity({ ...activity, tool_name: "x".repeat(121) })).toBeNull();
    expect(parseAgentActivity({ ...activity, arguments: "private" })).toEqual(activity);
  });
  it("rejects repeated sequence numbers", async () => {
    const activity = { sequence: 1, kind: "tool", skill_name: "chef", tool_name: null, status: "started" };
    const frame = `data: ${JSON.stringify({ event_type: "activity", activity })}\n\n`;
    await expect(consumeAssistantStream(makeStream([frame, frame]), vi.fn())).rejects.toThrow("invalid_activity");
  });
  it("bounds the number of activity records", async () => {
    const frames = Array.from({ length: 65 }, (_, index) => `data: ${JSON.stringify({ event_type: "activity", activity: { sequence: index + 1, kind: "model", skill_name: "self-core", tool_name: null, status: "started" } })}\n\n`);
    await expect(consumeAssistantStream(makeStream(frames), vi.fn())).rejects.toThrow("activity_limit");
  });
  it("rejects an oversized unterminated frame", async () => {
    await expect(consumeAssistantStream(makeStream(["x".repeat(1_048_577)]), vi.fn())).rejects.toThrow("frame_limit");
  });
  it("returns completion and cancels an otherwise open stream", async () => {
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify({ event_type: "complete", response })}\n\n`)); },
      cancel,
    });
    expect(await consumeAssistantStream(stream, vi.fn())).toEqual(response);
    expect(cancel).toHaveBeenCalledOnce();
  });
});
