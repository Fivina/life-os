import { Check, Play, RefreshCw, Send, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { ConsistencyHeatmap } from "../../components/ConsistencyHeatmap";
import { MetricSlider } from "../../components/MetricSlider";
import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";
import type { FitnessStatus, KitchenStatus, LatestState, LearningStatus, PlanBlock, PlanDiff, StateObservationBatch } from "../../types/api";

function formatTimestamp(timestamp?: string | null) {
  if (!timestamp) {
    return null;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(timestamp));
}

function displayTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function displayLabel(value?: string | null) {
  if (!value) {
    return "Planner";
  }
  return value.replaceAll("_", " ");
}

function blockMoment(block: PlanBlock) {
  if (["completed", "skipped", "missed"].includes(block.status)) {
    return "past";
  }
  if (block.status === "in_progress") {
    return "now";
  }
  const now = Date.now();
  const starts = new Date(block.starts_at).getTime();
  const ends = new Date(block.ends_at).getTime();
  if (starts <= now && now <= ends) {
    return "now";
  }
  return starts > now ? "upcoming" : "past";
}

function diffLine(diff?: PlanDiff | null) {
  if (!diff) {
    return null;
  }
  const parts = [
    diff.shortened_blocks.length ? `${diff.shortened_blocks.length} shortened` : null,
    diff.moved_blocks.length ? `${diff.moved_blocks.length} moved` : null,
    diff.deferred_action_ids.length ? `${diff.deferred_action_ids.length} deferred` : null,
    diff.added_blocks.length ? `${diff.added_blocks.length} added` : null
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Plan kept stable";
}

function latestStateFromBatch(batch: StateObservationBatch): LatestState {
  const values = Object.fromEntries(batch.observations.map((observation) => [observation.observation_type, observation]));
  const energy = values.energy?.value;
  const mentalState = values.mental_state?.value;
  const observedAtValues = batch.observations.map((observation) => observation.observed_at);

  return {
    values,
    check_in:
      energy == null && mentalState == null
        ? null
        : {
            energy: energy == null ? null : Math.round(energy),
            mental_state: mentalState == null ? null : Math.round(mentalState),
            observed_at: observedAtValues.sort().at(-1) ?? null,
            observation_ids: Object.fromEntries(
              batch.observations.map((observation) => [observation.observation_type, observation.id])
            )
          },
    world_revision: batch.world_revision
  };
}

export function HomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [energy, setEnergy] = useState(45);
  const [mentalState, setMentalState] = useState(52);
  const [planDiff, setPlanDiff] = useState<PlanDiff | null>(null);
  const [controlMessage, setControlMessage] = useState<string | null>(null);

  const latestState = useQuery({
    queryKey: ["latest-state"],
    queryFn: api.latestState
  });

  const currentPlan = useQuery({
    queryKey: ["current-plan"],
    queryFn: () => api.currentPlan()
  });

  const fitnessStatus = useQuery<FitnessStatus>({
    queryKey: ["fitness-status"],
    queryFn: api.fitnessStatus
  });

  const learningStatus = useQuery<LearningStatus>({
    queryKey: ["learning-status"],
    queryFn: api.learningStatus
  });

  const kitchenStatus = useQuery<KitchenStatus>({
    queryKey: ["kitchen-status"],
    queryFn: api.kitchenStatus
  });

  const generatePlan = useMutation({
    mutationFn: () => api.generatePlan(),
    onSuccess: (plan) => {
      queryClient.setQueryData(["current-plan"], plan);
      setPlanDiff(null);
      queryClient.invalidateQueries({ queryKey: ["current-plan"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    }
  });

  const evaluateDay = useMutation({
    mutationFn: api.evaluateDay,
    onSuccess: (status) => {
      if (status.plan) {
        queryClient.setQueryData(["current-plan"], status.plan);
      }
      setPlanDiff(status.plan_diff ?? null);
      setControlMessage(
        status.control_status === "kept"
          ? "State updated. Plan unchanged."
          : status.control_status === "replanned" || status.control_status === "repaired"
            ? "Plan adjusted."
            : status.control_status === "update_suggested"
              ? "Plan update available."
              : null
      );
      queryClient.invalidateQueries({ queryKey: ["current-plan"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    }
  });

  const saveState = useMutation({
    mutationFn: api.createStateObservations,
    onSuccess: (batch) => {
      queryClient.setQueryData(["latest-state"], latestStateFromBatch(batch));
      queryClient.invalidateQueries({ queryKey: ["latest-state"] });
      evaluateDay.mutate();
    }
  });

  const replanDay = useMutation({
    mutationFn: api.replanDay,
    onSuccess: (response) => {
      if (response.plan) {
        queryClient.setQueryData(["current-plan"], response.plan);
      }
      setPlanDiff(response.plan_diff);
      setControlMessage(response.control_status === "replanned" ? "Plan adjusted." : "Plan unchanged.");
      queryClient.invalidateQueries({ queryKey: ["current-plan"] });
      queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    }
  });

  const startBlock = useMutation({
    mutationFn: (block: PlanBlock) => api.startPlanBlock(currentPlan.data?.id ?? "", block.id, block.version),
    onSuccess: (plan) => queryClient.setQueryData(["current-plan"], plan)
  });

  const completeBlock = useMutation({
    mutationFn: (block: PlanBlock) => api.completePlanBlock(currentPlan.data?.id ?? "", block.id, block.version, block.duration_minutes),
    onSuccess: (plan) => queryClient.setQueryData(["current-plan"], plan)
  });

  const skipBlock = useMutation({
    mutationFn: (block: PlanBlock) => api.skipPlanBlock(currentPlan.data?.id ?? "", block.id, block.version, "other"),
    onSuccess: (plan) => {
      queryClient.setQueryData(["current-plan"], plan);
      evaluateDay.mutate();
    }
  });

  useEffect(() => {
    const checkIn = latestState.data?.check_in;
    if (!checkIn) {
      return;
    }
    if (checkIn.energy != null) {
      setEnergy(checkIn.energy);
    }
    if (checkIn.mental_state != null) {
      setMentalState(checkIn.mental_state);
    }
  }, [latestState.data?.check_in]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    saveState.mutate({ energy, mental_state: mentalState });
  }

  function handleAssistantSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = String(new FormData(event.currentTarget).get("q") ?? "").trim();
    navigate(query ? `/self/assistant?q=${encodeURIComponent(query)}` : "/self/assistant");
  }

  const latestEnergy = latestState.data?.check_in?.energy;
  const latestMental = latestState.data?.check_in?.mental_state;
  const latestRecordedAt = useMemo(
    () => formatTimestamp(latestState.data?.check_in?.observed_at),
    [latestState.data?.check_in?.observed_at]
  );
  const planBlocks = useMemo(
    () =>
      [...(currentPlan.data?.blocks ?? [])].sort(
        (left: PlanBlock, right: PlanBlock) => new Date(left.starts_at).getTime() - new Date(right.starts_at).getTime()
      ),
    [currentPlan.data?.blocks]
  );
  const fitnessBlock = planBlocks.find((block) => block.domain === "fitness" && !["completed", "skipped", "missed"].includes(block.status));
  const learningBlock = planBlocks.find((block) => block.domain === "learning" && !["completed", "skipped", "missed"].includes(block.status));
  const kitchenBlock = planBlocks.find((block) => block.domain === "kitchen" && !["completed", "skipped", "missed"].includes(block.status));

  return (
    <div className="stack self-core-summary">
      <form className="ask-bar core-command" action="/self/assistant" method="get" onSubmit={handleAssistantSubmit}>
        <input aria-label="Ask or add something" name="q" placeholder="Ask Life OS..." />
        <button className="icon-button" type="submit" aria-label="Send">
          <Send size={18} />
        </button>
      </form>

      <section className="morning-band" aria-labelledby="morning-title">
        <div>
          <p className="eyebrow">Good morning</p>
          <h2 id="morning-title">Current State Check-in</h2>
          {latestState.isLoading ? <p className="status-text">Loading latest check-in...</p> : null}
          {latestState.isError ? <p className="status-text error">Could not load the latest check-in.</p> : null}
          {!latestState.isLoading && !latestState.isError && !latestState.data?.check_in ? (
            <p className="status-text">No previous check-in yet.</p>
          ) : null}
          {latestRecordedAt ? <p className="status-text">Last recorded {latestRecordedAt}</p> : null}
        </div>
        <form className="state-form" onSubmit={handleSubmit}>
          <MetricSlider label="Energy" value={energy} onChange={setEnergy} />
          <MetricSlider label="Mental state" value={mentalState} onChange={setMentalState} />
          <button className="primary-button" type="submit" disabled={saveState.isPending}>
            <span>{saveState.isPending ? "Saving" : "Save check-in"}</span>
            <Send size={17} aria-hidden="true" />
          </button>
          {saveState.isSuccess ? <p className="status-text success">Check-in saved.</p> : null}
          {controlMessage ? <p className="status-text success">{controlMessage}</p> : null}
          {saveState.isError ? <p className="status-text error">Could not save check-in.</p> : null}
        </form>
      </section>

      <section className="stat-grid" aria-label="Current status">
        <StatTile label="Energy" value={latestEnergy == null ? "--" : `${Math.round(latestEnergy)}`} tone="blue" />
        <StatTile label="Mind" value={latestMental == null ? "--" : `${Math.round(latestMental)}`} tone="green" />
        <StatTile label="Calories" value={kitchenStatus.data?.nutrition.calories_remaining == null ? "--" : `${Math.round(kitchenStatus.data.nutrition.calories_remaining)}`} tone="amber" />
        <StatTile label="Revision" value={`${latestState.data?.world_revision ?? 0}`} tone="rose" />
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Today Plan</h2>
          <span>{currentPlan.data?.planner_version ?? "v0.3"}</span>
        </div>
        <div className="plan-toolbar">
          <div>
            {currentPlan.isLoading ? <p className="status-text">Loading current plan...</p> : null}
            {currentPlan.isError ? <p className="status-text error">Could not load the current plan.</p> : null}
            {!currentPlan.isLoading && !currentPlan.isError && !currentPlan.data ? (
              <p className="status-text">No generated plan for today yet.</p>
            ) : null}
            {currentPlan.data ? (
              <p className="status-text">
                Generated from world revision {currentPlan.data.generated_from_world_revision} · load{" "}
                {currentPlan.data.summary_metrics.planning_load} / {currentPlan.data.summary_metrics.stress_estimate}
              </p>
            ) : null}
          </div>
          <button className="primary-button" type="button" onClick={() => generatePlan.mutate()} disabled={generatePlan.isPending}>
            <span>{generatePlan.isPending ? "Generating" : "Generate today's plan"}</span>
            <Send size={17} aria-hidden="true" />
          </button>
          <button className="secondary-button" type="button" onClick={() => replanDay.mutate()} disabled={replanDay.isPending || !currentPlan.data}>
            <span>{replanDay.isPending ? "Replanning" : "Replan remaining day"}</span>
            <RefreshCw size={16} aria-hidden="true" />
          </button>
        </div>
        {generatePlan.isSuccess ? <p className="status-text success">Plan generated.</p> : null}
        {generatePlan.isError ? <p className="status-text error">Plan could not be generated. Refresh and try again.</p> : null}
        {replanDay.isError ? <p className="status-text error">Could not replan the day.</p> : null}
        {planDiff ? (
          <div className="plan-diff" aria-label="Plan change summary">
            <strong>{controlMessage ?? "Plan update"}</strong>
            <span>{planDiff.trigger.replaceAll("_", " ")}</span>
            <p>{diffLine(planDiff)}</p>
          </div>
        ) : null}
      </section>

      {currentPlan.data ? (
        <section className="stat-grid" aria-label="Plan summary">
          <StatTile label="Flexible" value={`${currentPlan.data.summary_metrics.flexible_work_minutes}m`} tone="blue" />
          <StatTile label="Hard" value={`${currentPlan.data.summary_metrics.hard_commitment_minutes}m`} tone="rose" />
          <StatTile label="Slack" value={`${currentPlan.data.summary_metrics.slack_minutes}m`} tone="green" />
          <StatTile label="Pool" value={`${currentPlan.data.summary_metrics.actions_unscheduled}`} tone="amber" />
        </section>
      ) : null}

      <section className="split-grid">
        <article className="content-band">
          <div className="section-header">
            <h2>Learning</h2>
            <span>{learningStatus.data?.active_exam?.trajectory?.risk ?? "setup"}</span>
          </div>
          <a className="text-action" href="/learning">
            Open Learning
          </a>
          <p className="status-text">
            {learningStatus.data?.active_exam?.title ?? "No active exam"} · Readiness{" "}
            {learningStatus.data?.active_exam?.trajectory?.readiness_score ?? "--"} · Remaining{" "}
            {learningStatus.data?.active_exam?.trajectory
              ? `${Math.round(learningStatus.data.active_exam.trajectory.remaining_quality_adjusted_minutes / 60)}h`
              : "--"}
          </p>
          <p className="status-text">
            Pace:{" "}
            {learningStatus.data?.active_exam?.trajectory
              ? `${Math.round(learningStatus.data.active_exam.trajectory.required_daily_minutes)}m/day`
              : "--"}
            {learningBlock ? ` · Study today ${displayTime(learningBlock.starts_at)}` : ""}
          </p>
          <div className="progress-line">
            <span
              style={{
                width: `${Math.min(100, Math.max(0, learningStatus.data?.active_exam?.trajectory?.readiness_score ?? 0))}%`
              }}
            />
          </div>
        </article>
        <article className="content-band">
          <div className="section-header">
            <h2>Fitness Progress</h2>
            <span>{fitnessStatus.data?.readiness.band ?? "steady"}</span>
          </div>
          <a className="text-action" href="/fitness">
            Open Fitness
          </a>
          <p className="status-text">
            Next: {fitnessStatus.data?.next_workout?.name ?? "--"} · Recovery: {fitnessStatus.data?.readiness.band ?? "--"} · This week:{" "}
            {fitnessStatus.data?.workouts_this_week ?? 0} / {fitnessStatus.data?.weekly_target ?? 4}
          </p>
          <p className="status-text">
            Weight trend:{" "}
            {fitnessStatus.data?.body_trend.weight.rolling_average == null
              ? "--"
              : `${fitnessStatus.data.body_trend.weight.rolling_average} kg`}
            {fitnessBlock ? ` · Today ${displayTime(fitnessBlock.starts_at)} ${fitnessBlock.title}` : ""}
          </p>
        </article>
        <article className="content-band">
          <div className="section-header">
            <h2>Kitchen</h2>
            <span>{kitchenStatus.data?.shopping_need_count ?? 0} needs</span>
          </div>
          <a className="text-action" href="/kitchen">
            Open Kitchen
          </a>
          <p className="status-text">
            {kitchenStatus.data?.top_recommendation?.recipe.name ?? "No meal recommendation yet"} · Protein left{" "}
            {kitchenStatus.data?.nutrition.protein_g_remaining == null ? "--" : `${Math.round(kitchenStatus.data.nutrition.protein_g_remaining)}g`}
          </p>
          <p className="status-text">
            Inventory {kitchenStatus.data?.inventory_count ?? 0} · Expiring lots {kitchenStatus.data?.expiring_lots ?? 0}
            {kitchenBlock ? ` · Shopping ${displayTime(kitchenBlock.starts_at)}` : ""}
          </p>
        </article>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Consistency</h2>
          <span>35 days</span>
        </div>
        <ConsistencyHeatmap />
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Today Timeline</h2>
          <span>{planBlocks.length ? "current" : "empty"}</span>
        </div>
        <div className="timeline">
          {planBlocks.map((block) => (
            <article key={block.id} className={`timeline-item ${block.block_type} ${blockMoment(block)}`}>
              <div>
                <strong>
                  {displayTime(block.starts_at)}-{displayTime(block.ends_at)} {block.title}
                </strong>
                <small>
                  {blockMoment(block)} · {block.status.replaceAll("_", " ")} · {displayLabel(block.domain)} ·{" "}
                  {displayLabel(block.commitment_level ?? block.block_type)}
                  {!block.movable ? " · fixed" : ""}
                </small>
              </div>
              {block.block_type === "generated_action" && ["planned", "in_progress"].includes(block.status) ? (
                <div className="execution-actions">
                  {block.status === "planned" ? (
                    <button className="icon-button" type="button" aria-label={`Start ${block.title}`} onClick={() => startBlock.mutate(block)}>
                      <Play size={15} />
                    </button>
                  ) : null}
                  <button className="icon-button" type="button" aria-label={`Complete ${block.title}`} onClick={() => completeBlock.mutate(block)}>
                    <Check size={15} />
                  </button>
                  <button className="icon-button" type="button" aria-label={`Skip ${block.title}`} onClick={() => skipBlock.mutate(block)}>
                    <X size={15} />
                  </button>
                </div>
              ) : null}
            </article>
          ))}
          {!currentPlan.isLoading && planBlocks.length === 0 ? <span>No plan blocks yet.</span> : null}
        </div>
        {skipBlock.isError ? <p className="status-text error">Could not skip this block.</p> : null}
      </section>
    </div>
  );
}
