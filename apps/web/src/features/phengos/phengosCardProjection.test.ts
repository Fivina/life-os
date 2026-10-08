import { expect, it } from "vitest";
import type { AssistantActionProposal, CalendarProjection, FitnessStatus, FixtureBinding, MealPlan, ShoppingAggregate, StandingCalendarRule } from "../../types/api";
import { fixtureSourcesForRules, projectPhengosCards } from "./phengosCardProjection";

it("prioritizes today's saved work and does not duplicate a planned commitment", () => {
  const now = new Date(2026, 9, 3, 9, 0);
  const at = (hour: number) => new Date(2026, 9, 3, hour, 0).toISOString();
  const calendar = {
    commitments: [
      { canonical_id: "meeting-1", title: "Meet Deniz", starts_at: at(15), ends_at: at(16), status: "scheduled", level: "hard" },
      { canonical_id: "meeting-2", title: "Project sync", starts_at: at(17), ends_at: at(18), status: "scheduled", level: "hard" },
    ],
    current_plan: { id: "plan-1", blocks: [
      { id: "block-1", title: "Gym", domain: "fitness", starts_at: at(10), ends_at: at(11), duration_minutes: 60, block_type: "generated_action", status: "planned" },
      { id: "block-2", title: "Meet Deniz", domain: "social", commitment_id: "meeting-1", starts_at: at(15), ends_at: at(16), duration_minutes: 60, block_type: "hard_commitment", status: "planned" },
    ] },
  } as unknown as CalendarProjection;
  const fitness = { active_session: null, next_workout: { id: "upper-a", name: "Upper A", estimated_duration_minutes: 60 } } as FitnessStatus;
  const shopping = [{ ingredient_name: "Milk", quantity: 2, unit: "l", priority_class: "required", source_item_ids: ["milk-1"], status: "open" }] as ShoppingAggregate[];
  const meals = [{ id: "meal-1", status: "selected", planned_for: at(19), recipe: { name: "Pasta", preparation_minutes: 10, cooking_minutes: 20 } }] as MealPlan[];

  const cards = projectPhengosCards({ calendar, fitness, shopping, meals }, now);
  expect(cards[0].kind).toBe("commitment");
  expect(cards.find(card => card.kind === "workout")?.eyebrow).toBe("TRAINING TODAY");
  expect(cards.find(card => card.kind === "workout")?.action).toBeUndefined();
  expect(cards.find(card => card.kind === "shopping")?.items?.[0].sourceId).toBe("milk-1");
  expect(cards.find(card => card.kind === "meal")?.title).toBe("Pasta");
  expect(cards.filter(card => card.title === "Meet Deniz")).toHaveLength(0);
  expect(cards.find(card => card.title === "Project sync")).toBeDefined();
});

it("shows one nearest future fixture regardless of provider order and keeps safe club logo URLs", () => {
  const now = new Date(2026, 9, 3, 9, 0);
  const fixture = (id: string, hours: number, homeLogo: string): FixtureBinding => ({
    id, commitment_id: id === "soon" ? "commitment/id with spaces" : null, fixture_status: "SCHEDULED", suppressed: false,
    kickoff_at: new Date(now.getTime() + hours * 60 * 60_000).toISOString(),
    normalized_json: { home_team: "Beşiktaş", away_team: "Fenerbahçe", home_team_logo_url: homeLogo },
  } as unknown as FixtureBinding);
  const cards = projectPhengosCards({ fixtures: [fixture("late", 49, "javascript:alert(1)"), fixture("soon", 47, "https://example.org/besiktas.png")] }, now);
  expect(cards).toHaveLength(1);
  expect(cards[0].title).toBe("Beşiktaş vs Fenerbahçe");
  expect(cards[0].fixture?.homeLogo).toBe("https://example.org/besiktas.png");
  expect(cards[0].href).toBe("/calendar?commitment=commitment%2Fid%20with%20spaces");
  expect(cards[0].size).toBe("compact");
  const distant = projectPhengosCards({ fixtures: [fixture("distant", 24 * 30, "javascript:alert(1)")] }, now);
  expect(distant).toHaveLength(1);
  expect(distant[0].fixture?.homeLogo).toBeUndefined();
  expect(distant[0].priority).toBeLessThan(cards[0].priority);
  expect(distant[0].href).toBe("/calendar");
});

it("uses an authoritative empty next selection without deleting cached Calendar data", () => {
  const cached = [{ id: "cached", source_fixture_id: "9001" }] as FixtureBinding[];
  const rule = { next_fixture_selection_known: true, current_next_fixture_id: null } as StandingCalendarRule;
  expect(fixtureSourcesForRules([rule], [cached]).fixtures).toEqual([]);
  expect(cached).toHaveLength(1);
  expect(fixtureSourcesForRules([{ ...rule, current_next_fixture_id: "9001" }], [cached]).fixtures).toEqual(cached);
  expect(fixtureSourcesForRules([{ ...rule, next_fixture_selection_known: false }], [cached]).fixtures).toEqual(cached);
});

it("keeps the next match visible when higher-priority cards fill the dashboard", () => {
  const now = new Date(2026, 9, 3, 9);
  const proposals = Array.from({ length: 9 }, (_, index) => ({ id: `p${index}`, thread_id: "thread",
    summary: "Pending review", tool_name: "plan_create", arguments: {}, status: "pending",
    expires_at: new Date(now.getTime() + 600_000).toISOString(), consequence_category: "consequential",
    confirmation_required: true, version: 1 } satisfies AssistantActionProposal));
  const fixture = { id: "distant", commitment_id: "match", fixture_status: "SCHEDULED", suppressed: false,
    source_provider: "api_football", source_fixture_id: "distant", protection_overridden: false, version: 1,
    kickoff_at: new Date(now.getTime() + 30 * 24 * 60 * 60_000).toISOString(),
    normalized_json: { home_team: "Beşiktaş", away_team: "Opponent", raw_status: "NS" } } as FixtureBinding;
  const cards = projectPhengosCards({ proposals, fixtures: [fixture] }, now);
  expect(cards).toHaveLength(8);
  expect(cards.filter(card => card.kind === "fixture")).toHaveLength(1);
  expect(cards[0].kind).toBe("proposal");
});

it("shows unconfirmed kickoff only for the provider-selected next match", () => {
  const unknown = { id: "tbd", source_fixture_id: "9002", fixture_status: "SCHEDULED", suppressed: false,
    source_provider: "api_football", protection_overridden: false, version: 1,
    kickoff_at: null, normalized_json: { home_team: "Beşiktaş", away_team: "Opponent", raw_status: "TBD", competition: "Cup" } } as FixtureBinding;
  const now = new Date(2026, 9, 3, 9);
  expect(projectPhengosCards({ fixtures: [unknown] }, now)).toEqual([]);
  const sources = fixtureSourcesForRules([{ next_fixture_selection_known: true, current_next_fixture_id: "9002" } as StandingCalendarRule], [[unknown]]);
  const card = projectPhengosCards(sources, now)[0];
  expect(card.detail).toBe("Time not confirmed · Cup");
  expect(card.startsAt).toBeUndefined();
  expect(projectPhengosCards({ ...sources, fixtures: [{ ...unknown, suppressed: true }] }, now)).toEqual([]);
});

it("sends complex proposals to their saved thread for full review", () => {
  const now = new Date(2026, 9, 3, 9);
  const proposal = { id: "p1", thread_id: "conversation 1", summary: "Create a plan", tool_name: "plan_create",
    arguments: { notes: "x".repeat(200) }, status: "pending", expires_at: new Date(now.getTime() + 600_000).toISOString(),
    consequence_category: "consequential", confirmation_required: true, version: 1 } satisfies AssistantActionProposal;
  const card = projectPhengosCards({ proposals: [proposal] }, now)[0];
  expect(card.href).toBe("/self/assistant?thread=conversation%201");
  expect(card.action).toBeUndefined();
});
