import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyRealtimeEvent,
  getRealtimeStateClient,
  RealtimeRevisionTracker,
  resetRealtimeStateClientForTests,
  type RealtimeStateEvent
} from "../services/realtime";


function event(revision: number, overrides: Partial<RealtimeStateEvent> = {}): RealtimeStateEvent {
  return {
    event_kind: "STATE_CHANGED",
    event_id: `event-${revision}`,
    world_revision: revision,
    occurred_at: "2026-09-26T10:00:00Z",
    event_type: "inventory.adjust",
    domain: "kitchen",
    entity_type: "inventory_item",
    entity_id: "item-1",
    operation: "UPDATE",
    invalidates: ["inventory"],
    ...overrides
  };
}


beforeEach(() => {
  window.localStorage.clear();
  resetRealtimeStateClientForTests();
});


describe("realtime revision coordination", () => {
  it("accepts ordered revisions and persists the recovery cursor", () => {
    const tracker = new RealtimeRevisionTracker(4);
    const result = tracker.process(event(5));
    expect(result).toEqual({ accepted: true, resyncRequired: false, invalidates: ["inventory"] });
    expect(tracker.currentRevision).toBe(5);
    expect(window.localStorage.getItem("life-os.last-world-revision")).toBe("5");
    expect(new RealtimeRevisionTracker().currentRevision).toBe(5);
  });

  it("deduplicates repeats and ignores stale or out-of-order delivery", () => {
    const tracker = new RealtimeRevisionTracker(10);
    expect(tracker.process(event(11)).accepted).toBe(true);
    expect(tracker.process(event(11)).accepted).toBe(false);
    expect(tracker.process(event(9, { event_id: "late" })).accepted).toBe(false);
    expect(tracker.currentRevision).toBe(11);
  });

  it("turns a revision gap or explicit resync event into a full refetch", async () => {
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
    const tracker = new RealtimeRevisionTracker(2);
    const result = await applyRealtimeEvent(queryClient, tracker, event(5));
    expect(result.resyncRequired).toBe(true);
    expect(invalidate).toHaveBeenCalledWith();

    const explicit = new RealtimeRevisionTracker(5);
    const explicitResult = explicit.process(event(2, { event_kind: "RESYNC_REQUIRED", invalidates: ["world"] }));
    expect(explicitResult.resyncRequired).toBe(true);
    expect(explicit.currentRevision).toBe(2);
  });

  it("maps semantic invalidations to canonical query keys", async () => {
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
    const tracker = new RealtimeRevisionTracker(0);
    await applyRealtimeEvent(
      queryClient,
      tracker,
      event(1, {
        event_type: "conversation.message.created",
        invalidates: ["conversations", "conversation:thread-1"],
        conversation_id: "thread-1"
      })
    );
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["assistant-threads"] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["assistant-thread", "thread-1"] });
  });

  it("keeps exactly one app-level realtime client", () => {
    const queryClient = new QueryClient();
    const first = getRealtimeStateClient(queryClient);
    const second = getRealtimeStateClient(queryClient);
    expect(second).toBe(first);
  });
});
