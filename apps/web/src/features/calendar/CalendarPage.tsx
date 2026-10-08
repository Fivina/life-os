import { Check, CircleSlash, Info, Play, Plus, RefreshCw, TimerReset, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { api } from "../../services/api";
import { CalendarWorkspace } from "./CalendarWorkspace";
import { StandingRulesPanel } from "./StandingRulesPanel";

function toIso(date: string, time: string) {
  return new Date(`${date}T${time}:00`).toISOString();
}

function displayTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function displayDate(value?: string | null) {
  if (!value) {
    return "No deadline";
  }
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

export function CalendarPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const requestedCommitmentId = searchParams.get("commitment") || null;
  const tomorrow = useMemo(() => {
    const date = new Date();
    date.setDate(date.getDate() + 1);
    return date.toISOString().slice(0, 10);
  }, []);

  const [commitmentTitle, setCommitmentTitle] = useState("University");
  const [commitmentLevel, setCommitmentLevel] = useState("hard");
  const [commitmentDate, setCommitmentDate] = useState(tomorrow);
  const [commitmentStart, setCommitmentStart] = useState("11:00");
  const [commitmentEnd, setCommitmentEnd] = useState("16:00");
  const [commitmentLocation, setCommitmentLocation] = useState("University");
  const [commitmentNotes, setCommitmentNotes] = useState("");
  const [commitmentError, setCommitmentError] = useState<string | null>(null);

  const [actionTitle, setActionTitle] = useState("Study Macroeconomics");
  const [actionDomain, setActionDomain] = useState("learning");
  const [actionLevel, setActionLevel] = useState("goal_critical");
  const [actionMinutes, setActionMinutes] = useState("120");
  const [actionDeadline, setActionDeadline] = useState(tomorrow);
  const [actionLocation, setActionLocation] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<string[] | null>(null);
  const [modifyMinutes, setModifyMinutes] = useState("90");
  const [proposalError, setProposalError] = useState<string | null>(null);

  const projection = useQuery({
    queryKey: ["calendar-projection"],
    queryFn: api.calendarProjection
  });

  const requestedCommitment = useQuery({
    queryKey: ["commitment", requestedCommitmentId],
    queryFn: () => api.getCommitment(requestedCommitmentId!),
    enabled: Boolean(requestedCommitmentId),
    retry: false
  });

  const currentPlan = useQuery({
    queryKey: ["current-plan"],
    queryFn: () => api.currentPlan()
  });

  const horizon = useQuery({ queryKey: ["plan-horizon"], queryFn: api.horizonAllocations });
  const proposals = useQuery({ queryKey: ["plan-proposals"], queryFn: api.planProposals });

  const refreshPlanning = () => {
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    queryClient.invalidateQueries({ queryKey: ["plan-horizon"] });
    queryClient.invalidateQueries({ queryKey: ["plan-proposals"] });
  };

  const presentProposal = useMutation({ mutationFn: api.presentPlanProposal, onSuccess: refreshPlanning });
  const acceptProposal = useMutation({ mutationFn: api.acceptPlanProposal, onSuccess: refreshPlanning, onError: (error) => setProposalError(error instanceof Error ? error.message : "Could not apply proposal.") });
  const rejectProposal = useMutation({ mutationFn: api.rejectPlanProposal, onSuccess: refreshPlanning });
  const modifyProposal = useMutation({
    mutationFn: ({ id, minutes }: { id: string; minutes: number }) => api.modifyPlanProposal(id, { requested_target_minutes: minutes }),
    onSuccess: refreshPlanning,
    onError: (error) => setProposalError(error instanceof Error ? error.message : "Could not update proposal.")
  });

  const replan = useMutation({ mutationFn: api.replanDay, onSuccess: refreshPlanning });
  const completeBlock = useMutation({
    mutationFn: ({ planId, blockId, version, minutes }: { planId: string; blockId: string; version: number; minutes: number }) =>
      api.completePlanBlock(planId, blockId, version, minutes),
    onSuccess: refreshPlanning
  });
  const startBlock = useMutation({
    mutationFn: ({ planId, blockId, version }: { planId: string; blockId: string; version: number }) => api.startPlanBlock(planId, blockId, version),
    onSuccess: refreshPlanning
  });
  const partialBlock = useMutation({
    mutationFn: ({ planId, blockId, version, minutes }: { planId: string; blockId: string; version: number; minutes: number }) =>
      api.partialCompletePlanBlock(planId, blockId, version, minutes),
    onSuccess: refreshPlanning
  });
  const skipBlock = useMutation({
    mutationFn: ({ planId, blockId, version }: { planId: string; blockId: string; version: number }) => api.skipPlanBlock(planId, blockId, version),
    onSuccess: refreshPlanning
  });
  const cancelBlock = useMutation({
    mutationFn: ({ planId, blockId, version }: { planId: string; blockId: string; version: number }) => api.cancelPlanBlockPlacement(planId, blockId, version),
    onSuccess: refreshPlanning
  });
  const explainBlock = useMutation({
    mutationFn: ({ planId, blockId }: { planId: string; blockId: string }) => api.explainPlanBlock(planId, blockId),
    onSuccess: (data) => setExplanation(data.summary)
  });

  const saveCommitment = useMutation({
    mutationFn: api.addCommitment,
    onSuccess: () => {
      setCommitmentError(null);
      queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    },
    onError: (error) => {
      setCommitmentError(error instanceof Error ? error.message : "Could not save commitment.");
    }
  });

  const saveAction = useMutation({
    mutationFn: api.addAction,
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    },
    onError: (error) => {
      setActionError(error instanceof Error ? error.message : "Could not add intention.");
    }
  });

  const completeAction = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => api.completeAction(id, version),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calendar-projection"] })
  });

  const editCommitment = useMutation({
    mutationFn: ({ id, version, startsAt }: { id: string; version: number; startsAt: string }) =>
      api.updateCommitment(id, { expected_version: version, starts_at: startsAt }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["calendar-projection"] })
  });

  function handleCommitmentSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (commitmentStart >= commitmentEnd) {
      setCommitmentError("Start must be before end.");
      return;
    }
    saveCommitment.mutate({
      title: commitmentTitle,
      level: commitmentLevel,
      commitment_type: commitmentLevel === "hard" ? "hard" : "semi_fixed",
      starts_at: toIso(commitmentDate, commitmentStart),
      ends_at: toIso(commitmentDate, commitmentEnd),
      location: commitmentLocation || null,
      notes: commitmentNotes || null,
      recurrence: { frequency: "none" }
    });
  }

  function handleActionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const minutes = Number(actionMinutes);
    if (!Number.isFinite(minutes) || minutes <= 0) {
      setActionError("Estimated duration must be positive.");
      return;
    }
    saveAction.mutate({
      title: actionTitle,
      domain: actionDomain,
      level: actionLevel,
      estimated_minutes: minutes,
      deadline: actionDeadline ? toIso(actionDeadline, "23:59") : null,
      location: actionLocation || null
    });
  }

  return (
    <div className="stack calendar-page">
      <CalendarWorkspace
        projection={projection.data}
        plan={currentPlan.data}
        horizon={horizon.data}
        proposals={proposals.data}
        requestedCommitmentId={requestedCommitmentId}
        requestedCommitment={requestedCommitment.data}
        requestedCommitmentLoading={requestedCommitment.isLoading}
        requestedCommitmentError={requestedCommitment.isError}
        loading={projection.isLoading || currentPlan.isLoading}
        error={projection.isError || currentPlan.isError}
        onAddCommitment={() => document.getElementById("add-commitment")?.scrollIntoView({ behavior: "smooth", block: "start" })}
        onAddIntention={() => document.getElementById("add-intention")?.scrollIntoView({ behavior: "smooth", block: "start" })}
      />
      <StandingRulesPanel />
      <section className="content-band">
        <div className="section-header">
          <h2 id="daily-list" tabIndex={-1}>Calendar Projection</h2>
          <button className="icon-button" type="button" aria-label="Replan day" title="Replan day" onClick={() => replan.mutate()} disabled={replan.isPending || !currentPlan.data}>
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>
        {projection.isLoading ? <p className="status-text">Loading calendar projection...</p> : null}
        {currentPlan.isLoading ? <p className="status-text">Building today's plan...</p> : null}
        {projection.isError ? <p className="status-text error">Could not load calendar projection.</p> : null}
        {currentPlan.data?.overload_status && currentPlan.data.overload_status !== "feasible" ? (
          <div className="planner-warning" role="status">
            <strong>{currentPlan.data.overload_status.replaceAll("_", " ")}</strong>
            <span>{currentPlan.data.shortfall_minutes ?? 0} minutes cannot currently be placed.</span>
          </div>
        ) : null}
        <div className="timeline">
          {(projection.data?.commitments ?? []).map((item) => (
            <span key={item.canonical_id} className={`timeline-item ${item.level}`}>
              {displayTime(item.starts_at)}-{displayTime(item.ends_at)} {item.title}
              {item.location ? ` · ${item.location}` : ""}
              <button
                type="button"
                className="text-action"
                onClick={() => editCommitment.mutate({ id: item.canonical_id, version: item.version, startsAt: item.starts_at })}
              >
                Save edit
              </button>
            </span>
          ))}
          {(currentPlan.data?.blocks ?? []).map((block) => (
            <span key={block.id} className={`timeline-item ${block.block_type}`} aria-label={`Plan block ${block.title}`}>
              <span>
                {displayTime(block.starts_at)}-{displayTime(block.ends_at)} {block.title}
                {block.domain ? ` · ${block.domain}` : ""}
                {block.variant_type ? ` · ${block.variant_type}` : ""}
                {` · ${block.status.replaceAll("_", " ")}`}
              </span>
              {block.block_type === "generated_action" && ["planned", "in_progress"].includes(block.status) && currentPlan.data ? (
                <span className="timeline-actions">
                  <button className="icon-button" type="button" aria-label={`Why here ${block.title}`} title="Why here?" onClick={() => explainBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id })}><Info size={15} /></button>
                  {block.status === "planned" ? <button className="icon-button" type="button" aria-label={`Start ${block.title}`} title="Start" onClick={() => startBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id, version: block.version })}><Play size={15} /></button> : null}
                  <button className="icon-button" type="button" aria-label={`Complete ${block.title}`} title="Complete" onClick={() => completeBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id, version: block.version, minutes: block.duration_minutes })}><Check size={15} /></button>
                  <button className="icon-button" type="button" aria-label={`Partially complete ${block.title}`} title="Partial completion" onClick={() => partialBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id, version: block.version, minutes: Math.max(1, Math.floor(block.duration_minutes / 2)) })}><TimerReset size={15} /></button>
                  <button className="icon-button" type="button" aria-label={`Skip ${block.title}`} title="Skip" onClick={() => skipBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id, version: block.version })}><CircleSlash size={15} /></button>
                  <button className="icon-button" type="button" aria-label={`Remove placement ${block.title}`} title="Remove placement" onClick={() => cancelBlock.mutate({ planId: currentPlan.data!.id, blockId: block.id, version: block.version })}><X size={15} /></button>
                </span>
              ) : null}
            </span>
          ))}
          {!projection.isLoading &&
          !currentPlan.isLoading &&
          (projection.data?.commitments.length ?? 0) === 0 &&
          (currentPlan.data?.blocks.length ?? 0) === 0 ? (
            <span>No fixed commitments yet.</span>
          ) : null}
        </div>
        {explanation ? <div className="planner-explanation"><strong>Why here?</strong>{explanation.map((item) => <p key={item}>{item}</p>)}</div> : null}
      </section>

      {(proposals.data?.length ?? 0) > 0 ? (
        <section className="content-band strategic-proposals">
          <div className="section-header"><h2 id="plan-proposals">Plan Proposals</h2><span>{proposals.data?.length}</span></div>
          <div className="proposal-list">
            {proposals.data?.map((proposal) => {
              const title = String(proposal.trajectory_snapshot.exam_title ?? "Exam recovery");
              const minutes = proposal.expected_effects.scheduled_minutes;
              const shortfall = proposal.expected_effects.projected_shortfall_minutes;
              return (
                <article className="proposal-panel" key={proposal.id}>
                  <div className="proposal-heading">
                    <div><small>WHY</small><strong>{title}</strong><span>{proposal.reason_code.replaceAll("_", " ")}</span></div>
                    <span className="proposal-status">{proposal.status}</span>
                  </div>
                  <dl>
                    <div><dt>CURRENT</dt><dd>{minutes?.current ?? 0}m scheduled · {shortfall?.current ?? 0}m shortfall</dd></div>
                    <div><dt>PROPOSED</dt><dd>{minutes?.proposed ?? 0}m scheduled · {shortfall?.proposed ?? 0}m shortfall</dd></div>
                    <div><dt>EFFECT</dt><dd>{minutes?.delta && minutes.delta > 0 ? "+" : ""}{minutes?.delta ?? 0}m toward this exam</dd></div>
                    <div><dt>TRADE-OFFS</dt><dd>{proposal.tradeoffs.length ? proposal.tradeoffs.map((item) => String(item.type ?? "allocation change").replaceAll("_", " ")).join(" · ") : "No protected blocks changed"}</dd></div>
                  </dl>
                  <div className="proposal-actions">
                    {proposal.status === "DRAFT" ? <button type="button" className="secondary-button" onClick={() => presentProposal.mutate(proposal.id)}>Review</button> : null}
                    <button type="button" className="primary-button" onClick={() => acceptProposal.mutate(proposal.id)} disabled={acceptProposal.isPending}>Apply</button>
                    <label className="proposal-adjustment">Minutes<input type="number" min="10" max="720" step="15" value={modifyMinutes} onChange={(event) => setModifyMinutes(event.target.value)} /></label>
                    <button type="button" className="secondary-button" onClick={() => modifyProposal.mutate({ id: proposal.id, minutes: Math.max(10, Number(modifyMinutes) || 90) })}>Modify</button>
                    <button type="button" className="text-action" onClick={() => rejectProposal.mutate(proposal.id)}>Reject</button>
                  </div>
                </article>
              );
            })}
          </div>
          {proposalError ? <p className="status-text error">{proposalError}</p> : null}
        </section>
      ) : null}

      {(currentPlan.data?.unscheduled_actions.length ?? 0) > 0 ? (
        <section className="content-band calendar-needs-attention">
          <div className="section-header"><h2>Needs Attention</h2><span>{currentPlan.data?.unscheduled_actions.length}</span></div>
          <div className="pool-list">
            {currentPlan.data?.unscheduled_actions.map((item) => (
              <article className="pool-item" key={item.source_action_id}><div><strong>{item.title}</strong><p className="status-text">{item.reason.replaceAll("_", " ")} · {item.shortfall_minutes ?? item.required_minutes ?? 0}m at risk</p></div></article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="content-band">
        <div className="section-header"><h2>Week Map</h2><span>{horizon.data?.status ?? "loading"}</span></div>
        <div className="allocation-strip">
          {(horizon.data?.allocations ?? []).map((item) => <span key={item.id}><strong>{new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(new Date(`${item.planning_date}T12:00:00`))}</strong>{item.domain} · {item.allocated_minutes}m</span>)}
          {!horizon.isLoading && (horizon.data?.allocations.length ?? 0) === 0 ? <p className="muted">No rolling allocations yet.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2 id="add-commitment">Add Commitment</h2>
          <span>canonical</span>
        </div>
        <form className="compact-form v02-form" onSubmit={handleCommitmentSubmit}>
          <label>
            Title
            <input value={commitmentTitle} onChange={(event) => setCommitmentTitle(event.target.value)} />
          </label>
          <label>
            Level
            <select value={commitmentLevel} onChange={(event) => setCommitmentLevel(event.target.value)}>
              <option value="hard">Hard</option>
              <option value="goal_critical">Goal-critical</option>
              <option value="maintenance">Maintenance</option>
              <option value="optional">Optional</option>
            </select>
          </label>
          <label>
            Date
            <input type="date" value={commitmentDate} onChange={(event) => setCommitmentDate(event.target.value)} />
          </label>
          <label>
            Start
            <input type="time" value={commitmentStart} onChange={(event) => setCommitmentStart(event.target.value)} />
          </label>
          <label>
            End
            <input type="time" value={commitmentEnd} onChange={(event) => setCommitmentEnd(event.target.value)} />
          </label>
          <label>
            Location
            <input value={commitmentLocation} onChange={(event) => setCommitmentLocation(event.target.value)} />
          </label>
          <label>
            Notes
            <input value={commitmentNotes} onChange={(event) => setCommitmentNotes(event.target.value)} />
          </label>
          <button className="primary-button" type="submit" disabled={saveCommitment.isPending}>
            <span>{saveCommitment.isPending ? "Saving" : "Save commitment"}</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        {saveCommitment.isSuccess ? <p className="status-text success">Commitment saved.</p> : null}
        {commitmentError ? <p className="status-text error">Conflict or error: {commitmentError}</p> : null}
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2 id="add-intention">Add Intention</h2>
          <span>unscheduled</span>
        </div>
        <form className="compact-form v02-form" onSubmit={handleActionSubmit}>
          <label>
            Title
            <input value={actionTitle} onChange={(event) => setActionTitle(event.target.value)} />
          </label>
          <label>
            Domain
            <select value={actionDomain} onChange={(event) => setActionDomain(event.target.value)}>
              <option value="learning">Learning</option>
              <option value="fitness">Fitness</option>
              <option value="home">Home</option>
              <option value="kitchen">Kitchen</option>
              <option value="admin">Admin</option>
              <option value="personal">Personal</option>
            </select>
          </label>
          <label>
            Level
            <select value={actionLevel} onChange={(event) => setActionLevel(event.target.value)}>
              <option value="goal_critical">Goal-critical</option>
              <option value="maintenance">Maintenance</option>
              <option value="optional">Optional</option>
            </select>
          </label>
          <label>
            Minutes
            <input value={actionMinutes} onChange={(event) => setActionMinutes(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Deadline
            <input type="date" value={actionDeadline} onChange={(event) => setActionDeadline(event.target.value)} />
          </label>
          <label>
            Context
            <input value={actionLocation} onChange={(event) => setActionLocation(event.target.value)} />
          </label>
          <button className="primary-button" type="submit" disabled={saveAction.isPending}>
            <span>{saveAction.isPending ? "Adding" : "Add intention"}</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        {saveAction.isSuccess ? <p className="status-text success">Intention added to Planning Pool.</p> : null}
        {actionError ? <p className="status-text error">{actionError}</p> : null}
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Planning Pool</h2>
          <span>{projection.data?.planning_pool.length ?? 0}</span>
        </div>
        <div className="pool-list">
          {(projection.data?.planning_pool ?? []).map((item) => (
            <article className="pool-item" key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <p className="status-text">
                  {item.domain} · {item.level} · {item.estimated_minutes ?? "--"}m · {displayDate(item.deadline)}
                </p>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label={`Complete ${item.title}`}
                onClick={() => completeAction.mutate({ id: item.id, version: item.version })}
              >
                <Check size={17} />
              </button>
            </article>
          ))}
          {!projection.isLoading && (projection.data?.planning_pool.length ?? 0) === 0 ? (
            <p className="muted">No unscheduled intentions yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
