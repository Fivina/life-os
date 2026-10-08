import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FitnessPage } from "../features/fitness/FitnessPage";
import { api } from "../services/api";
import type { Exercise, FitnessStatus, WorkoutProgram, WorkoutSession, WorkoutTemplate } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    fitnessStatus: vi.fn(),
    fitnessPrograms: vi.fn(),
    fitnessTemplates: vi.fn(),
    fitnessExercises: vi.fn(),
    createFitnessProgram: vi.fn(),
    createFitnessExercise: vi.fn(),
    createFitnessTemplate: vi.fn(),
    addFitnessTemplateExercise: vi.fn(),
    startWorkout: vi.fn(),
    logWorkoutSet: vi.fn(),
    completeWorkout: vi.fn(),
    abandonWorkout: vi.fn(),
    addBodyMeasurement: vi.fn(),
    addRecoveryObservation: vi.fn(),
    syncFitnessCandidateActions: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderFitness() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return render(<FitnessPage />, { wrapper: Wrapper });
}

function submitByButton(name: RegExp) {
  const button = screen.getByRole("button", { name });
  const form = button.closest("form");
  if (!form) {
    throw new Error(`No form found for ${name}`);
  }
  fireEvent.submit(form);
}

function programFixture(): WorkoutProgram {
  return {
    id: "program-1",
    name: "Hypertrophy 4-Day",
    description: null,
    goal_type: "hypertrophy",
    status: "active",
    active: true,
    version: 1
  };
}

function exerciseFixture(): Exercise {
  return {
    id: "exercise-1",
    name: "Bench Press",
    category: "strength",
    primary_muscle_group: "chest",
    equipment: "barbell",
    default_rest_seconds: 120,
    active: true,
    notes: null,
    version: 1
  };
}

function templateFixture(): WorkoutTemplate {
  return {
    id: "template-1",
    program_id: "program-1",
    name: "Upper A",
    sequence_order: 0,
    estimated_duration_minutes: 75,
    active: true,
    notes: null,
    version: 1,
    exercises: [
      {
        id: "template-exercise-1",
        template_id: "template-1",
        exercise_id: "exercise-1",
        exercise: exerciseFixture(),
        order_index: 0,
        target_sets: 3,
        target_rep_min: 8,
        target_rep_max: 10,
        target_load_kg: 70,
        target_rpe: 8.5,
        rest_seconds: 120,
        progression_rule: "double_progression",
        load_increment_kg: 2.5,
        notes: null,
        version: 1
      }
    ]
  };
}

function sessionFixture(): WorkoutSession {
  return {
    id: "session-1",
    workout_template_id: "template-1",
    source_action_id: null,
    source_plan_block_id: null,
    started_at: "2026-09-20T08:00:00Z",
    completed_at: null,
    status: "in_progress",
    perceived_session_difficulty: null,
    notes: null,
    template: templateFixture(),
    sets: [],
    progression: [
      {
        id: "progression-1",
        template_exercise_id: "template-exercise-1",
        exercise_id: "exercise-1",
        rule: "double_progression",
        previous_load_kg: 70,
        recommended_load_kg: 72.5,
        recommendation: "increase",
        explanation_json: { reason: "All required working sets reached the upper rep target." },
        version: 1
      }
    ],
    version: 1
  };
}

function statusFixture(overrides: Partial<FitnessStatus> = {}): FitnessStatus {
  return {
    active_program: programFixture(),
    next_workout: templateFixture(),
    active_session: null,
    latest_measurement: null,
    body_trend: {
      latest_measurement: null,
      weight: { latest: 78.3, rolling_average: 78.47, sample_count: 7, window_days: 7, change: 0.3, direction: "up", label: "78.47 kg rolling 7-day average" },
      body_fat: { latest: 17.2, rolling_average: 17.1, sample_count: 7, window_days: 7, change: -0.2, direction: "down", label: "17.1% rolling 7-day average" }
    },
    readiness: { score: 76, band: "good", factors: [{ factor: "base_readiness", contribution: 76 }] },
    workouts_this_week: 2,
    weekly_target: 4,
    progression: [],
    candidates: [
      {
        candidate_id: "fitness:template-1:full",
        title: "Upper A (full)",
        template_id: "template-1",
        duration_minutes: 75,
        minimum_minutes: 25,
        maximum_minutes: 75,
        physical_load: 70,
        activation_difficulty: 34,
        trajectory_value: 48,
        expected_state_effect: { readiness_score: 76 },
        metadata: { duration_variant: "full" }
      }
    ],
    ...overrides
  };
}

describe("Fitness V0.5", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.fitnessStatus.mockResolvedValue(statusFixture());
    mockedApi.fitnessPrograms.mockResolvedValue([programFixture()]);
    mockedApi.fitnessTemplates.mockResolvedValue([templateFixture()]);
    mockedApi.fitnessExercises.mockResolvedValue([exerciseFixture()]);
    mockedApi.createFitnessProgram.mockResolvedValue(programFixture());
    mockedApi.createFitnessExercise.mockResolvedValue(exerciseFixture());
    mockedApi.createFitnessTemplate.mockResolvedValue(templateFixture());
    mockedApi.addFitnessTemplateExercise.mockResolvedValue(templateFixture().exercises[0]);
    mockedApi.startWorkout.mockResolvedValue(sessionFixture());
    mockedApi.logWorkoutSet.mockResolvedValue({
      id: "set-1",
      workout_session_id: "session-1",
      exercise_id: "exercise-1",
      template_exercise_id: "template-exercise-1",
      sequence: 1,
      reps: 10,
      load_kg: 72.5,
      rpe: 8,
      set_type: "working",
      completed_at: "2026-09-20T08:10:00Z",
      note: null,
      completed: true,
      version: 1
    });
    mockedApi.completeWorkout.mockResolvedValue({ ...sessionFixture(), status: "completed", completed_at: "2026-09-20T09:00:00Z" });
    mockedApi.abandonWorkout.mockResolvedValue({ ...sessionFixture(), status: "abandoned", completed_at: "2026-09-20T08:30:00Z" });
    mockedApi.addBodyMeasurement.mockResolvedValue({
      id: "measurement-1",
      measured_at: "2026-09-20T07:00:00Z",
      body_weight_kg: 78.3,
      body_fat_percentage: 17.2,
      lean_mass_kg: null,
      source: "etekcity_scale",
      metadata_json: {},
      notes: null,
      version: 1
    });
    mockedApi.addRecoveryObservation.mockResolvedValue({
      id: "recovery-1",
      observed_at: "2026-09-20T07:00:00Z",
      soreness: 25,
      sleep_quality: 75,
      stress: 35,
      readiness: null,
      source: "manual",
      notes: null,
      version: 1
    });
    mockedApi.syncFitnessCandidateActions.mockResolvedValue([]);
  });

  it("renders dashboard, next workout, trends, recovery, and candidates", async () => {
    renderFitness();

    expect((await screen.findAllByText("Upper A")).length).toBeGreaterThan(0);
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText("2 / 4")).toBeInTheDocument();
    expect(screen.getByText(/78.47 kg rolling 7-day average/i)).toBeInTheDocument();
    expect(screen.getByText("Upper A (full)")).toBeInTheDocument();
  });

  it("creates program, exercise, template, and template exercise", async () => {
    renderFitness();

    await screen.findByRole("button", { name: /create program/i });
    submitByButton(/create program/i);
    await waitFor(() => expect(mockedApi.createFitnessProgram).toHaveBeenCalled());
    expect(mockedApi.createFitnessProgram.mock.calls[0][0]).toMatchObject({ name: "Hypertrophy 4-Day" });

    submitByButton(/create exercise/i);
    await waitFor(() => expect(mockedApi.createFitnessExercise).toHaveBeenCalled());
    expect(mockedApi.createFitnessExercise.mock.calls[0][0]).toMatchObject({ name: "Bench Press" });

    submitByButton(/create template/i);
    await waitFor(() => expect(mockedApi.createFitnessTemplate).toHaveBeenCalled());

    submitByButton(/add to template/i);
    await waitFor(() => expect(mockedApi.addFitnessTemplateExercise).toHaveBeenCalled());
  });

  it("starts workout from today's workout card", async () => {
    renderFitness();

    fireEvent.click(await screen.findByRole("button", { name: /start upper a/i }));

    await waitFor(() => expect(mockedApi.startWorkout).toHaveBeenCalledWith({ workout_template_id: "template-1" }));
  });

  it("logs a set in workout mode and starts the rest timer", async () => {
    mockedApi.fitnessStatus.mockResolvedValue(statusFixture({ active_session: sessionFixture() }));
    renderFitness();

    expect(await screen.findByText("Workout mode")).toBeInTheDocument();
    expect(screen.getByText(/Set 1 \/ 3/i)).toBeInTheDocument();
    await screen.findByDisplayValue("72.5");
    fireEvent.click(screen.getByRole("button", { name: /complete set/i }));

    await waitFor(() => expect(mockedApi.logWorkoutSet).toHaveBeenCalledWith("session-1", expect.objectContaining({ reps: 10, load_kg: 72.5, rpe: 8.5 })));
    expect(await screen.findByText(/01:|02:/)).toBeInTheDocument();
  });

  it("completes and abandons active workouts", async () => {
    mockedApi.fitnessStatus.mockResolvedValue(statusFixture({ active_session: sessionFixture() }));
    renderFitness();

    fireEvent.click(await screen.findByRole("button", { name: /complete workout/i }));
    await waitFor(() => expect(mockedApi.completeWorkout).toHaveBeenCalledWith("session-1", expect.objectContaining({ perceived_session_difficulty: 8 })));

    fireEvent.click(screen.getByRole("button", { name: /abandon/i }));
    await waitFor(() => expect(mockedApi.abandonWorkout).toHaveBeenCalledWith("session-1", expect.any(Object)));
  });

  it("records body measurements, recovery, and syncs candidates", async () => {
    renderFitness();

    await screen.findByRole("button", { name: /add measurement/i });
    submitByButton(/add measurement/i);
    await waitFor(() => expect(mockedApi.addBodyMeasurement).toHaveBeenCalled());
    expect(mockedApi.addBodyMeasurement.mock.calls[0][0]).toMatchObject({ body_weight_kg: 78.3, source: "etekcity_scale" });

    submitByButton(/save recovery/i);
    await waitFor(() => expect(mockedApi.addRecoveryObservation).toHaveBeenCalled());
    expect(mockedApi.addRecoveryObservation.mock.calls[0][0]).toMatchObject({ soreness: 25, sleep_quality: 75, stress: 35 });

    fireEvent.click(screen.getByRole("button", { name: /sync candidates/i }));
    await waitFor(() => expect(mockedApi.syncFitnessCandidateActions).toHaveBeenCalled());
  });
});
