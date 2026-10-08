import type { AssistantActionProposal, CalendarProjection, FitnessStatus, FixtureBinding, MealPlan, ShoppingAggregate, StandingCalendarRule } from "../../types/api";

export type PhengosCard = {
  id: string;
  kind: "agenda" | "commitment" | "shopping" | "workout" | "meal" | "fixture" | "proposal";
  priority: number;
  title: string;
  eyebrow: string;
  detail: string;
  href: string;
  startsAt?: string;
  items?: Array<{ title: string; detail?: string; sourceId?: string }>;
  action?: { kind: "start-workout" | "start-cooking" | "confirm-proposal"; id: string };
  fixture?: { home: string; away: string; homeLogo?: string; awayLogo?: string };
  size: "wide" | "standard" | "compact";
};

type Sources = {
  calendar?: CalendarProjection;
  fitness?: FitnessStatus;
  shopping?: ShoppingAggregate[];
  meals?: MealPlan[];
  fixtures?: FixtureBinding[];
  selectedNextFixtureIds?: ReadonlySet<string>;
  proposals?: AssistantActionProposal[];
};

export function fixtureSourcesForRules(rules: StandingCalendarRule[], lists: Array<FixtureBinding[] | undefined>) {
  const selectedNextFixtureIds = new Set<string>();
  const fixtures = rules.flatMap((rule, index) => {
    const cached = lists[index] ?? [];
    if (!rule.next_fixture_selection_known) return cached;
    const selected = cached.filter(fixture => fixture.source_fixture_id === rule.current_next_fixture_id);
    for (const fixture of selected) selectedNextFixtureIds.add(fixture.id);
    return selected;
  });
  return { fixtures, selectedNextFixtureIds };
}

function localDayBounds(now: Date) {
  return {
    start: new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime(),
    end: new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime(),
  };
}

function overlapsDay(start: string, end: string, day: { start: number; end: number }) {
  const a = new Date(start).getTime(), b = new Date(end).getTime();
  return Number.isFinite(a) && Number.isFinite(b) && a < day.end && b > day.start;
}

function timeLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function validLogo(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}

/** Deterministic, read-only projection of canonical domain data into the home surface. */
export function projectPhengosCards(sources: Sources, now = new Date()): PhengosCard[] {
  const cards: PhengosCard[] = [];
  const day = localDayBounds(now);
  const currentTime = now.getTime();
  for (const proposal of sources.proposals ?? []) {
    if (proposal.status !== "pending" || new Date(proposal.expires_at).getTime() <= currentTime) continue;
    const argumentsToReview = Object.entries(proposal.arguments).filter(([, value]) => value != null);
    const readable = argumentsToReview.length <= 8 && argumentsToReview.every(([, value]) => {
      try { return (typeof value === "string" ? value : JSON.stringify(value)).length <= 180; }
      catch { return false; }
    });
    cards.push({ id: `proposal:${proposal.id}`, kind: "proposal", priority: 116, title: proposal.summary,
      eyebrow: "PHENGOS PROPOSES", detail: `${proposal.tool_name.replaceAll("_", " ")} · Review before saving`,
      href: proposal.thread_id ? `/self/assistant?thread=${encodeURIComponent(proposal.thread_id)}` : "/self/assistant",
      size: "wide", action: readable ? { kind: "confirm-proposal", id: proposal.id } : undefined,
      items: argumentsToReview.slice(0, 8).map(([key, value]) => ({ title: key.replaceAll("_", " "),
        detail: typeof value === "string" ? value : JSON.stringify(value) })),
    });
  }
  const blocks = (sources.calendar?.current_plan?.blocks ?? []).filter(block =>
    !["completed", "skipped", "missed", "cancelled"].includes(block.status.toLowerCase())
      && block.block_type !== "slack" && overlapsDay(block.starts_at, block.ends_at, day));
  const agendaBlocks = blocks.filter(block => block.domain !== "fitness")
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
  const agenda = agendaBlocks.slice(0, 4);
  if (agenda.length) cards.push({
    id: `agenda:${sources.calendar?.current_plan?.id}`, kind: "agenda", priority: agenda.some(block => block.status === "in_progress") ? 112 : 84,
    title: "Today", eyebrow: "YOUR DAY", detail: `${agendaBlocks.length} planned ${agendaBlocks.length === 1 ? "block" : "blocks"}`,
    href: "/calendar#daily-list", size: "wide", items: [
      ...agenda.map(block => ({ title: block.title, detail: timeLabel(block.starts_at) })),
      ...(agendaBlocks.length > agenda.length ? [{ title: `+${agendaBlocks.length - agenda.length} more in your daily plan` }] : []),
    ],
  });

  const plannedFitness = blocks.find(block => block.domain === "fitness");
  const session = sources.fitness?.active_session;
  const nextWorkout = sources.fitness?.next_workout;
  if (session) cards.push({
    id: `workout:${session.id}`, kind: "workout", priority: 120, title: session.template?.name ?? "Workout in progress",
    eyebrow: "ACTIVE TRAINING", detail: "Continue your session", href: "/fitness#training", size: "standard",
  });
  else if (plannedFitness) cards.push({
    id: `workout:plan:${plannedFitness.id}`, kind: "workout", priority: 92, title: plannedFitness.title,
    eyebrow: "TRAINING TODAY", detail: `${timeLabel(plannedFitness.starts_at)} · ${plannedFitness.duration_minutes} min`,
    href: "/fitness#training", size: "standard", startsAt: plannedFitness.starts_at,
  });
  else if (nextWorkout) cards.push({
    id: `workout:next:${nextWorkout.id}`, kind: "workout", priority: 35, title: nextWorkout.name,
    eyebrow: "NEXT WORKOUT", detail: `${nextWorkout.estimated_duration_minutes} min planned`, href: "/fitness#training", size: "compact",
    action: { kind: "start-workout", id: nextWorkout.id },
  });

  const committedIds = new Set(blocks.map(block => block.commitment_id).filter(Boolean));
  const upcoming = (sources.calendar?.commitments ?? []).filter(item => {
    const starts = new Date(item.starts_at).getTime();
    return !["completed", "cancelled"].includes(item.status.toLowerCase()) && !committedIds.has(item.canonical_id)
      && Number.isFinite(starts) && starts >= currentTime && starts < day.end;
  }).sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
  for (const item of upcoming.slice(0, 2)) cards.push({
    id: `commitment:${item.canonical_id}`, kind: "commitment", priority: item.level === "hard" ? 98 : 78,
    title: item.title, eyebrow: "UPCOMING TODAY", detail: `${timeLabel(item.starts_at)}${item.location ? ` · ${item.location}` : ""}`,
    href: "/calendar", startsAt: item.starts_at, size: "standard",
  });

  const shopping = (sources.shopping ?? []).filter(item => item.status.toLowerCase() === "open");
  if (shopping.length) cards.push({
    id: "shopping:active", kind: "shopping", priority: shopping.some(item => item.priority_class === "required") ? 76 : 58,
    title: "Shopping", eyebrow: "HOME · KITCHEN", detail: `${shopping.length} ${shopping.length === 1 ? "item" : "items"} to get`,
    href: "/kitchen#shopping", size: "standard",
    items: shopping.slice(0, 4).map(item => ({ title: item.ingredient_name, detail: `${item.quantity} ${item.unit}`,
      sourceId: item.source_item_ids.length === 1 ? item.source_item_ids[0] : undefined })),
  });

  const meal = (sources.meals ?? []).filter(item => { const planned = new Date(item.planned_for).getTime();
    return item.status.toLowerCase() === "selected" && Number.isFinite(planned) && planned >= day.start && planned < day.end; })
    .sort((a, b) => new Date(a.planned_for).getTime() - new Date(b.planned_for).getTime())[0];
  if (meal) cards.push({
    id: `meal:${meal.id}`, kind: "meal", priority: 72, title: meal.recipe.name, eyebrow: "SELECTED MEAL",
    detail: `${timeLabel(meal.planned_for)} · ${meal.recipe.preparation_minutes + meal.recipe.cooking_minutes} min`,
    href: "/kitchen#nutrition", startsAt: meal.planned_for, size: "standard", action: { kind: "start-cooking", id: meal.id },
  });

  const futureFixtures = (sources.fixtures ?? []).filter(fixture => {
    const kickoff = fixture.kickoff_at ? new Date(fixture.kickoff_at).getTime() : NaN;
    return !fixture.suppressed && ["SCHEDULED", "CONFIRMED"].includes(fixture.fixture_status.toUpperCase())
      && (Number.isFinite(kickoff) ? kickoff >= currentTime
        : fixture.normalized_json.raw_status === "TBD" && sources.selectedNextFixtureIds?.has(fixture.id));
  }).sort((a, b) => (a.kickoff_at ? new Date(a.kickoff_at).getTime() : Infinity)
    - (b.kickoff_at ? new Date(b.kickoff_at).getTime() : Infinity) || a.id.localeCompare(b.id));
  const fixture = futureFixtures[0];
  if (fixture) {
    const kickoff = fixture.kickoff_at ? new Date(fixture.kickoff_at).getTime() : NaN;
    const details = fixture.normalized_json;
    const home = typeof details.home_team === "string" ? details.home_team : "Home";
    const away = typeof details.away_team === "string" ? details.away_team : "Away";
    const confirmedTime = Number.isFinite(kickoff) && details.raw_status !== "TBD";
    const competition = typeof details.competition === "string" ? details.competition : "";
    const when = confirmedTime ? new Intl.DateTimeFormat(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(kickoff) : "Time not confirmed";
    cards.push({ id: `fixture:${fixture.id}`, kind: "fixture", priority: kickoff <= currentTime + 48 * 60 * 60_000 ? 75 : 52,
      title: `${home} vs ${away}`, eyebrow: "MATCH COMING UP", detail: [when, competition].filter(Boolean).join(" · "),
      href: fixture.commitment_id ? `/calendar?commitment=${encodeURIComponent(fixture.commitment_id)}` : "/calendar",
      startsAt: fixture.kickoff_at ?? undefined, size: "wide",
      fixture: { home, away, homeLogo: validLogo(details.home_team_logo_url), awayLogo: validLogo(details.away_team_logo_url) },
    });
  }

  return cards.sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id)).slice(0, 8);
}
