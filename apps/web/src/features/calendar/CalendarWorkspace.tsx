import { ArrowRight, CalendarDays, ChevronLeft, ChevronRight, Clock3, Plus, Sparkles } from "lucide-react";
import { useMemo, useRef, useState, type CSSProperties } from "react";
import type { CalendarProjection, HorizonAllocation, Plan, PlanProposal } from "../../types/api";
import { addDays, calendarEvents, dayKey, eventsOnDay, shiftView, startOfDay, startOfWeek, type CalendarEvent, type CalendarView } from "./calendarWorkspaceModel";
import "./calendar-workspace.css";

type Props = {
  projection?: CalendarProjection;
  plan?: Plan | null;
  horizon?: HorizonAllocation;
  proposals?: PlanProposal[];
  loading: boolean;
  error: boolean;
  onAddCommitment: () => void;
  onAddIntention: () => void;
};

const WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const MONTH = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });
const TIME = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const FULL_DATE = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
const HOURS = Array.from({ length: 24 }, (_, index) => index);
const HOUR_HEIGHT = 42;

function rangeLabel(date: Date, view: CalendarView) {
  if (view === "day") return FULL_DATE.format(date);
  if (view === "month") return MONTH.format(date);
  const start = startOfWeek(date);
  const end = addDays(start, 6);
  const first = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(start);
  const last = new Intl.DateTimeFormat(undefined, { month: start.getMonth() === end.getMonth() ? undefined : "short", day: "numeric", year: "numeric" }).format(end);
  return `${first} – ${last}`;
}

function eventPosition(event: CalendarEvent, date: Date) {
  const dayStart = startOfDay(date).getTime();
  const start = Math.max(event.startsAt.getTime(), dayStart);
  const end = Math.min(event.endsAt.getTime(), addDays(date, 1).getTime());
  return { top: ((start - dayStart) / 3_600_000) * HOUR_HEIGHT, height: Math.max(26, ((end - start) / 3_600_000) * HOUR_HEIGHT) };
}

function layoutDay(events: CalendarEvent[], date: Date) {
  const visible = eventsOnDay(events, date).map(event => ({ event, ...eventPosition(event, date), lane: 0, lanes: 1 }));
  let group: typeof visible = [];
  let groupEnd = -1;
  let occupiedUntil: number[] = [];
  const finishGroup = () => { for (const item of group) item.lanes = occupiedUntil.length; group = []; occupiedUntil = []; };
  for (const item of visible) {
    if (item.top >= groupEnd) { finishGroup(); groupEnd = -1; }
    const lane = occupiedUntil.findIndex(end => end <= item.top);
    item.lane = lane === -1 ? occupiedUntil.push(item.top + item.height) - 1 : lane;
    occupiedUntil[item.lane] = item.top + item.height;
    group.push(item);
    groupEnd = Math.max(groupEnd, item.top + item.height);
  }
  finishGroup();
  return visible;
}

function Timeline({ dates, events, selectedId, onSelect, onDaySelect }: { dates: Date[]; events: CalendarEvent[]; selectedId: string | null; onSelect: (id: string) => void; onDaySelect: (date: Date) => void }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const initializedScroll = useRef(false);
  return <div className="cal-timeline-scroll" ref={node => {
    scrollRef.current = node;
    if (node && !initializedScroll.current) { node.scrollTop = 7 * HOUR_HEIGHT; initializedScroll.current = true; }
  }}>
    <div className="cal-timeline" style={{ "--cal-days": dates.length, "--cal-hour-height": `${HOUR_HEIGHT}px`, "--cal-track-height": `${24 * HOUR_HEIGHT}px`, minWidth: 58 + dates.length * 85 } as CSSProperties}>
      <div className="cal-time-heading">LOCAL TIME</div>
      {dates.map(date => <button className={`cal-day-heading ${dayKey(date) === dayKey(new Date()) ? "is-today" : ""}`} key={dayKey(date)} onClick={() => onDaySelect(date)} type="button" aria-label={`Open ${FULL_DATE.format(date)} in day view`}>
        <span>{WEEKDAY.format(date)}</span><strong>{date.getDate()}</strong>
      </button>)}
      <div className="cal-hour-labels">{HOURS.map(hour => <span key={hour} style={{ top: hour * HOUR_HEIGHT }}>{String(hour).padStart(2, "0")}:00</span>)}</div>
      {dates.map(date => <div className="cal-day-track" key={dayKey(date)}>
        {layoutDay(events, date).map(({ event, top, height, lane, lanes }) => {
          return <button type="button" key={event.id} className={`cal-event cal-origin-${event.domain} ${selectedId === event.id ? "is-selected" : ""}`} style={{ top, height, left: `calc(${lane} * (100% - 8px) / ${lanes} + 4px)`, width: `calc((100% - 8px) / ${lanes})` }} onClick={() => onSelect(event.id)} aria-label={`${event.title}, ${TIME.format(event.startsAt)} to ${TIME.format(event.endsAt)}`}>
            <strong>{event.title}</strong><span>{TIME.format(event.startsAt)} – {TIME.format(event.endsAt)}</span>
          </button>;
        })}
      </div>)}
    </div>
  </div>;
}

function MonthGrid({ date, events, onDaySelect }: { date: Date; events: CalendarEvent[]; onDaySelect: (day: Date) => void }) {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const gridStart = startOfWeek(first);
  const days = Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  const weekdays = Array.from({ length: 7 }, (_, index) => WEEKDAY.format(addDays(gridStart, index)));
  return <div className="cal-month-grid" role="grid" aria-label={MONTH.format(date)}>
    {weekdays.map((day, index) => <span className="cal-month-weekday" key={index}>{day}</span>)}
    {days.map(day => {
      const dayEvents = eventsOnDay(events, day);
      return <button type="button" role="gridcell" key={dayKey(day)} className={`cal-month-day ${day.getMonth() !== date.getMonth() ? "outside" : ""} ${dayKey(day) === dayKey(new Date()) ? "is-today" : ""}`} onClick={() => onDaySelect(day)} aria-label={`${FULL_DATE.format(day)}, ${dayEvents.length} known items`}>
        <strong>{day.getDate()}</strong><span className="cal-month-dots">{dayEvents.slice(0, 4).map(event => <i className={`cal-origin-${event.domain}`} key={event.id} />)}</span><small>{dayEvents.length ? `${dayEvents.length} known` : ""}</small>
      </button>;
    })}
  </div>;
}

export function CalendarWorkspace({ projection, plan, horizon, proposals, loading, error, onAddCommitment, onAddIntention }: Props) {
  const [view, setView] = useState<CalendarView>("week");
  const [date, setDate] = useState(() => startOfDay(new Date()));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const events = useMemo(() => calendarEvents(projection, plan ?? projection?.current_plan), [projection, plan]);
  const weekStart = startOfWeek(date);
  const dates = view === "week" ? Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)) : [date];
  const selected = events.find(event => event.id === selectedId);
  const today = startOfDay(new Date());
  const todayEvents = eventsOnDay(events, today);
  const activityStart = view === "month" ? new Date(date.getFullYear(), date.getMonth(), 1) : weekStart;
  const activityEnd = view === "month" ? new Date(date.getFullYear(), date.getMonth() + 1, 1) : addDays(weekStart, 7);
  const activityEvents = events.filter(event => event.startsAt < activityEnd && event.endsAt > activityStart);
  const allocationMinutes = (horizon?.allocations ?? []).filter(item => view === "month" ? item.planning_date >= dayKey(activityStart) && item.planning_date < dayKey(activityEnd) : dates.some(day => item.planning_date === dayKey(day))).reduce((sum, item) => sum + item.allocated_minutes, 0);
  const weekAllocations = Array.from({ length: 7 }, (_, index) => {
    const day = addDays(weekStart, index);
    return { day, minutes: (horizon?.allocations ?? []).filter(item => item.planning_date === dayKey(day)).reduce((sum, item) => sum + item.allocated_minutes, 0) };
  });
  const maxAllocation = Math.max(60, ...weekAllocations.map(item => item.minutes));
  const displayedEvents = view === "month" ? activityEvents : events.filter(event => dates.some(day => eventsOnDay([event], day).length));
  const pendingProposal = proposals?.find(proposal => proposal.status === "DRAFT" || proposal.status === "PRESENTED" || proposal.status === "MODIFIED");
  const needsAttention = Boolean(plan?.overload_status && plan.overload_status !== "feasible");
  const goDay = (day: Date) => { setDate(day); setView("day"); setSelectedId(null); };

  return <section className="cal-workspace" aria-label="Calendar workspace">
    <div className="cal-workspace-layout">
      <div className="cal-main-column">
        <div className="cal-workspace-heading"><div className="cal-title-mark"><CalendarDays size={29} aria-hidden="true" /></div><div><h1>Calendar</h1><p>Plan your time. Align your life.</p></div></div>
        <div className="cal-main-panel">
        <div className="cal-toolbar">
          <div className="cal-view-tabs" aria-label="Calendar view">{(["day", "week", "month"] as const).map(option => <button key={option} type="button" aria-pressed={view === option} className={view === option ? "active" : ""} onClick={() => { setView(option); setSelectedId(null); }}>{option}</button>)}</div>
          <div className="cal-date-navigation"><button type="button" aria-label={`Previous ${view}`} onClick={() => setDate(current => shiftView(current, view, -1))}><ChevronLeft size={17} /></button><button type="button" onClick={() => setDate(today)}>Today</button><button type="button" aria-label={`Next ${view}`} onClick={() => setDate(current => shiftView(current, view, 1))}><ChevronRight size={17} /></button></div>
          <strong className="cal-range-label">{rangeLabel(date, view)}</strong>
          <button type="button" className="cal-add-button" onClick={onAddCommitment} aria-label="Go to Add Commitment"><Plus size={21} /></button>
        </div>
        {loading ? <p className="cal-data-note" role="status">Loading commitments and plan blocks…</p> : null}
        {error ? <p className="cal-data-note error" role="status">Some calendar data could not be loaded. Showing available items only.</p> : null}
        {!loading && !error && displayedEvents.length === 0 ? <p className="cal-data-note">No known scheduled items in this {view}. Add a commitment or create a plan below.</p> : null}
        {view === "month" ? <MonthGrid date={date} events={events} onDaySelect={goDay} /> : <Timeline dates={dates} events={events} selectedId={selectedId} onSelect={setSelectedId} onDaySelect={goDay} />}
        <p className="cal-coverage-note">Loaded commitments and current plan · dates outside the projection may be incomplete</p>
        </div>
        <div className="cal-action-dock"><span><CalendarDays size={18} aria-hidden="true" /> Calendar actions</span><button type="button" onClick={onAddIntention}>New intention</button><a href="#daily-list">Planning controls</a><button className="cal-dock-primary" type="button" onClick={onAddCommitment}><Plus size={16} aria-hidden="true" /> Add event</button></div>
      </div>
      <aside className="cal-insights" aria-label="Calendar details and summaries">
        <div className="cal-insights-heading"><strong>{FULL_DATE.format(today)}</strong><span>{loading ? "Reading today's schedule…" : `${todayEvents.length} known scheduled ${todayEvents.length === 1 ? "item" : "items"} today`}</span></div>
        {pendingProposal ? <a className="cal-insight cal-suggestion" href="#plan-proposals"><span className="cal-suggestion-icon"><Sparkles size={18} aria-hidden="true" /></span><span><small>PHÉNGOS SUGGESTION</small><strong>{String(pendingProposal.trajectory_snapshot.exam_title ?? "Planning proposal")} · {pendingProposal.status.toLowerCase()}</strong><p>{pendingProposal.reason_code.replaceAll("_", " ")}</p></span><ChevronRight size={17} aria-hidden="true" /></a>
          : needsAttention ? <a className="cal-insight cal-suggestion" href="#daily-list"><span className="cal-suggestion-icon"><Sparkles size={18} aria-hidden="true" /></span><span><small>PHÉNGOS SUGGESTION</small><strong>{new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(today)} is overloaded by {plan?.shortfall_minutes ?? 0} min.</strong><p>Review today’s plan and adjust your time.</p></span><ChevronRight size={17} aria-hidden="true" /></a> : null}
        {needsAttention ? <div className="cal-insight cal-attention"><small>NEEDS ATTENTION</small><strong>{plan?.overload_status?.replaceAll("_", " ")}</strong><p>Current shortfall: {plan?.shortfall_minutes ?? 0} minutes.</p><a href="#daily-list">Review plan <ChevronRight size={14} /></a></div> : null}
        <div className="cal-insight cal-today"><small>TODAY · {new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(today)}</small><strong>{loading ? "Loading known items…" : `${todayEvents.length} known scheduled ${todayEvents.length === 1 ? "item" : "items"}`}</strong><div className="cal-today-list">{todayEvents.slice(0, 4).map(event => <button type="button" key={event.id} className={`cal-origin-${event.domain}`} onClick={() => { setDate(today); setView("day"); setSelectedId(event.id); }}><span>{TIME.format(event.startsAt)}</span><strong>{event.title}</strong><ChevronRight size={14} /></button>)}{!loading && todayEvents.length === 0 ? <p>No known items today.</p> : null}</div></div>
        {selected && <div className={`cal-insight cal-selection cal-origin-${selected.domain}`}><small>{selected.kind === "plan" ? "PLAN BLOCK" : "COMMITMENT"}</small><h2>{selected.title}</h2><p>{FULL_DATE.format(selected.startsAt)}</p><p><Clock3 size={14} aria-hidden="true" /> {TIME.format(selected.startsAt)} – {TIME.format(selected.endsAt)}</p><p>{selected.detail} · {selected.status.replaceAll("_", " ")}</p><a href="#daily-list">Open planning controls <ChevronRight size={14} /></a></div>}
        <div className="cal-insight cal-capacity"><div className="cal-capacity-title"><small>WEEK ALLOCATION</small><strong>{horizon ? `${weekAllocations.reduce((sum, item) => sum + item.minutes, 0)}m` : "—"}</strong></div><div className="cal-capacity-bars">{weekAllocations.map(item => <div key={dayKey(item.day)} title={horizon ? `${WEEKDAY.format(item.day)}: ${item.minutes} allocated minutes` : `${WEEKDAY.format(item.day)}: allocation unavailable`}><span className="cal-capacity-track">{horizon ? <i style={{ height: `${Math.max(item.minutes ? 10 : 3, item.minutes / maxAllocation * 100)}%` }} /> : null}</span><small>{WEEKDAY.format(item.day)}</small></div>)}</div><p>{horizon ? `${allocationMinutes} allocated minutes for the visible ${view} in the loaded horizon.` : "Capacity data is unavailable."}</p></div>
        <div className="cal-insight cal-commitment-mini"><div className="cal-mini-heading"><small>COMMITMENT CALENDAR</small><span>{MONTH.format(date)}</span></div><div>{Array.from({ length: new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate() }, (_, index) => { const day = new Date(date.getFullYear(), date.getMonth(), index + 1); const count = eventsOnDay(events.filter(event => event.kind === "commitment"), day).length; return <button type="button" key={index} onClick={() => goDay(day)} className={count ? "has-item" : ""} title={`${FULL_DATE.format(day)}: ${count} known commitments`} aria-label={`${FULL_DATE.format(day)}: ${count} known commitments`}><span>{index + 1}</span></button>; })}</div></div>
        <a className="cal-utility-link" href="#calendar-utilities">All calendar utilities <ArrowRight size={15} aria-hidden="true" /></a>
      </aside>
    </div>
  </section>;
}
