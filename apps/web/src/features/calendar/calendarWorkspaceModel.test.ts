import { describe, expect, it } from "vitest";
import type { CalendarProjection, Plan } from "../../types/api";
import { addDays, calendarEvents, dayKey, eventsOnDay, shiftView, startOfWeek } from "./calendarWorkspaceModel";

describe("Calendar workspace model", () => {
  it("navigates local days, Monday-based weeks, and month ends", () => {
    const saturday = new Date(2026, 9, 31);
    expect(dayKey(startOfWeek(saturday))).toBe("2026-10-26");
    expect(dayKey(addDays(saturday, 1))).toBe("2026-11-01");
    expect(dayKey(shiftView(saturday, "day", -1))).toBe("2026-10-30");
    expect(dayKey(shiftView(saturday, "week", 1))).toBe("2026-11-07");
    expect(dayKey(shiftView(saturday, "month", 1))).toBe("2026-11-30");
  });

  it("uses source domains, avoids duplicate canonical commitments, and includes overnight events on both days", () => {
    const projection: CalendarProjection = { commitments: [{ canonical_id: "c1", canonical_type: "commitment", title: "Training", starts_at: "2026-10-03T22:00:00", ends_at: "2026-10-04T01:00:00", status: "active", level: "hard", commitment_type: "hard", location: "Gym", source: "fitness", version: 1 }], planning_pool: [], world_revision: 1 };
    const plan = { blocks: [
      { id: "copy", commitment_id: "c1", block_type: "hard_commitment", title: "Training", starts_at: "2026-10-03T22:00:00", ends_at: "2026-10-04T01:00:00", domain: "fitness", status: "planned" },
      { id: "study", commitment_id: null, block_type: "generated_action", title: "Study", starts_at: "2026-10-04T11:00:00", ends_at: "2026-10-04T12:00:00", domain: "learning", status: "planned" }
    ] } as Plan;
    const events = calendarEvents(projection, plan);
    expect(events).toHaveLength(2);
    expect(events.map(event => event.domain)).toEqual(["fitness", "learning"]);
    expect(eventsOnDay(events, new Date(2026, 9, 3)).map(event => event.title)).toEqual(["Training"]);
    expect(eventsOnDay(events, new Date(2026, 9, 4)).map(event => event.title)).toEqual(["Training", "Study"]);
  });
});
