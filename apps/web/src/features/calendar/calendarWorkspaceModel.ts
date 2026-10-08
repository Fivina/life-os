import type { CalendarProjection, Plan } from "../../types/api";

export type CalendarView = "day" | "week" | "month";
export type CalendarEvent = {
  id: string;
  title: string;
  startsAt: Date;
  endsAt: Date;
  domain: string;
  kind: "commitment" | "plan";
  detail: string;
  status: string;
};

export function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function addDays(date: Date, days: number) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function startOfWeek(date: Date) {
  return addDays(startOfDay(date), -((date.getDay() + 6) % 7));
}

export function shiftView(date: Date, view: CalendarView, amount: number) {
  if (view === "month") return new Date(date.getFullYear(), date.getMonth() + amount, Math.min(date.getDate(), new Date(date.getFullYear(), date.getMonth() + amount + 1, 0).getDate()));
  return addDays(date, amount * (view === "week" ? 7 : 1));
}

export function dayKey(date: Date) {
  const local = startOfDay(date);
  return `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, "0")}-${String(local.getDate()).padStart(2, "0")}`;
}

export function eventDomain(value?: string | null) {
  const domain = (value ?? "").toLowerCase();
  if (["home", "kitchen", "shopping", "household"].includes(domain)) return "home";
  if (["fitness", "training", "nutrition"].includes(domain)) return "fitness";
  if (["learning", "study", "university"].includes(domain)) return "learning";
  if (["life", "social", "personal"].includes(domain)) return "life";
  return "calendar";
}

export function calendarEvents(projection?: CalendarProjection, plan?: Plan | null): CalendarEvent[] {
  const commitments: CalendarEvent[] = (projection?.commitments ?? [])
    .filter(item => item.status === "active")
    .map(item => ({
      id: `commitment:${item.canonical_id}`,
      title: item.title,
      startsAt: new Date(item.starts_at),
      endsAt: new Date(item.ends_at),
      domain: eventDomain(item.source),
      kind: "commitment" as const,
      detail: item.location || item.commitment_type.replaceAll("_", " "),
      status: item.status
    }));
  const commitmentIds = new Set((projection?.commitments ?? []).map(item => item.canonical_id));
  const blocks: CalendarEvent[] = (plan?.blocks ?? [])
    .filter(block => block.block_type !== "hard_commitment" || !block.commitment_id || !commitmentIds.has(block.commitment_id))
    .map(block => ({
      id: `plan:${block.id}`,
      title: block.title,
      startsAt: new Date(block.starts_at),
      endsAt: new Date(block.ends_at),
      domain: eventDomain(block.domain),
      kind: "plan" as const,
      detail: [block.block_type.replaceAll("_", " "), block.variant_type?.replaceAll("_", " ")].filter(Boolean).join(" · "),
      status: block.status
    }));
  return [...commitments, ...blocks].filter(event => Number.isFinite(event.startsAt.getTime()) && Number.isFinite(event.endsAt.getTime()) && event.endsAt > event.startsAt).sort((a, b) => a.startsAt.getTime() - b.startsAt.getTime());
}

export function eventsOnDay(events: CalendarEvent[], date: Date) {
  const start = startOfDay(date).getTime();
  const end = addDays(date, 1).getTime();
  return events.filter(event => event.startsAt.getTime() < end && event.endsAt.getTime() > start);
}
