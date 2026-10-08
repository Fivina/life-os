import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowUpRight, CalendarDays, Check, CircleDot, Dumbbell, ListChecks, Pin, ShoppingCart, Sparkles, Utensils, X } from "lucide-react";
import { useState, type CSSProperties } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api";
import type { CalendarProjection, FitnessStatus, MealPlan, ShoppingAggregate } from "../../types/api";
import { projectPhengosCards, type PhengosCard } from "./phengosCardProjection";

const icons = { agenda: ListChecks, commitment: CalendarDays, shopping: ShoppingCart, workout: Dumbbell, meal: Utensils, fixture: CircleDot, proposal: Sparkles };
const PIN_KEY = "life-os:phengos-pinned-cards";

function savedPins(): Set<string> {
  try { const value = JSON.parse(window.localStorage.getItem(PIN_KEY) ?? "[]"); return new Set(Array.isArray(value) ? value.filter(item => typeof item === "string") : []); }
  catch { return new Set(); }
}

export function PhengosContextCards() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const reduced = !!useReducedMotion();
  const [dismissed, setDismissed] = useState<Set<string>>(() => new Set());
  const [pinned, setPinned] = useState(savedPins);
  const [actionNotice, setActionNotice] = useState("");
  const calendar = useQuery({ queryKey: ["calendar-projection"], queryFn: api.calendarProjection, retry: false, staleTime: 30_000, refetchInterval: 60_000 });
  const fitness = useQuery({ queryKey: ["fitness-status"], queryFn: api.fitnessStatus, retry: false, staleTime: 30_000, refetchInterval: 60_000 });
  const shopping = useQuery({ queryKey: ["shopping-list"], queryFn: api.shoppingList, retry: false, staleTime: 30_000, refetchInterval: 60_000 });
  const meals = useQuery({ queryKey: ["meal-plans"], queryFn: api.mealPlans, retry: false, staleTime: 30_000, refetchInterval: 60_000 });
  const rules = useQuery({ queryKey: ["standing-calendar-rules"], queryFn: api.standingCalendarRules, retry: false, staleTime: 60_000, refetchInterval: 300_000 });
  const proposals = useQuery({ queryKey: ["assistant-pending-proposals"], queryFn: api.pendingAssistantProposals, retry: false, staleTime: 15_000, refetchInterval: 15_000 });
  const fixtureQueries = useQueries({ queries: (rules.data ?? []).filter(rule => rule.enabled && rule.rule_type === "SPORTS_FIXTURE")
    .map(rule => ({ queryKey: ["standing-rule-fixtures", rule.id], queryFn: () => api.standingRuleFixtures(rule.id), retry: false, staleTime: 60_000, refetchInterval: 60_000 })) });
  const purchase = useMutation({
    mutationFn: (id: string) => api.markShoppingPurchased(id, { add_to_inventory: true }),
    onSuccess: () => {
      setActionNotice("Shopping item marked purchased.");
      for (const key of ["shopping-list", "shopping-needs", "inventory", "kitchen-status"]) void queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  const startWorkout = useMutation({
    mutationFn: (templateId: string) => api.startWorkout({ workout_template_id: templateId }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ["fitness-status"] }); navigate("/fitness#training", { state: { phengosOriginLayer: "overview" } }); },
  });
  const confirmProposal = useMutation({
    mutationFn: (id: string) => api.confirmAssistantProposal(id),
    onSuccess: response => {
      if (response.response_type !== "MUTATION_RESULT") return;
      setActionNotice(response.message || "Proposal approved and saved.");
      for (const key of ["assistant-pending-proposals", "calendar-projection", "fitness-status", "shopping-list", "meal-plans", "current-plan", "review-items"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });
  const cancelProposal = useMutation({
    mutationFn: (id: string) => api.cancelAssistantProposal(id),
    onSuccess: response => { if (response.response_type === "NO_ACTION") { setActionNotice(response.message); void queryClient.invalidateQueries({ queryKey: ["assistant-pending-proposals"] }); } },
  });
  const cards = projectPhengosCards({ calendar: calendar.data, fitness: fitness.data, shopping: shopping.data, meals: meals.data,
    fixtures: fixtureQueries.flatMap(query => query.data ?? []), proposals: proposals.data });
  const visibleCards = cards.filter(card => card.kind !== "agenda" && !dismissed.has(card.id))
    .sort((a, b) => Number(pinned.has(b.id)) - Number(pinned.has(a.id)));
  // A dismissed real card must not reappear immediately as its utility fallback.
  const represented = new Set(cards.filter(card => card.kind !== "agenda").map(card => card.kind));
  const fallbackKinds = (["shopping", "workout", "meal", "assistant"] as const)
    .filter(kind => kind === "assistant" || !represented.has(kind))
    .slice(0, Math.max(0, 4 - visibleCards.length));
  const togglePin = (id: string) => setPinned(previous => {
    const next = new Set(previous);
    if (next.has(id)) next.delete(id); else next.add(id);
    try { window.localStorage.setItem(PIN_KEY, JSON.stringify([...next])); } catch { /* Pinning remains available for this view. */ }
    return next;
  });
  const loading = calendar.isPending || fitness.isPending || shopping.isPending || meals.isPending || rules.isPending || proposals.isPending
    || fixtureQueries.some(query => query.isPending);
  const failed = calendar.isError || fitness.isError || shopping.isError || meals.isError || rules.isError || proposals.isError
    || fixtureQueries.some(query => query.isError);

  return <section className="phengos-today" aria-label="What matters now">
    <div className="phengos-today-heading"><div><span>YOUR GENERAL SURFACE</span><h3>Today at a glance</h3></div>
      <div className="phengos-today-heading-meta">
        {failed && <span className="phengos-source-status" role="status" title="Some live cards are unavailable. Open a domain for its full view.">Some cards unavailable</span>}
        <time>{new Intl.DateTimeFormat(undefined, { weekday: "long", month: "short", day: "numeric" }).format(new Date())}</time>
      </div></div>
    <DashboardFoundation calendar={calendar.data} calendarPending={calendar.isPending} calendarError={calendar.isError}
      fitness={fitness.data} shopping={shopping.data} meals={meals.data} />
    <div className="phengos-domain-section-heading"><span>AROUND YOUR DAY</span><span>What matters, then what is one step away</span></div>
    <div className="phengos-context">
      <AnimatePresence initial={false}>
        {visibleCards.map((card, index) => <ContextCard key={card.id} card={card} index={index} reduced={reduced}
          dismiss={() => { document.querySelector<HTMLInputElement>("#phengos-request")?.focus(); setDismissed(previous => new Set(previous).add(card.id)); }}
          pinned={pinned.has(card.id)} togglePin={() => togglePin(card.id)}
          purchase={id => purchase.mutate(id)} purchasing={purchase.isPending}
          startWorkout={id => startWorkout.mutate(id)} startingWorkout={startWorkout.isPending}
          confirmProposal={id => confirmProposal.mutate(id)} confirmingProposal={confirmProposal.isPending}
          cancelProposal={id => cancelProposal.mutate(id)} cancellingProposal={cancelProposal.isPending} />)}
      </AnimatePresence>
      {fallbackKinds.map(kind => <EverydayCard key={kind} kind={kind} shopping={shopping.data} fitness={fitness.data} meals={meals.data} />)}
    </div>
    {loading && <p className="phengos-today-empty" role="status">Reading your plans and saved items…</p>}
    {actionNotice && <p className="phengos-context-notice" role="status">{actionNotice}</p>}
    {confirmProposal.data && confirmProposal.data.response_type !== "MUTATION_RESULT" && <p className="phengos-context-error" role="alert">{confirmProposal.data.message}</p>}
    {confirmProposal.isError && <p className="phengos-context-error" role="alert">Approval could not be saved. Open chat to review this proposal.</p>}
  </section>;
}

function EverydayCard({ kind, shopping, fitness, meals }: {
  kind: "shopping" | "workout" | "meal" | "assistant";
  shopping?: ShoppingAggregate[]; fitness?: FitnessStatus; meals?: MealPlan[];
}) {
  const openShopping = shopping?.filter(item => item.status.toLowerCase() === "open") ?? [];
  const upcomingMeal = meals?.find(item => item.status.toLowerCase() === "selected" && new Date(item.planned_for).getTime() >= Date.now());
  const details = {
    shopping: { icon: ShoppingCart, eyebrow: "HOME / SHOPPING", title: openShopping.length ? "Shopping needed" : "Shopping list",
      detail: openShopping.length ? `${openShopping.length} items to get` : "Your list is clear", href: "/kitchen#shopping", action: "Open list" },
    workout: { icon: Dumbbell, eyebrow: "FITNESS / TRAINING", title: fitness?.next_workout?.name ?? "Your training",
      detail: fitness?.next_workout ? `${fitness.next_workout.estimated_duration_minutes} min · Next session` : "Plan your next session", href: "/fitness#training", action: "Open training" },
    meal: { icon: Utensils, eyebrow: "HOME / KITCHEN", title: upcomingMeal?.recipe.name ?? "What to cook",
      detail: upcomingMeal ? "Selected meal" : "Find a meal that fits today", href: "/kitchen", action: "Open Kitchen" },
    assistant: { icon: Sparkles, eyebrow: "SELF / ASSISTANT", title: "Plan with PHÉNGOS",
      detail: "Ask, reflect, or shape your next step", href: "/self/assistant", action: "Open assistant" },
  }[kind];
  const Icon = details.icon;
  return <article className={`phengos-everyday-card phengos-everyday-card--${kind}`}>
    <div className="phengos-everyday-top"><Icon size={22} aria-hidden="true" /><span>{details.eyebrow}</span><ArrowUpRight size={16} aria-hidden="true" /></div>
    <h4>{details.title}</h4><p>{details.detail}</p>
    {kind === "shopping" && openShopping.length > 0 && <ul>{openShopping.slice(0, 2).map(item => <li key={item.ingredient_name}>{item.ingredient_name}</li>)}</ul>}
    <Link to={details.href} state={{ phengosOriginLayer: "overview" }}>{details.action}<ArrowUpRight size={15} aria-hidden="true" /></Link>
  </article>;
}

function originColor(domain?: string | null): string {
  switch (domain?.toLowerCase()) {
    case "fitness": case "training": return "var(--life-domain-fitness)";
    case "learning": case "study": return "var(--life-domain-learning)";
    case "kitchen": case "home": case "shopping": return "var(--life-domain-home)";
    case "life": case "social": return "var(--life-domain-life)";
    case "self": case "assistant": return "var(--life-domain-self)";
    default: return "var(--life-domain-calendar)";
  }
}

function DashboardFoundation({ calendar, calendarPending, calendarError, fitness, shopping, meals }: {
  calendar?: CalendarProjection; calendarPending: boolean; calendarError: boolean;
  fitness?: FitnessStatus; shopping?: ShoppingAggregate[]; meals?: MealPlan[];
}) {
  const now = new Date();
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const dayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).getTime();
  const blocks = (calendar?.current_plan?.blocks ?? []).filter(block => {
    const start = new Date(block.starts_at).getTime(), end = new Date(block.ends_at).getTime();
    return Number.isFinite(start) && Number.isFinite(end) && start < dayEnd && end > dayStart
      && block.block_type !== "slack" && !["completed", "skipped", "missed", "cancelled"].includes(block.status.toLowerCase());
  }).sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime());
  const focusBlock = blocks.find(block => block.status === "in_progress")
    ?? blocks.find(block => new Date(block.ends_at).getTime() > now.getTime());
  const activeWorkout = fitness?.active_session;
  const focusTitle = activeWorkout?.template?.name ?? (activeWorkout ? "Workout in progress" : focusBlock?.title ?? "Your time is open");
  const focusDetail = activeWorkout ? "Continue your training" : focusBlock
    ? `${focusBlock.status === "in_progress" ? "In progress" : "Up next"} · ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(focusBlock.starts_at))}`
    : calendarPending ? "Reading your plan…" : calendarError ? "Plan unavailable" : "Choose what to focus on next";
  const focusHref = activeWorkout || focusBlock?.domain === "fitness" ? "/fitness#training" : "/calendar#daily-list";
  const focusColor = activeWorkout ? "var(--life-domain-fitness)" : focusBlock ? originColor(focusBlock.domain) : "var(--life-domain-overview)";
  const openShopping = shopping?.filter(item => item.status.toLowerCase() === "open").length;
  const selectedMeals = meals?.filter(item => {
    const planned = new Date(item.planned_for).getTime();
    return item.status.toLowerCase() === "selected" && planned >= dayStart && planned < dayEnd;
  }).length;
  const date = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(now);
  const time = (value: string) => new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));

  return <div className="phengos-dashboard-foundation">
    <article className="phengos-foundation-card phengos-foundation-card--today">
      <div className="phengos-foundation-top"><span>01 / TODAY</span><CalendarDays size={20} aria-hidden="true" /></div>
      <h4>{date}</h4>
      <p>{calendarPending ? "Reading your day…" : calendarError ? "Your plan is unavailable" : blocks.length
        ? `${blocks.length} planned ${blocks.length === 1 ? "block" : "blocks"}` : "No active plan blocks today"}</p>
      {blocks.length > 0 && <ol className="phengos-foundation-agenda">{blocks.slice(0, 3).map(block => <li key={block.id}
        style={{ "--item-origin": originColor(block.domain) } as CSSProperties}>
        <span>{block.title}</span><time dateTime={block.starts_at}>{time(block.starts_at)}</time>
      </li>)}</ol>}
      {blocks.length > 3 && <span className="phengos-foundation-more">+{blocks.length - 3} more in your plan</span>}
      <Link to="/calendar#daily-list" state={{ phengosOriginLayer: "overview" }}>Open daily plan <ArrowUpRight size={16} aria-hidden="true" /></Link>
    </article>
    <article className="phengos-foundation-card phengos-foundation-card--focus" style={{ "--card-origin": focusColor } as CSSProperties}>
      <div className="phengos-foundation-top"><span>02 / FOCUS</span><CircleDot size={20} aria-hidden="true" /></div>
      <div className="phengos-focus-orbit" aria-hidden="true"><span>{activeWorkout || focusBlock?.status === "in_progress" ? "NOW" : focusBlock ? "NEXT" : "OPEN"}</span></div>
      <div className="phengos-foundation-focus-copy"><small>{activeWorkout || focusBlock?.status === "in_progress" ? "RIGHT NOW" : focusBlock ? "COMING UP" : "OPEN SPACE"}</small>
        <h4>{focusTitle}</h4><p>{focusDetail}</p></div>
      <Link to={focusHref} state={{ phengosOriginLayer: "overview" }}>{activeWorkout ? "Continue workout" : "Open plan"} <ArrowUpRight size={16} aria-hidden="true" /></Link>
    </article>
    <article className="phengos-foundation-card phengos-foundation-card--life">
      <div className="phengos-foundation-top"><span>03 / LIFE OVERVIEW</span><CircleDot size={20} aria-hidden="true" /></div>
      <h4>Your areas</h4><p>Current state from your saved data.</p>
      <div className="phengos-life-minis">
        <Link to="/calendar" state={{ phengosOriginLayer: "overview" }}><CalendarDays size={17} aria-hidden="true" /><span>Plan</span><strong>{calendar ? blocks.length ? `${blocks.length} blocks` : "Open day" : "Loading"}</strong></Link>
        <Link to="/fitness#training" state={{ phengosOriginLayer: "overview" }}><Dumbbell size={17} aria-hidden="true" /><span>Training</span><strong>{fitness ? activeWorkout ? "In session" : fitness.next_workout ? "Next ready" : "Plan next" : "Loading"}</strong></Link>
        <Link to="/kitchen#shopping" state={{ phengosOriginLayer: "overview" }}><ShoppingCart size={17} aria-hidden="true" /><span>Shopping</span><strong>{openShopping === undefined ? "Loading" : openShopping ? `${openShopping} to get` : "List clear"}</strong></Link>
        <Link to="/kitchen" state={{ phengosOriginLayer: "overview" }}><Utensils size={17} aria-hidden="true" /><span>Meals</span><strong>{selectedMeals === undefined ? "Loading" : selectedMeals ? `${selectedMeals} selected` : "Choose meal"}</strong></Link>
      </div>
    </article>
  </div>;
}

function ContextCard({ card, index, reduced, dismiss, pinned, togglePin, purchase, purchasing, startWorkout, startingWorkout, confirmProposal, confirmingProposal, cancelProposal, cancellingProposal }: {
  card: PhengosCard; index: number; reduced: boolean; dismiss: () => void; pinned: boolean; togglePin: () => void;
  purchase: (id: string) => void; purchasing: boolean; startWorkout: (id: string) => void; startingWorkout: boolean;
  confirmProposal: (id: string) => void; confirmingProposal: boolean; cancelProposal: (id: string) => void; cancellingProposal: boolean;
}) {
  const Icon = icons[card.kind];
  return <motion.article layout="position" className={`phengos-context-card phengos-context-card--${card.kind} phengos-context-card--${card.size}`} data-pinned={pinned}
    initial={reduced ? false : { opacity: 0, y: -30, scale: 0.9 }} animate={{ opacity: 1, y: 0, scale: 1 }}
    exit={reduced ? { opacity: 0, transition: { duration: 0 } } : { opacity: 0, y: -46, scale: 0.55, transition: { duration: 0.25 } }}
    transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 280, damping: 25, delay: Math.min(index * 0.07, 0.3) }}>
    <div className="phengos-context-heading"><span className="phengos-context-icon"><Icon size={19} aria-hidden="true" /></span>
      <div><span className="phengos-context-eyebrow">{card.eyebrow}</span><h4>{card.title}</h4></div>
      <button className="phengos-icon" type="button" aria-label={`${pinned ? "Unpin" : "Pin"} ${card.kind} card`} title={pinned ? "Unpin card" : "Pin card"} onClick={togglePin}><Pin size={15} fill={pinned ? "currentColor" : "none"} /></button>
      <button className="phengos-icon" type="button" aria-label={`Dismiss ${card.kind} card`} title="Dismiss card" onClick={dismiss}><X size={17} /></button></div>
    <p className="phengos-context-note">{card.detail}</p>
    {card.fixture && <div className="phengos-fixture-teams"><TeamMark name={card.fixture.home} logo={card.fixture.homeLogo} /><span>VS</span><TeamMark name={card.fixture.away} logo={card.fixture.awayLogo} /></div>}
    {card.items?.length ? <ul className="phengos-context-items">{card.items.map((item, position) => <li key={`${item.title}:${position}`}>
      <span><strong>{item.title}</strong>{item.detail && <small>{item.detail}</small>}</span>
      {card.kind === "shopping" && item.sourceId && <button type="button" aria-label={`Mark ${item.title} purchased`} title="Mark purchased"
        disabled={purchasing} onClick={() => purchase(item.sourceId!)}><Check size={16} /></button>}
    </li>)}</ul> : null}
    <div className="phengos-context-actions"><Link className="phengos-context-link" to={card.href} state={{ phengosOriginLayer: "overview" }}>
      {card.kind === "agenda" ? "Open daily plan" : card.kind === "shopping" ? "Open shopping list" : card.kind === "workout" ? "Open training" : card.kind === "meal" ? "Open meal" : card.kind === "fixture" ? "Open match" : card.kind === "proposal" ? "Review or adjust in chat" : "Open calendar"}
      <ArrowUpRight size={16} aria-hidden="true" /></Link>
      {card.action?.kind === "start-workout" && <button className="phengos-context-link phengos-context-link--secondary" type="button"
        disabled={startingWorkout} onClick={() => startWorkout(card.action!.id)}>Start workout</button>}
      {card.action?.kind === "confirm-proposal" && <><button className="phengos-context-link" type="button" disabled={confirmingProposal || cancellingProposal}
        onClick={() => confirmProposal(card.action!.id)}>Approve and save</button>
        <button className="phengos-context-link phengos-context-link--secondary" type="button" disabled={confirmingProposal || cancellingProposal}
          onClick={() => cancelProposal(card.action!.id)}>Decline</button></>}
    </div>
  </motion.article>;
}

function TeamMark({ name, logo }: { name: string; logo?: string }) {
  return <span className="phengos-team-mark">{logo ? <img src={logo} alt="" loading="lazy" /> : <span aria-hidden="true">{name.slice(0, 2).toUpperCase()}</span>}<strong>{name}</strong></span>;
}
