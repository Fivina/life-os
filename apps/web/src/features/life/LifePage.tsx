import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CircleDot, Milestone, Plus, WalletCards } from "lucide-react";
import { FormEvent, useState } from "react";

import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)) : "No target date";
}

function recurrenceLabel(recurrence: Record<string, unknown>) {
  const kind = String(recurrence.type ?? "weekly").replaceAll("_", " ");
  const interval = Number(recurrence.interval ?? recurrence.days ?? 1);
  return interval > 1 ? `${kind} · every ${interval}` : kind;
}

export function LifePage() {
  const queryClient = useQueryClient();
  const [goalTitle, setGoalTitle] = useState("");
  const [goalDomain, setGoalDomain] = useState("personal");
  const [goalDate, setGoalDate] = useState("");
  const [choreTitle, setChoreTitle] = useState("Laundry");
  const [choreDays, setChoreDays] = useState("7");
  const [choreMinutes, setChoreMinutes] = useState("45");

  const goals = useQuery({ queryKey: ["goals-overview"], queryFn: api.goalsOverview });
  const household = useQuery({ queryKey: ["household-overview"], queryFn: api.householdOverview });

  const refreshLife = () => {
    queryClient.invalidateQueries({ queryKey: ["goals-overview"] });
    queryClient.invalidateQueries({ queryKey: ["household-overview"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
  };

  const createGoal = useMutation({ mutationFn: api.createGoal, onSuccess: refreshLife });
  const createChore = useMutation({ mutationFn: api.createHouseholdTask, onSuccess: refreshLife });
  const completeChore = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => api.completeHouseholdTask(id, version),
    onSuccess: refreshLife
  });

  const activeGoals = (goals.data?.goals ?? []).filter((goal) => goal.active && goal.status === "active");
  const dueTasks = household.data?.due ?? [];

  function submitGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!goalTitle.trim()) return;
    createGoal.mutate({
      title: goalTitle.trim(),
      domain: goalDomain,
      target_date: goalDate || null,
      priority: 60,
      progress_mode: "manual"
    });
    setGoalTitle("");
  }

  function submitChore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const days = Math.max(1, Number(choreDays));
    const minutes = Math.max(5, Number(choreMinutes));
    createChore.mutate({
      title: choreTitle,
      recurrence: { type: "interval", days },
      estimated_duration_minutes: minutes,
      minimum_duration_minutes: Math.min(minutes, Math.max(10, Math.round(minutes / 2))),
      location: "home",
      priority: 50
    });
  }

  return (
    <div className="stack life-overview">
      <a className="settings-action" href="/finance"><WalletCards size={18} /><span>Open Finance</span></a>
      <section className="stat-grid" aria-label="Life trajectory summary">
        <StatTile label="Active goals" value={`${activeGoals.length}`} tone="blue" />
        <StatTile label="On track" value={`${activeGoals.filter((goal) => goal.trajectory?.on_track).length}`} tone="green" />
        <StatTile label="Due at home" value={`${dueTasks.length}`} tone="amber" />
        <StatTile label="Weekly focus" value={`${goals.data?.weekly_focus.length ?? 0}`} tone="rose" />
      </section>

      <section className="content-band">
        <div className="section-header"><h2 id="goals" tabIndex={-1}>Goals & Trajectories</h2><Milestone size={18} aria-hidden="true" /></div>
        <div className="trajectory-list">
          {activeGoals.map((goal) => (
            <article className="trajectory-row" key={goal.id}>
              <CircleDot size={16} aria-hidden="true" />
              <div>
                <strong>{goal.title}</strong>
                <small>{goal.domain} · {goal.trajectory?.status.replaceAll("_", " ") ?? "insufficient data"} · {formatDate(goal.target_date)}</small>
                {goal.trajectory?.current_value != null ? (
                  <div className="progress-line" aria-label={`${goal.title} progress`}><span style={{ width: `${Math.min(100, Math.max(0, goal.progress ?? goal.trajectory.current_value))}%` }} /></div>
                ) : null}
              </div>
              <span>{goal.trajectory?.risk ?? "unknown"}</span>
            </article>
          ))}
          {!goals.isLoading && activeGoals.length === 0 ? <p className="status-text">No active goals yet.</p> : null}
          {goals.isError ? <p className="status-text error">Could not load goals.</p> : null}
        </div>
        <form className="compact-form v02-form" onSubmit={submitGoal}>
          <label>Goal<input value={goalTitle} onChange={(event) => setGoalTitle(event.target.value)} placeholder="Meaningful outcome" /></label>
          <label>Domain<select value={goalDomain} onChange={(event) => setGoalDomain(event.target.value)}><option value="personal">Personal</option><option value="learning">Learning</option><option value="fitness">Fitness</option><option value="home">Home</option></select></label>
          <label>Target date<input type="date" value={goalDate} onChange={(event) => setGoalDate(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={createGoal.isPending || !goalTitle.trim()}><span>Add goal</span><Plus size={16} /></button>
        </form>
      </section>

      <section className="content-band">
        <div className="section-header"><h2 id="household" tabIndex={-1}>Household</h2><span>{household.data?.active_count ?? 0} recurring</span></div>
        <div className="trajectory-list">
          {dueTasks.map((task) => (
            <article className="trajectory-row" key={task.id}>
              <CircleDot size={16} aria-hidden="true" />
              <div><strong>{task.title}</strong><small>{task.due_status} · {task.estimated_duration_minutes}m · {recurrenceLabel(task.recurrence)}</small></div>
              <button className="icon-button" type="button" aria-label={`Complete ${task.title}`} title="Complete" onClick={() => completeChore.mutate({ id: task.id, version: task.version })}><Check size={16} /></button>
            </article>
          ))}
          {(household.data?.upcoming ?? []).slice(0, 5).map((task) => (
            <article className="trajectory-row" key={task.id}><CircleDot size={16} aria-hidden="true" /><div><strong>{task.title}</strong><small>Due {formatDate(task.next_due_at)} · {recurrenceLabel(task.recurrence)}</small></div><span>{task.estimated_duration_minutes}m</span></article>
          ))}
          {!household.isLoading && (household.data?.active_count ?? 0) === 0 ? <p className="status-text">No recurring household tasks.</p> : null}
        </div>
        <form className="compact-form v02-form" onSubmit={submitChore}>
          <label>Task<input value={choreTitle} onChange={(event) => setChoreTitle(event.target.value)} /></label>
          <label>Every days<input inputMode="numeric" value={choreDays} onChange={(event) => setChoreDays(event.target.value)} /></label>
          <label>Minutes<input inputMode="numeric" value={choreMinutes} onChange={(event) => setChoreMinutes(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={createChore.isPending}><span>Add recurrence</span><Plus size={16} /></button>
        </form>
      </section>
    </div>
  );
}
