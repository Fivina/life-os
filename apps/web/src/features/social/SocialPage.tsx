import { CalendarClock, Check, ExternalLink, MapPin, Plus, RefreshCw, Sparkles, Users, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../services/api";
import type { OpportunityRecommendation } from "../../types/api";

type View = "opportunities" | "activity" | "sources";

export function SocialPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>("opportunities");
  const [category, setCategory] = useState("");
  const [activityTitle, setActivityTitle] = useState("");
  const [sourceCity, setSourceCity] = useState<Record<string, string>>({});
  const trajectory = useQuery({ queryKey: ["social-trajectory"], queryFn: api.socialTrajectory });
  const opportunities = useQuery({ queryKey: ["opportunities", category], queryFn: () => api.opportunities({ category: category || undefined, relevant: true, starts_after: new Date().toISOString() }) });
  const activities = useQuery({ queryKey: ["social-activities"], queryFn: api.socialActivities });
  const sources = useQuery({ queryKey: ["opportunity-sources"], queryFn: api.opportunitySources });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["social-trajectory"] });
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["social-activities"] });
    void queryClient.invalidateQueries({ queryKey: ["opportunity-sources"] });
  };
  const updateTrajectory = useMutation({ mutationFn: api.updateSocialTrajectory, onSuccess: refresh });
  const recommend = useMutation({ mutationFn: api.recommendOpportunities });
  const dismiss = useMutation({ mutationFn: api.dismissOpportunity, onSuccess: refresh });
  const outcome = useMutation({
    mutationFn: ({ recommendation, optionId, result }: { recommendation: OpportunityRecommendation; optionId: string; result: "SELECTED" | "REJECTED" | "EXECUTED" }) =>
      api.recordOpportunityOutcome({ recommendation_id: recommendation.id, option_id: optionId, outcome: result, idempotency_key: crypto.randomUUID() }),
    onSuccess: refresh
  });
  const addActivity = useMutation({ mutationFn: api.addSocialActivity, onSuccess: () => { setActivityTitle(""); refresh(); } });
  const updateSource = useMutation({ mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof api.updateOpportunitySource>[1] }) => api.updateOpportunitySource(id, payload), onSuccess: refresh });
  const discover = useMutation({ mutationFn: api.discoverOpportunities, onSuccess: refresh });

  function submitActivity(event: FormEvent) {
    event.preventDefault();
    if (!activityTitle.trim()) return;
    addActivity.mutate({ activity_type: "SOCIAL_ACTIVITY", title: activityTitle.trim(), occurred_at: new Date().toISOString(), meaningful: true, idempotency_key: crypto.randomUUID() });
  }

  const state = trajectory.data;
  const recommendation = recommend.data;
  return <div className="stack social-page">
    <section className="social-command-band">
      <div><p className="eyebrow">Social trajectory</p><h2>Meaningful activity</h2><p>{state ? `${state.completed_count} this week · target ${state.target_min}${state.target_max !== state.target_min ? `–${state.target_max}` : ""}` : "Loading this week…"}</p></div>
      {state ? <div className="social-target-controls"><label className="toggle-row"><input type="checkbox" checked={state.enabled} onChange={(event) => updateTrajectory.mutate({ enabled: event.target.checked, target_min: state.target_min, target_max: state.target_max, week_starts_on: state.week_starts_on })} /><span>Use weekly target</span></label><label>Target<input aria-label="Weekly social target" type="number" min="0" max="21" value={state.target_min} onChange={(event) => updateTrajectory.mutate({ enabled: state.enabled, target_min: Number(event.target.value), target_max: Math.max(Number(event.target.value), state.target_max), week_starts_on: state.week_starts_on })} /></label></div> : null}
    </section>

    <nav className="segmented-control social-tabs" aria-label="Social views">
      <button className={view === "opportunities" ? "active" : ""} onClick={() => setView("opportunities")}><Sparkles size={15} /> Opportunities</button>
      <button className={view === "activity" ? "active" : ""} onClick={() => setView("activity")}><Users size={15} /> Activity</button>
      <button className={view === "sources" ? "active" : ""} onClick={() => setView("sources")}><RefreshCw size={15} /> Sources</button>
    </nav>

    {view === "opportunities" ? <section className="content-band">
      <div className="section-header"><div><h2>Worth considering</h2><span>Relevant and calendar-aware</span></div><button className="primary-button" onClick={() => recommend.mutate()} disabled={recommend.isPending}><Sparkles size={16} /> Refresh picks</button></div>
      <div className="social-filter"><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All relevant</option><option value="CONCERT">Concerts</option><option value="FOOTBALL">Football</option><option value="EXHIBITION">Exhibitions</option><option value="FESTIVAL">Festivals</option><option value="WORKSHOP">Workshops</option><option value="SPORT">Sport</option></select></label></div>
      {recommendation ? <div className="opportunity-list">{recommendation.options.map((option) => <article className="opportunity-row recommended" key={option.id}><OpportunityCopy title={option.label} reasons={option.payload_json.reasons} /><div className="opportunity-actions"><button className="icon-button" title="Interested" aria-label={`Interested in ${option.label}`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "SELECTED" })}><Check size={17} /></button><button className="icon-button" title="Attended" aria-label={`Mark ${option.label} attended`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "EXECUTED" })}><Users size={17} /></button><button className="icon-button" title="Not for me" aria-label={`Dismiss ${option.label}`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "REJECTED" })}><X size={17} /></button></div></article>)}</div> : null}
      <div className="opportunity-list">{(opportunities.data ?? []).map((item) => <article className="opportunity-row" key={item.id}><OpportunityCopy title={item.title} startsAt={item.starts_at} venue={item.venue} city={item.city} cost={formatCost(item.cost_min, item.currency)} reasons={item.reasons} feasibility={item.feasibility.status} /><div className="opportunity-actions">{item.source_url ? <a className="icon-button" href={item.source_url} target="_blank" rel="noreferrer" title="View source" aria-label={`View ${item.title} source`}><ExternalLink size={17} /></a> : null}<button className="icon-button" title="Not for me" aria-label={`Dismiss ${item.title}`} onClick={() => dismiss.mutate(item.id)}><X size={17} /></button></div></article>)}</div>
      {!opportunities.isLoading && !opportunities.data?.length ? <p className="status-text">No relevant opportunities are ready yet. Configure a source or keep an explicit future interest.</p> : null}
    </section> : null}

    {view === "activity" ? <section className="content-band"><div className="section-header"><h2>Meaningful activity</h2><span>{activities.data?.length ?? 0} recorded</span></div><form className="social-activity-form" onSubmit={submitActivity}><input aria-label="Activity title" placeholder="Dinner with friends" value={activityTitle} onChange={(event) => setActivityTitle(event.target.value)} /><button className="icon-button" title="Add activity" aria-label="Add meaningful activity"><Plus size={18} /></button></form><div className="social-activity-list">{(activities.data ?? []).map((item) => <article key={item.id}><time>{formatDate(item.occurred_at)}</time><div><strong>{item.title}</strong><small>{item.activity_type.replaceAll("_", " ").toLowerCase()}</small></div></article>)}</div></section> : null}

    {view === "sources" ? <section className="content-band"><div className="section-header"><h2>Discovery sources</h2><span>City-level context only</span></div><div className="source-list">{(sources.data ?? []).map((source) => <article className="source-row" key={source.id}><div><strong>{source.source_id === "ticketmaster" ? "Ticketmaster Discovery" : source.source_id}</strong><small>{source.configured ? source.last_status.toLowerCase() : "API key not configured"}{source.last_discovery_at ? ` · ${formatDate(source.last_discovery_at)}` : ""}</small></div><input aria-label={`${source.source_id} city`} placeholder="City" value={sourceCity[source.id] ?? source.city ?? ""} onChange={(event) => setSourceCity((current) => ({ ...current, [source.id]: event.target.value }))} /><label className="toggle-row"><input type="checkbox" checked={source.enabled} disabled={!source.configured} onChange={(event) => updateSource.mutate({ id: source.source_id, payload: { enabled: event.target.checked, city: sourceCity[source.id] ?? source.city, country_code: source.country_code, categories: source.categories, cadence_minutes: source.cadence_minutes, horizon_days: source.horizon_days } })} /><span>Enabled</span></label><button className="icon-button" title="Discover now" aria-label={`Run ${source.source_id} discovery`} disabled={!source.configured || discover.isPending} onClick={() => discover.mutate(source.source_id)}><RefreshCw size={17} /></button></article>)}</div></section> : null}
  </div>;
}

function OpportunityCopy({ title, startsAt, venue, city, cost, reasons = [], feasibility }: { title: string; startsAt?: string; venue?: string | null; city?: string | null; cost?: string | null; reasons?: string[]; feasibility?: string }) {
  return <div className="opportunity-copy"><div className="opportunity-title"><span className="opportunity-mark" aria-hidden="true"><Sparkles size={14} /></span><div><strong>{title}</strong>{startsAt ? <small><CalendarClock size={13} /> {formatDateTime(startsAt)}</small> : null}</div></div>{venue || city ? <p><MapPin size={13} /> {[venue, city].filter(Boolean).join(" · ")}</p> : null}<div className="opportunity-meta">{cost ? <span>{cost}</span> : <span>Price unknown</span>}{feasibility ? <span>{friendlyFeasibility(feasibility)}</span> : null}</div>{reasons.length ? <ul>{reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}</ul> : null}</div>;
}

function formatDateTime(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)); }
function formatCost(value?: string | number | null, currency?: string | null) { return value == null ? null : new Intl.NumberFormat(undefined, { style: "currency", currency: currency || "EUR" }).format(Number(value)); }
function friendlyFeasibility(value: string) { return value === "CLEAN_SLOT" ? "Calendar clear" : value === "PROPOSAL_ELIGIBLE" ? "Needs a plan proposal" : "Calendar conflict"; }
