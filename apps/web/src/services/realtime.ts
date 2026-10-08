import type { QueryClient } from "@tanstack/react-query";

import { getValidAuthToken } from "../lib/auth";
import { API_BASE_URL } from "./api";

export type RealtimeConnectionState = "CONNECTING" | "LIVE" | "RECONNECTING" | "OFFLINE";
export type RealtimeEventKind = "STATE_CHANGED" | "RESYNC_REQUIRED" | "HEARTBEAT";

export interface RealtimeStateEvent {
  event_kind: RealtimeEventKind;
  event_id: string;
  world_revision: number;
  occurred_at: string;
  event_type: string;
  domain: string;
  entity_type: string;
  entity_id: string;
  operation: string;
  invalidates: string[];
  conversation_id?: string | null;
  workspace_id?: string | null;
}

export interface RealtimeProcessResult {
  accepted: boolean;
  resyncRequired: boolean;
  invalidates: string[];
}

const REVISION_KEY = "life-os.last-world-revision";
const MAX_SEEN_EVENTS = 512;

const INVALIDATION_QUERY_KEYS: Record<string, string[]> = {
  inventory: ["inventory", "kitchen-status", "chef-recommendations", "meal-plans"],
  kitchen: ["kitchen-status", "inventory", "chef-recommendations", "meal-plans"],
  shopping_list: ["shopping-list", "shopping-needs"],
  shopping_needs: ["shopping-needs", "shopping-list"],
  finance_summary: ["finance-overview"],
  current_plan: ["current-plan"],
  calendar: ["calendar-projection"],
  plan_horizon: ["plan-horizon"],
  plan_proposals: ["plan-proposals"],
  attention_items: ["attention-items"],
  active_workspace: ["active-workspaces", "foreground-workspace"],
  global_workspace: ["global-workspace", "latest-state"],
  learning_status: ["learning-status", "exams"],
  fitness_status: ["fitness-status"],
  latest_state: ["latest-state"],
  goals: ["goals-overview"],
  personal_model: ["personal-model-summary", "personal-models", "personal-patterns"],
  conversations: ["assistant-threads"]
  , movies: ["movies"]
  , movie_watchlist: ["movie-watchlist"]
  , movie_history: ["movie-history"]
  , movie_recommendations: ["movie-recommendations"]
  , leisure_trajectory: ["leisure-trajectory"]
};

export class RealtimeRevisionTracker {
  private revision: number;
  private seenEventIds = new Set<string>();
  private seenOrder: string[] = [];

  constructor(initialRevision?: number) {
    const stored = typeof window !== "undefined" ? Number(window.localStorage.getItem(REVISION_KEY) ?? "0") : 0;
    this.revision = Math.max(0, initialRevision ?? (Number.isFinite(stored) ? stored : 0));
  }

  get currentRevision() {
    return this.revision;
  }

  process(event: RealtimeStateEvent): RealtimeProcessResult {
    if (event.event_kind === "HEARTBEAT") {
      return { accepted: false, resyncRequired: false, invalidates: [] };
    }
    if (event.event_kind === "RESYNC_REQUIRED") {
      if (this.seenEventIds.has(event.event_id)) {
        return { accepted: false, resyncRequired: false, invalidates: [] };
      }
      this.remember(event.event_id);
      this.revision = event.world_revision;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(REVISION_KEY, String(this.revision));
      }
      return { accepted: true, resyncRequired: true, invalidates: ["world"] };
    }
    if (this.seenEventIds.has(event.event_id) || event.world_revision <= this.revision) {
      return { accepted: false, resyncRequired: false, invalidates: [] };
    }
    const gap = event.world_revision > this.revision + 1;
    this.remember(event.event_id);
    this.revision = event.world_revision;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(REVISION_KEY, String(this.revision));
    }
    return {
      accepted: true,
      resyncRequired: gap,
      invalidates: gap ? ["world"] : event.invalidates
    };
  }

  private remember(eventId: string) {
    this.seenEventIds.add(eventId);
    this.seenOrder.push(eventId);
    if (this.seenOrder.length > MAX_SEEN_EVENTS) {
      const removed = this.seenOrder.shift();
      if (removed) this.seenEventIds.delete(removed);
    }
  }
}

export async function applyRealtimeEvent(
  queryClient: QueryClient,
  tracker: RealtimeRevisionTracker,
  event: RealtimeStateEvent
) {
  const result = tracker.process(event);
  if (!result.accepted) return result;
  if (result.resyncRequired || result.invalidates.includes("world")) {
    await queryClient.invalidateQueries();
    return result;
  }
  const keys = new Set<string>();
  for (const invalidation of result.invalidates) {
    if (invalidation.startsWith("conversation:")) {
      const conversationId = invalidation.slice("conversation:".length);
      keys.add("assistant-threads");
      await queryClient.invalidateQueries({ queryKey: ["assistant-thread", conversationId] });
      continue;
    }
    for (const key of INVALIDATION_QUERY_KEYS[invalidation] ?? []) keys.add(key);
  }
  await Promise.all([...keys].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
  return result;
}

type StateListener = (state: RealtimeConnectionState) => void;

export class RealtimeStateClient {
  private controller: AbortController | null = null;
  private stopped = true;
  private retryMs = 1000;
  private generation = 0;
  private readonly tracker = new RealtimeRevisionTracker();

  constructor(private readonly queryClient: QueryClient, private readonly onState: StateListener = () => undefined) {}

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    const generation = ++this.generation;
    void this.run(generation);
  }

  stop() {
    this.stopped = true;
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    this.onState("OFFLINE");
  }

  restart() {
    this.stop();
    this.start();
  }

  private async run(generation: number) {
    this.onState("CONNECTING");
    while (!this.stopped && generation === this.generation) {
      const token = await getValidAuthToken();
      if (!token) {
        this.onState("OFFLINE");
        await this.delay(1000);
        continue;
      }
      try {
        this.controller = new AbortController();
        const response = await fetch(
          `${API_BASE_URL}/api/v1/realtime/stream?after_revision=${this.tracker.currentRevision}`,
          {
            headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
            signal: this.controller.signal
          }
        );
        if (!response.ok || !response.body) throw new Error(`Realtime connection failed: ${response.status}`);
        this.onState("LIVE");
        this.retryMs = 1000;
        await this.consume(response.body, generation);
      } catch (error) {
        if (this.stopped || generation !== this.generation || (error instanceof DOMException && error.name === "AbortError")) return;
        this.onState("RECONNECTING");
        await this.delay(this.retryMs);
        this.retryMs = Math.min(this.retryMs * 2, 30_000);
      }
    }
  }

  private async consume(body: ReadableStream<Uint8Array>, generation: number) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!this.stopped && generation === this.generation) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");
        if (data) {
          const event = JSON.parse(data) as RealtimeStateEvent;
          await applyRealtimeEvent(this.queryClient, this.tracker, event);
        }
        boundary = buffer.indexOf("\n\n");
      }
    }
  }

  private delay(milliseconds: number) {
    return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
  }
}

let sharedClient: RealtimeStateClient | null = null;

export function getRealtimeStateClient(queryClient: QueryClient, onState?: StateListener) {
  if (!sharedClient) sharedClient = new RealtimeStateClient(queryClient, onState);
  return sharedClient;
}

export function resetRealtimeStateClientForTests() {
  sharedClient?.stop();
  sharedClient = null;
}
