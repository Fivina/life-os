import { Check, Dumbbell, Pause, Play, Plus, RotateCcw, Square, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";
import type { ProgressionState, WorkoutSession, WorkoutTemplateExercise } from "../../types/api";

function displayNumber(value?: number | null, suffix = "") {
  return value == null ? "--" : `${Math.round(value * 10) / 10}${suffix}`;
}

function setsFor(session: WorkoutSession | null | undefined, templateExerciseId?: string) {
  if (!session || !templateExerciseId) {
    return [];
  }
  return session.sets.filter((set) => set.template_exercise_id === templateExerciseId);
}

function progressionFor(items: ProgressionState[], templateExerciseId?: string) {
  return items.find((item) => item.template_exercise_id === templateExerciseId);
}

function formatTimer(seconds: number) {
  const minutes = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const remaining = Math.max(0, seconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${remaining}`;
}

export function FitnessPage() {
  const queryClient = useQueryClient();
  const [programName, setProgramName] = useState("Hypertrophy 4-Day");
  const [templateName, setTemplateName] = useState("Upper A");
  const [templateMinutes, setTemplateMinutes] = useState("75");
  const [exerciseName, setExerciseName] = useState("Bench Press");
  const [exerciseRest, setExerciseRest] = useState("120");
  const [targetSets, setTargetSets] = useState("3");
  const [targetRepMin, setTargetRepMin] = useState("8");
  const [targetRepMax, setTargetRepMax] = useState("10");
  const [targetLoad, setTargetLoad] = useState("70");
  const [targetRpe, setTargetRpe] = useState("8.5");
  const [loadIncrement, setLoadIncrement] = useState("2.5");
  const [weight, setWeight] = useState("78.3");
  const [bodyFat, setBodyFat] = useState("17.2");
  const [soreness, setSoreness] = useState("25");
  const [sleepQuality, setSleepQuality] = useState("75");
  const [stress, setStress] = useState("35");
  const [reps, setReps] = useState("10");
  const [load, setLoad] = useState("70");
  const [rpe, setRpe] = useState("8");
  const [sessionDifficulty, setSessionDifficulty] = useState("8");
  const [restUntil, setRestUntil] = useState<number | null>(null);
  const [restPaused, setRestPaused] = useState(false);
  const [timerNow, setTimerNow] = useState(Date.now());

  const status = useQuery({ queryKey: ["fitness-status"], queryFn: api.fitnessStatus });
  const programs = useQuery({ queryKey: ["fitness-programs"], queryFn: api.fitnessPrograms });
  const templates = useQuery({ queryKey: ["fitness-templates"], queryFn: api.fitnessTemplates });
  const exercises = useQuery({ queryKey: ["fitness-exercises"], queryFn: api.fitnessExercises });

  const activeSession = status.data?.active_session ?? null;
  const nextWorkout = status.data?.next_workout ?? templates.data?.[0] ?? null;
  const templateExercises = activeSession?.template?.exercises ?? nextWorkout?.exercises ?? [];
  const currentTemplateExercise = useMemo(() => {
    if (!activeSession?.template) {
      return null;
    }
    return (
      activeSession.template.exercises.find((item) => setsFor(activeSession, item.id).length < item.target_sets) ??
      activeSession.template.exercises.at(-1) ??
      null
    );
  }, [activeSession]);
  const currentSetCount = setsFor(activeSession, currentTemplateExercise?.id).length;
  const currentSetNumber = currentSetCount + 1;
  const currentProgression = progressionFor(activeSession?.progression ?? status.data?.progression ?? [], currentTemplateExercise?.id);
  const remainingRestSeconds = restUntil && !restPaused ? Math.max(0, Math.ceil((restUntil - timerNow) / 1000)) : 0;

  useEffect(() => {
    const timer = window.setInterval(() => setTimerNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!activeSession?.id) {
      setRestUntil(null);
      return;
    }
    const saved = window.localStorage.getItem(`fitness-rest-${activeSession.id}`);
    if (saved) {
      setRestUntil(Number(saved));
    }
  }, [activeSession?.id]);

  useEffect(() => {
    if (!activeSession?.id || !restUntil) {
      return;
    }
    window.localStorage.setItem(`fitness-rest-${activeSession.id}`, String(restUntil));
  }, [activeSession?.id, restUntil]);

  useEffect(() => {
    if (!currentTemplateExercise) {
      return;
    }
    setReps(String(currentTemplateExercise.target_rep_max));
    const suggestedLoad = currentProgression?.recommended_load_kg ?? currentTemplateExercise.target_load_kg ?? 0;
    setLoad(String(suggestedLoad));
    setRpe(String(currentTemplateExercise.target_rpe ?? 8));
  }, [currentTemplateExercise?.id, currentProgression?.recommended_load_kg]);

  function refreshFitness() {
    queryClient.invalidateQueries({ queryKey: ["fitness-status"] });
    queryClient.invalidateQueries({ queryKey: ["fitness-programs"] });
    queryClient.invalidateQueries({ queryKey: ["fitness-templates"] });
    queryClient.invalidateQueries({ queryKey: ["fitness-exercises"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
  }

  const createProgram = useMutation({ mutationFn: api.createFitnessProgram, onSuccess: refreshFitness });
  const createExercise = useMutation({ mutationFn: api.createFitnessExercise, onSuccess: refreshFitness });
  const createTemplate = useMutation({ mutationFn: api.createFitnessTemplate, onSuccess: refreshFitness });
  const addTemplateExercise = useMutation({
    mutationFn: ({ templateId, exerciseId }: { templateId: string; exerciseId: string }) =>
      api.addFitnessTemplateExercise(templateId, {
        exercise_id: exerciseId,
        order_index: templateExercises.length,
        target_sets: Number(targetSets),
        target_rep_min: Number(targetRepMin),
        target_rep_max: Number(targetRepMax),
        target_load_kg: Number(targetLoad),
        target_rpe: Number(targetRpe),
        rest_seconds: Number(exerciseRest),
        load_increment_kg: Number(loadIncrement)
      }),
    onSuccess: refreshFitness
  });
  const startWorkout = useMutation({
    mutationFn: (templateId: string) => api.startWorkout({ workout_template_id: templateId }),
    onSuccess: refreshFitness
  });
  const logSet = useMutation({
    mutationFn: (item: WorkoutTemplateExercise) =>
      api.logWorkoutSet(activeSession?.id ?? "", {
        template_exercise_id: item.id,
        reps: Number(reps),
        load_kg: Number(load),
        rpe: Number(rpe)
      }),
    onSuccess: () => {
      if (currentTemplateExercise) {
        const until = Date.now() + currentTemplateExercise.rest_seconds * 1000;
        setRestUntil(until);
        setRestPaused(false);
      }
      refreshFitness();
    }
  });
  const completeWorkout = useMutation({
    mutationFn: () => api.completeWorkout(activeSession?.id ?? "", { perceived_session_difficulty: Number(sessionDifficulty) }),
    onSuccess: refreshFitness
  });
  const abandonWorkout = useMutation({
    mutationFn: () => api.abandonWorkout(activeSession?.id ?? "", { notes: "Abandoned from workout mode." }),
    onSuccess: refreshFitness
  });
  const addMeasurement = useMutation({
    mutationFn: api.addBodyMeasurement,
    onSuccess: refreshFitness
  });
  const addRecovery = useMutation({
    mutationFn: api.addRecoveryObservation,
    onSuccess: refreshFitness
  });
  const syncCandidates = useMutation({
    mutationFn: api.syncFitnessCandidateActions,
    onSuccess: refreshFitness
  });

  function handleProgramSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createProgram.mutate({ name: programName, goal_type: "hypertrophy", active: true });
  }

  function handleExerciseSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createExercise.mutate({ name: exerciseName, category: "strength", default_rest_seconds: Number(exerciseRest) });
  }

  function handleTemplateSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const programId = status.data?.active_program?.id ?? programs.data?.[0]?.id;
    if (programId) {
      createTemplate.mutate({ program_id: programId, name: templateName, estimated_duration_minutes: Number(templateMinutes), active: true });
    }
  }

  function handleTemplateExerciseSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const templateId = nextWorkout?.id ?? templates.data?.[0]?.id;
    const exerciseId = exercises.data?.find((item) => item.name === exerciseName)?.id ?? exercises.data?.[0]?.id;
    if (templateId && exerciseId) {
      addTemplateExercise.mutate({ templateId, exerciseId });
    }
  }

  function handleMeasurementSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addMeasurement.mutate({
      body_weight_kg: Number(weight),
      body_fat_percentage: Number(bodyFat),
      source: "etekcity_scale"
    });
  }

  function handleRecoverySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addRecovery.mutate({ soreness: Number(soreness), sleep_quality: Number(sleepQuality), stress: Number(stress) });
  }

  return (
    <div className="stack">
      <section className="stat-grid" aria-label="Fitness summary">
        <StatTile label="Next" value={nextWorkout?.name ?? "--"} tone="blue" />
        <StatTile label="Recovery" value={status.data?.readiness.band ?? "--"} tone="green" />
        <StatTile label="This week" value={`${status.data?.workouts_this_week ?? 0} / ${status.data?.weekly_target ?? 4}`} tone="amber" />
        <StatTile label="Weight trend" value={displayNumber(status.data?.body_trend.weight.rolling_average, " kg")} tone="rose" />
      </section>

      {activeSession ? (
        <section className="content-band workout-mode" aria-label="Workout mode">
          <div className="section-header">
            <div>
              <p className="eyebrow">Workout mode</p>
              <h2>{activeSession.template?.name ?? "Workout"}</h2>
            </div>
            <span>{activeSession.status.replaceAll("_", " ")}</span>
          </div>
          {currentTemplateExercise ? (
            <div className="workout-focus">
              <div>
                <strong>{currentTemplateExercise.exercise?.name ?? "Exercise"}</strong>
                <p className="status-text">
                  Set {Math.min(currentSetNumber, currentTemplateExercise.target_sets)} / {currentTemplateExercise.target_sets} ·{" "}
                  {currentTemplateExercise.target_rep_min}-{currentTemplateExercise.target_rep_max} reps ·{" "}
                  {displayNumber(currentProgression?.recommended_load_kg ?? currentTemplateExercise.target_load_kg, " kg")}
                </p>
              </div>
              <form className="compact-form v02-form" onSubmit={(event) => event.preventDefault()}>
                <label>
                  Load kg
                  <input value={load} onChange={(event) => setLoad(event.target.value)} inputMode="decimal" />
                </label>
                <label>
                  Reps
                  <input value={reps} onChange={(event) => setReps(event.target.value)} inputMode="numeric" />
                </label>
                <label>
                  RPE
                  <input value={rpe} onChange={(event) => setRpe(event.target.value)} inputMode="decimal" />
                </label>
                <button className="primary-button" type="button" onClick={() => logSet.mutate(currentTemplateExercise)} disabled={logSet.isPending}>
                  <span>{logSet.isPending ? "Saving" : "Complete set"}</span>
                  <Check size={17} aria-hidden="true" />
                </button>
              </form>
              <div className="rest-panel">
                <strong>{remainingRestSeconds > 0 ? formatTimer(remainingRestSeconds) : "Rest ready"}</strong>
                <div className="execution-actions">
                  <button
                    className="icon-button"
                    type="button"
                    aria-label="Start rest timer"
                    onClick={() => {
                      setRestUntil(Date.now() + currentTemplateExercise.rest_seconds * 1000);
                      setRestPaused(false);
                    }}
                  >
                    <Play size={15} />
                  </button>
                  <button className="icon-button" type="button" aria-label="Pause rest timer" onClick={() => setRestPaused(true)}>
                    <Pause size={15} />
                  </button>
                  <button className="icon-button" type="button" aria-label="Reset rest timer" onClick={() => setRestUntil(null)}>
                    <RotateCcw size={15} />
                  </button>
                </div>
              </div>
              <div className="set-history">
                {setsFor(activeSession, currentTemplateExercise.id).map((set) => (
                  <span key={set.id}>
                    {set.load_kg}kg x {set.reps} @ {set.rpe}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="status-text">All planned sets are logged.</p>
          )}
          <form className="compact-form" onSubmit={(event) => event.preventDefault()}>
            <label>
              Session RPE
              <input value={sessionDifficulty} onChange={(event) => setSessionDifficulty(event.target.value)} inputMode="decimal" />
            </label>
            <button className="primary-button" type="button" onClick={() => completeWorkout.mutate()} disabled={completeWorkout.isPending}>
              <span>Complete workout</span>
              <Square size={16} aria-hidden="true" />
            </button>
            <button className="secondary-button" type="button" onClick={() => abandonWorkout.mutate()} disabled={abandonWorkout.isPending}>
              <span>Abandon</span>
              <X size={16} aria-hidden="true" />
            </button>
          </form>
        </section>
      ) : (
        <section className="content-band">
          <div className="section-header">
            <h2 id="training" tabIndex={-1}>Today Workout</h2>
            <span>{nextWorkout ? `${nextWorkout.exercises.length} exercises` : "empty"}</span>
          </div>
          {nextWorkout ? (
            <div className="timeline">
              <article className="timeline-item generated_action">
                <div>
                  <strong>{nextWorkout.name}</strong>
                  <small>{nextWorkout.estimated_duration_minutes}m · {nextWorkout.exercises.length} exercises</small>
                </div>
                <button className="icon-button" type="button" aria-label={`Start ${nextWorkout.name}`} onClick={() => startWorkout.mutate(nextWorkout.id)}>
                  <Dumbbell size={16} />
                </button>
              </article>
            </div>
          ) : (
            <p className="status-text">Create a program and template to start training.</p>
          )}
        </section>
      )}

      <section className="content-band">
        <div className="section-header">
          <h2>Program Setup</h2>
          <span>{status.data?.active_program?.name ?? "none"}</span>
        </div>
        <form className="compact-form v02-form" onSubmit={handleProgramSubmit}>
          <label>
            Program
            <input value={programName} onChange={(event) => setProgramName(event.target.value)} />
          </label>
          <button className="primary-button" type="submit">
            <span>Create program</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        <form className="compact-form v02-form" onSubmit={handleTemplateSubmit}>
          <label>
            Template
            <input value={templateName} onChange={(event) => setTemplateName(event.target.value)} />
          </label>
          <label>
            Minutes
            <input value={templateMinutes} onChange={(event) => setTemplateMinutes(event.target.value)} inputMode="numeric" />
          </label>
          <button className="primary-button" type="submit" disabled={!status.data?.active_program && !programs.data?.[0]}>
            <span>Create template</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        <form className="compact-form v02-form" onSubmit={handleExerciseSubmit}>
          <label>
            Exercise
            <input value={exerciseName} onChange={(event) => setExerciseName(event.target.value)} />
          </label>
          <label>
            Rest seconds
            <input value={exerciseRest} onChange={(event) => setExerciseRest(event.target.value)} inputMode="numeric" />
          </label>
          <button className="primary-button" type="submit">
            <span>Create exercise</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        <form className="compact-form v02-form" onSubmit={handleTemplateExerciseSubmit}>
          <label>
            Sets
            <input value={targetSets} onChange={(event) => setTargetSets(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Reps
            <input value={`${targetRepMin}-${targetRepMax}`} onChange={(event) => {
              const [min, max] = event.target.value.split("-");
              setTargetRepMin(min ?? "8");
              setTargetRepMax(max ?? min ?? "10");
            }} />
          </label>
          <label>
            Load kg
            <input value={targetLoad} onChange={(event) => setTargetLoad(event.target.value)} inputMode="decimal" />
          </label>
          <label>
            RPE
            <input value={targetRpe} onChange={(event) => setTargetRpe(event.target.value)} inputMode="decimal" />
          </label>
          <label>
            Increment kg
            <input value={loadIncrement} onChange={(event) => setLoadIncrement(event.target.value)} inputMode="decimal" />
          </label>
          <button className="primary-button" type="submit" disabled={!nextWorkout && !templates.data?.[0]}>
            <span>Add to template</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Progression</h2>
          <span>double progression</span>
        </div>
        <div className="pool-list">
          {(status.data?.progression ?? []).map((item) => (
            <article className="pool-item" key={item.id}>
              <div>
                <strong>{item.recommendation}</strong>
                <p className="status-text">
                  {displayNumber(item.previous_load_kg, " kg")} to {displayNumber(item.recommended_load_kg, " kg")} ·{" "}
                  {String(item.explanation_json.reason ?? "No explanation")}
                </p>
              </div>
            </article>
          ))}
          {(status.data?.progression.length ?? 0) === 0 ? <p className="muted">Recommendations appear after completed workouts.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header"><h2>Recent Workouts</h2><span>{status.data?.recent_workouts?.length ?? 0}</span></div>
        <div className="pool-list">
          {(status.data?.recent_workouts ?? []).map((session) => (
            <article className="pool-item" key={session.id}><div><strong>{session.template?.name ?? "Workout"}</strong><p className="status-text">{session.completed_at ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(session.completed_at)) : "In progress"} · {session.actual_duration_minutes ?? "--"}m{session.modified ? " · modified" : ""}</p></div></article>
          ))}
          {(status.data?.recent_workouts?.length ?? 0) === 0 ? <p className="muted">Completed workouts will appear here.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Body Measurement</h2>
          <span>Etekcity scale</span>
        </div>
        <form className="compact-form v02-form" onSubmit={handleMeasurementSubmit}>
          <label>
            Weight kg
            <input value={weight} onChange={(event) => setWeight(event.target.value)} inputMode="decimal" />
          </label>
          <label>
            Body fat %
            <input value={bodyFat} onChange={(event) => setBodyFat(event.target.value)} inputMode="decimal" />
          </label>
          <button className="primary-button" type="submit" disabled={addMeasurement.isPending}>
            <span>Add measurement</span>
            <Plus size={17} aria-hidden="true" />
          </button>
        </form>
        <p className="status-text">
          Latest {displayNumber(status.data?.body_trend.weight.latest, " kg")} · trend{" "}
          {displayNumber(status.data?.body_trend.weight.rolling_average, " kg")} · {status.data?.body_trend.weight.label ?? "No trend yet"}
        </p>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Recovery</h2>
          <span>{status.data?.readiness.score ?? "--"}</span>
        </div>
        <form className="compact-form v02-form" onSubmit={handleRecoverySubmit}>
          <label>
            Soreness
            <input value={soreness} onChange={(event) => setSoreness(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Sleep
            <input value={sleepQuality} onChange={(event) => setSleepQuality(event.target.value)} inputMode="numeric" />
          </label>
          <label>
            Stress
            <input value={stress} onChange={(event) => setStress(event.target.value)} inputMode="numeric" />
          </label>
          <button className="primary-button" type="submit">
            <span>Save recovery</span>
            <Check size={17} aria-hidden="true" />
          </button>
        </form>
        <p className="status-text">
          Readiness is {status.data?.readiness.band ?? "--"} from {status.data?.readiness.factors.length ?? 0} deterministic factors.
        </p>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Planner Candidates</h2>
          <span>{status.data?.candidates.length ?? 0}</span>
        </div>
        <div className="pool-list">
          {(status.data?.candidates ?? []).map((candidate) => (
            <article className="pool-item" key={candidate.candidate_id}>
              <div>
                <strong>{candidate.title}</strong>
                <p className="status-text">
                  {candidate.duration_minutes}m · physical {candidate.physical_load} · activation {candidate.activation_difficulty}
                </p>
              </div>
            </article>
          ))}
        </div>
        <button className="secondary-button" type="button" onClick={() => syncCandidates.mutate()} disabled={syncCandidates.isPending}>
          <span>{syncCandidates.isPending ? "Syncing" : "Sync candidates to Planning Pool"}</span>
        </button>
      </section>
    </div>
  );
}
