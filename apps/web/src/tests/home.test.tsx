import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { HomePage } from "../features/home/HomePage";
import { api } from "../services/api";
import type { LatestState, Plan, StateObservationBatch } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    latestState: vi.fn(),
    createStateObservations: vi.fn(),
    currentPlan: vi.fn(),
    generatePlan: vi.fn(),
    evaluateDay: vi.fn(),
    replanDay: vi.fn(),
    startPlanBlock: vi.fn(),
    completePlanBlock: vi.fn(),
    skipPlanBlock: vi.fn(),
    fitnessStatus: vi.fn(),
    learningStatus: vi.fn(),
    kitchenStatus: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderHome() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(<HomePage />, { wrapper: Wrapper });
}

function latestStateFixture(overrides: Partial<LatestState> = {}): LatestState {
  return {
    values: {},
    check_in: null,
    world_revision: 0,
    ...overrides
  };
}

function savedBatchFixture(): StateObservationBatch {
  return {
    observations: [
      {
        id: "energy-id",
        observation_type: "energy",
        value: 65,
        observed_at: "2026-09-14T08:00:00Z",
        source: "manual",
        notes: null
      },
      {
        id: "mental-id",
        observation_type: "mental_state",
        value: 72,
        observed_at: "2026-09-14T08:00:00Z",
        source: "manual",
        notes: null
      }
    ],
    world_revision: 4
  };
}

function planFixture(): Plan {
  return {
    id: "plan-1",
    user_id: "user-1",
    planner_version: "v0.3-core-planner",
    generated_from_world_revision: 8,
    status: "current",
    planning_day: "2026-09-14",
    horizon_start: "2026-09-14T08:00:00Z",
    horizon_end: "2026-09-14T22:00:00Z",
    generated_at: "2026-09-14T07:30:00Z",
    previous_plan_id: null,
    replan_reason: null,
    control_loop_version: "v0.4-control-loop",
    plan_diff: {
      previous_plan_id: null,
      new_plan_id: "plan-1",
      trigger: "plan.generated",
      kept_block_ids: [],
      moved_blocks: [],
      shortened_blocks: [],
      removed_blocks: [],
      added_blocks: [],
      deferred_action_ids: [],
      previous_stress: null,
      new_stress: 58,
      previous_slack_minutes: null,
      new_slack_minutes: 90
    },
    summary_metrics: {
      flexible_work_minutes: 150,
      hard_commitment_minutes: 300,
      slack_minutes: 90,
      actions_scheduled: 2,
      actions_unscheduled: 1,
      planning_load: "moderate",
      stress_estimate: 58,
      stress_threshold: 68,
      state_band: "medium",
      usable_flexible_minutes: 270,
      required_slack_minutes: 90
    },
    decision_factors: [],
    blocks: [
      {
        id: "block-hard",
        source_type: "commitment",
        source_id: "commitment-1",
        action_id: null,
        commitment_id: "commitment-1",
        domain: "commitment",
        title: "University",
        starts_at: "2026-09-14T11:00:00Z",
        ends_at: "2026-09-14T16:00:00Z",
        duration_minutes: 300,
        block_type: "hard_commitment",
        commitment_level: "hard",
        movable: false,
        status: "planned",
        started_at: null,
        finished_at: null,
        actual_duration_minutes: null,
        outcome_reason: null,
        note: null,
        decision_factors: [],
        version: 1
      },
      {
        id: "block-study",
        source_type: "action",
        source_id: "action-1",
        action_id: "action-1",
        commitment_id: null,
        domain: "learning",
        title: "Study Macroeconomics",
        starts_at: "2026-09-14T09:00:00Z",
        ends_at: "2026-09-14T10:30:00Z",
        duration_minutes: 90,
        block_type: "generated_action",
        commitment_level: "goal_critical",
        movable: true,
        status: "planned",
        started_at: null,
        finished_at: null,
        actual_duration_minutes: null,
        outcome_reason: null,
        note: null,
        decision_factors: [],
        version: 1
      },
      {
        id: "block-slack",
        source_type: "planner",
        source_id: null,
        action_id: null,
        commitment_id: null,
        domain: "recovery",
        title: "Buffer / slack",
        starts_at: "2026-09-14T16:00:00Z",
        ends_at: "2026-09-14T17:30:00Z",
        duration_minutes: 90,
        block_type: "slack",
        commitment_level: null,
        movable: true,
        status: "planned",
        started_at: null,
        finished_at: null,
        actual_duration_minutes: null,
        outcome_reason: null,
        note: null,
        decision_factors: [],
        version: 1
      }
    ],
    unscheduled_actions: [{ source_action_id: "action-2", title: "Read optional article", reason: "capacity_limit", score: 12 }],
    current_world_revision: 9,
    version: 1
  };
}

function controlStatusFixture(plan = planFixture()) {
  return {
    plan,
    control_status: "kept",
    replan_reason: "NO_CHANGE",
    last_evaluated_at: "2026-09-14T08:30:00Z",
    last_replanned_at: null,
    plan_diff: {
      previous_plan_id: plan.id,
      new_plan_id: plan.id,
      trigger: "NO_CHANGE",
      kept_block_ids: plan.blocks.map((block) => block.id),
      moved_blocks: [],
      shortened_blocks: [],
      removed_blocks: [],
      added_blocks: [],
      deferred_action_ids: [],
      previous_stress: plan.summary_metrics.stress_estimate,
      new_stress: plan.summary_metrics.stress_estimate,
      previous_slack_minutes: plan.summary_metrics.slack_minutes,
      new_slack_minutes: plan.summary_metrics.slack_minutes
    }
  };
}

function fitnessStatusFixture() {
  return {
    active_program: null,
    next_workout: null,
    active_session: null,
    latest_measurement: null,
    body_trend: {
      latest_measurement: null,
      weight: { latest: null, rolling_average: null, sample_count: 0, window_days: 7, change: null, direction: "unknown", label: "No data" },
      body_fat: { latest: null, rolling_average: null, sample_count: 0, window_days: 7, change: null, direction: "unknown", label: "No data" }
    },
    readiness: { score: 70, band: "good", factors: [] },
    workouts_this_week: 0,
    weekly_target: 4,
    progression: [],
    candidates: []
  };
}

function learningStatusFixture() {
  return {
    courses: [],
    exams: [],
    active_exam: null,
    candidates: [],
    recent_sessions: [],
    current_learning_plan_window: []
  };
}

function kitchenStatusFixture() {
  return {
    inventory_count: 2,
    expiring_lots: 1,
    expired_lots: 0,
    nutrition: {
      date: "2026-09-14",
      calories_target: 2400,
      protein_g_target: 170,
      calories_consumed: 850,
      protein_g_consumed: 70,
      calories_remaining: 1550,
      protein_g_remaining: 100,
      calories_over_target: 0,
      protein_g_over_target: 0
    },
    top_recommendation: null,
    shopping_need_count: 0,
    active_candidate_count: 0
  };
}

function withBlockStatus(status: string): Plan {
  const plan = planFixture();
  return {
    ...plan,
    blocks: plan.blocks.map((block) =>
      block.id === "block-study"
        ? {
            ...block,
            status,
            started_at: status === "in_progress" || status === "completed" ? "2026-09-14T09:00:00Z" : null,
            finished_at: status === "completed" || status === "skipped" ? "2026-09-14T10:30:00Z" : null
          }
        : block
    )
  };
}

describe("Home check-in", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.currentPlan.mockResolvedValue(null);
    mockedApi.evaluateDay.mockResolvedValue(controlStatusFixture());
    mockedApi.fitnessStatus.mockResolvedValue(fitnessStatusFixture());
    mockedApi.learningStatus.mockResolvedValue(learningStatusFixture());
    mockedApi.kitchenStatus.mockResolvedValue(kitchenStatusFixture());
    mockedApi.replanDay.mockResolvedValue({
      plan: planFixture(),
      replan_mode: "FULL_REPLAN",
      trigger_reason: "USER_REQUESTED",
      control_status: "replanned",
      plan_diff: {
        previous_plan_id: "plan-0",
        new_plan_id: "plan-1",
        trigger: "USER_REQUESTED",
        kept_block_ids: ["block-hard"],
        moved_blocks: [],
        shortened_blocks: [{ block_id: "block-study", from_minutes: 120, to_minutes: 90 }],
        removed_blocks: [],
        added_blocks: [],
        deferred_action_ids: ["action-2"],
        previous_stress: 62,
        new_stress: 58,
        previous_slack_minutes: 60,
        new_slack_minutes: 90
      },
      last_evaluated_at: "2026-09-14T08:30:00Z",
      last_replanned_at: "2026-09-14T08:30:00Z"
    });
  });

  it("renders the current state check-in and empty state", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());

    renderHome();

    expect(screen.getByRole("heading", { name: "Current State Check-in" })).toBeInTheDocument();
    expect(screen.getByLabelText(/ask or add something/i)).toHaveAttribute("name", "q");
    expect(await screen.findByText("No previous check-in yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save check-in/i })).toBeInTheDocument();
  });

  it("renders saved latest values and timestamp", async () => {
    mockedApi.latestState.mockResolvedValue(
      latestStateFixture({
        check_in: {
          energy: 65,
          mental_state: 72,
          observed_at: "2026-09-14T08:00:00Z",
          observation_ids: { energy: "energy-id", mental_state: "mental-id" }
        },
        world_revision: 3
      })
    );

    renderHome();

    expect(await screen.findByText(/Last recorded/i)).toBeInTheDocument();
    expect(screen.getAllByText("65").length).toBeGreaterThan(0);
    expect(screen.getAllByText("72").length).toBeGreaterThan(0);
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("lets values change and saves through the API", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.createStateObservations.mockResolvedValue(savedBatchFixture());

    renderHome();

    await screen.findByText("No previous check-in yet.");
    fireEvent.change(screen.getByLabelText(/energy/i), { target: { value: "65" } });
    fireEvent.change(screen.getByLabelText(/mental state/i), { target: { value: "72" } });
    fireEvent.click(screen.getByRole("button", { name: /save check-in/i }));

    await waitFor(() => {
      expect(mockedApi.createStateObservations).toHaveBeenCalled();
    });
    expect(mockedApi.createStateObservations.mock.calls[0][0]).toEqual({ energy: 65, mental_state: 72 });
    await waitFor(() => expect(mockedApi.evaluateDay).toHaveBeenCalled());
    expect(await screen.findByText("Check-in saved.")).toBeInTheDocument();
  });

  it("renders an error state when latest state loading fails", async () => {
    mockedApi.latestState.mockRejectedValue(new Error("network"));

    renderHome();

    expect(await screen.findByText("Could not load the latest check-in.")).toBeInTheDocument();
  });

  it("loads the current plan and renders no-plan state", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(null);

    renderHome();

    expect(await screen.findByText("No generated plan for today yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generate today's plan/i })).toBeInTheDocument();
    expect(screen.getByText("No plan blocks yet.")).toBeInTheDocument();
  });

  it("generates a plan through the API", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(null);
    mockedApi.generatePlan.mockResolvedValue(planFixture());

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /generate today's plan/i }));

    await waitFor(() => expect(mockedApi.generatePlan).toHaveBeenCalled());
    expect(await screen.findByText("Plan generated.")).toBeInTheDocument();
  });

  it("renders hard commitments, generated actions, slack, and summary", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());

    renderHome();

    expect(await screen.findByText(/University/)).toBeInTheDocument();
    expect(await screen.findByText(/Study Macroeconomics/)).toBeInTheDocument();
    expect(await screen.findByText(/Buffer \/ slack/)).toBeInTheDocument();
    expect(screen.getByText("150m")).toBeInTheDocument();
    expect(screen.getByText("300m")).toBeInTheDocument();
    expect(screen.getByText("90m")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders a generation error state", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(null);
    mockedApi.generatePlan.mockRejectedValue(new Error("stale_world_revision"));

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /generate today's plan/i }));

    expect(await screen.findByText("Plan could not be generated. Refresh and try again.")).toBeInTheDocument();
  });

  it("renders execution controls and starts a generated block", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());
    mockedApi.startPlanBlock.mockResolvedValue(withBlockStatus("in_progress"));

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /start study macroeconomics/i }));

    await waitFor(() => expect(mockedApi.startPlanBlock).toHaveBeenCalledWith("plan-1", "block-study", 1));
  });

  it("completes a generated block through the execution API", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());
    mockedApi.completePlanBlock.mockResolvedValue(withBlockStatus("completed"));

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /complete study macroeconomics/i }));
    await waitFor(() => expect(mockedApi.completePlanBlock).toHaveBeenCalledWith("plan-1", "block-study", 1, 90));
  });

  it("skips a generated block and evaluates the remaining day", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());
    mockedApi.skipPlanBlock.mockResolvedValue(withBlockStatus("skipped"));

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /skip study macroeconomics/i }));
    await waitFor(() => expect(mockedApi.skipPlanBlock).toHaveBeenCalledWith("plan-1", "block-study", 1, "other"));
    await waitFor(() => expect(mockedApi.evaluateDay).toHaveBeenCalled());
  });

  it("runs manual replan and renders PlanDiff summary", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());

    renderHome();

    await screen.findByText(/Generated from world revision 8/i);
    const replanButton = screen.getByRole("button", { name: /replan remaining day/i });
    await waitFor(() => expect(replanButton).not.toBeDisabled());
    fireEvent.click(replanButton);

    await waitFor(() => expect(mockedApi.replanDay).toHaveBeenCalled());
    await waitFor(() => expect(screen.getAllByText("Plan adjusted.").length).toBeGreaterThan(0));
    expect(screen.getByText(/USER REQUESTED/i)).toBeInTheDocument();
    expect(screen.getByText(/1 shortened/i)).toBeInTheDocument();
  });

  it("shows material state adjustment feedback after check-in", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.createStateObservations.mockResolvedValue(savedBatchFixture());
    mockedApi.evaluateDay.mockResolvedValue({
      ...controlStatusFixture(planFixture()),
      control_status: "replanned",
      replan_reason: "STATE_MATERIAL_CHANGE",
      plan_diff: {
        ...controlStatusFixture(planFixture()).plan_diff,
        trigger: "STATE_MATERIAL_CHANGE",
        shortened_blocks: [{ block_id: "block-study", from_minutes: 90, to_minutes: 35 }],
        deferred_action_ids: ["action-2"]
      }
    });

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /save check-in/i }));

    await waitFor(() => expect(screen.getAllByText("Plan adjusted.").length).toBeGreaterThan(0));
    expect(screen.getByText(/STATE MATERIAL CHANGE/i)).toBeInTheDocument();
  });

  it("renders a skip error state", async () => {
    mockedApi.latestState.mockResolvedValue(latestStateFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());
    mockedApi.skipPlanBlock.mockRejectedValue(new Error("conflict"));

    renderHome();

    fireEvent.click(await screen.findByRole("button", { name: /skip study macroeconomics/i }));

    expect(await screen.findByText("Could not skip this block.")).toBeInTheDocument();
  });
});
