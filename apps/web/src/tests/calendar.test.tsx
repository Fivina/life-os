import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { CalendarPage } from "../features/calendar/CalendarPage";
import { api } from "../services/api";
import type { ActionIntention, CalendarProjection, Commitment, Plan, PlanProposal } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    calendarProjection: vi.fn(),
    getCommitment: vi.fn(),
    addCommitment: vi.fn(),
    addAction: vi.fn(),
    updateCommitment: vi.fn(),
    completeAction: vi.fn(),
    currentPlan: vi.fn(),
    planProposals: vi.fn(),
    presentPlanProposal: vi.fn(),
    acceptPlanProposal: vi.fn(),
    modifyPlanProposal: vi.fn(),
    rejectPlanProposal: vi.fn(),
    horizonAllocations: vi.fn(),
    replanDay: vi.fn(),
    completePlanBlock: vi.fn(),
    partialCompletePlanBlock: vi.fn(),
    skipPlanBlock: vi.fn(),
    explainPlanBlock: vi.fn(),
    standingCalendarRules: vi.fn(),
    syncStandingCalendarRule: vi.fn(),
    setStandingCalendarRuleEnabled: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderCalendar(path = "/calendar") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[path]}>{children}</MemoryRouter></QueryClientProvider>;
  }

  return render(<CalendarPage />, { wrapper: Wrapper });
}

function commitmentFixture(): Commitment {
  return {
    id: "commitment-1",
    title: "University",
    level: "hard",
    commitment_type: "hard",
    starts_at: "2026-09-16T09:00:00Z",
    ends_at: "2026-09-16T14:00:00Z",
    timezone: "Europe/Berlin",
    all_day: false,
    location: "University",
    recurrence: { frequency: "none" },
    source: "manual",
    status: "active",
    version: 1
  };
}

function actionFixture(): ActionIntention {
  return {
    id: "action-1",
    title: "Study Macroeconomics",
    domain: "learning",
    level: "goal_critical",
    deadline: "2026-09-20T21:59:00Z",
    estimated_minutes: 120,
    completed_minutes: 0,
    status: "active",
    scheduled_start: null,
    scheduled_end: null,
    metadata_json: {},
    version: 1
  };
}

function projectionFixture(): CalendarProjection {
  return {
    commitments: [
      {
        canonical_id: "commitment-1",
        canonical_type: "commitment",
        title: "University",
        starts_at: "2026-09-16T09:00:00Z",
        ends_at: "2026-09-16T14:00:00Z",
        status: "active",
        level: "hard",
        commitment_type: "hard",
        location: "University",
        source: "manual",
        version: 1
      }
    ],
    planning_pool: [actionFixture()],
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
    planning_day: "2026-09-16",
    horizon_start: "2026-09-16T07:00:00Z",
    horizon_end: "2026-09-16T20:00:00Z",
    generated_at: "2026-09-16T06:30:00Z",
    previous_plan_id: null,
    replan_reason: null,
    control_loop_version: "v0.4-control-loop",
    plan_diff: null,
    summary_metrics: {
      flexible_work_minutes: 90,
      hard_commitment_minutes: 300,
      slack_minutes: 120,
      actions_scheduled: 1,
      actions_unscheduled: 0,
      planning_load: "moderate",
      stress_estimate: 54,
      stress_threshold: 68,
      state_band: "medium",
      usable_flexible_minutes: 240,
      required_slack_minutes: 90
    },
    decision_factors: [],
    blocks: [
      {
        id: "block-study",
        source_type: "action",
        source_id: "action-1",
        action_id: "action-1",
        commitment_id: null,
        domain: "learning",
        title: "Study Macroeconomics",
        starts_at: "2026-09-16T15:00:00Z",
        ends_at: "2026-09-16T16:30:00Z",
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
      }
    ],
    unscheduled_actions: [],
    current_world_revision: 8,
    version: 1
  };
}

describe("V0.2 Calendar and Planning Pool", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.calendarProjection.mockResolvedValue({ commitments: [], planning_pool: [], world_revision: 0 });
    mockedApi.currentPlan.mockResolvedValue(null);
    mockedApi.planProposals.mockResolvedValue([]);
    mockedApi.horizonAllocations.mockResolvedValue({ horizon_start: "2026-09-16", horizon_end: "2026-09-25", status: "feasible", required_minutes: 0, available_minutes: 0, shortfall_minutes: 0, allocations: [] });
    mockedApi.standingCalendarRules.mockResolvedValue([]);
  });

  it("renders commitment and intention forms", async () => {
    renderCalendar();

    expect(screen.getByRole("heading", { name: "Add Commitment" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add Intention" })).toBeInTheDocument();
    expect(await screen.findByText("No fixed commitments yet.")).toBeInTheDocument();
  });

  it("opens an encoded distant commitment on its actual day from the route", async () => {
    mockedApi.getCommitment.mockResolvedValue({
      ...commitmentFixture(),
      id: "fixture/id with spaces",
      title: "Distant derby",
      starts_at: "2030-12-20T18:00:00Z",
      ends_at: "2030-12-20T20:00:00Z"
    });
    renderCalendar("/calendar?commitment=fixture%2Fid%20with%20spaces");

    expect(await screen.findByRole("heading", { name: "Distant derby" })).toBeInTheDocument();
    expect(mockedApi.getCommitment).toHaveBeenCalledWith("fixture/id with spaces");
    expect(screen.getByRole("button", { name: "day" })).toHaveAttribute("aria-pressed", "true");
    const expectedDate = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" }).format(new Date("2030-12-20T18:00:00Z"));
    expect(screen.getAllByText(expectedDate).length).toBeGreaterThan(0);
  });

  it("shows an explicit unavailable state without selecting an unrelated commitment", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.getCommitment.mockRejectedValue(new Error("Not found"));
    renderCalendar("/calendar?commitment=missing-fixture");

    expect(await screen.findByText(/Could not open the requested commitment/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "University" })).not.toBeInTheDocument();
  });

  it("shows the actual requested commitment when its date and kickoff are unconfirmed", async () => {
    mockedApi.getCommitment.mockResolvedValue({
      ...commitmentFixture(),
      id: "tbd-fixture",
      title: "Beşiktaş vs Opponent",
      starts_at: null,
      ends_at: null
    });
    renderCalendar("/calendar?commitment=tbd-fixture");

    expect(await screen.findByRole("heading", { name: "Beşiktaş vs Opponent" })).toBeInTheDocument();
    expect(screen.getByText("Date not confirmed")).toBeInTheDocument();
    expect(screen.getByText("Time not confirmed")).toBeInTheDocument();
  });

  it("navigates week, month, and day views while keeping calendar actions accessible", async () => {
    renderCalendar();

    expect(screen.getByRole("button", { name: "week" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "month" }));
    expect(screen.getByRole("button", { name: "month" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("gridcell")).toHaveLength(42);
    fireEvent.click(screen.getAllByRole("gridcell")[14]);
    expect(screen.getByRole("button", { name: "day" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Go to Add Commitment" })).toBeInTheDocument();
  });

  it("submits a valid commitment through the canonical API", async () => {
    mockedApi.addCommitment.mockResolvedValue(commitmentFixture());
    renderCalendar();

    fireEvent.click(screen.getByRole("button", { name: /save commitment/i }));

    await waitFor(() => expect(mockedApi.addCommitment).toHaveBeenCalled());
    expect(mockedApi.addCommitment.mock.calls[0][0]).toMatchObject({
      title: "University",
      level: "hard",
      commitment_type: "hard",
      location: "University"
    });
  });

  it("displays commitment conflict errors", async () => {
    mockedApi.addCommitment.mockRejectedValue(new Error("Hard commitment overlaps an existing active hard commitment."));
    renderCalendar();

    fireEvent.click(screen.getByRole("button", { name: /save commitment/i }));

    expect(await screen.findByText(/Conflict or error/i)).toBeInTheDocument();
  });

  it("renders commitments in projection and intentions only in Planning Pool", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    renderCalendar();

    expect(await screen.findByText(/University/)).toBeInTheDocument();
    expect(await screen.findByText(/Study Macroeconomics/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Planning Pool" })).toBeInTheDocument();
  });

  it("renders current PlanBlocks in the calendar projection", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.currentPlan.mockResolvedValue(planFixture());
    renderCalendar();

    expect(await screen.findByLabelText("Plan block Study Macroeconomics")).toBeInTheDocument();
    expect(screen.getByText(/planned/i)).toBeInTheDocument();
  });

  it("shows overload, at-risk work, and requests deterministic replanning", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.currentPlan.mockResolvedValue({
      ...planFixture(),
      overload_status: "overloaded",
      shortfall_minutes: 150,
      unscheduled_actions: [{ source_action_id: "action-risk", title: "Algorithms", reason: "capacity_limit", score: 42, required_minutes: 150, shortfall_minutes: 150 }]
    });
    mockedApi.replanDay.mockResolvedValue({} as never);
    renderCalendar();

    expect(await screen.findByText(/150 minutes cannot currently be placed/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Needs Attention" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Replan day" }));
    await waitFor(() => expect(mockedApi.replanDay).toHaveBeenCalled());
  });

  it("supports complete, partial, skip, and deterministic explanation controls", async () => {
    const plan = planFixture();
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.currentPlan.mockResolvedValue(plan);
    mockedApi.completePlanBlock.mockResolvedValue(plan);
    mockedApi.partialCompletePlanBlock.mockResolvedValue(plan);
    mockedApi.skipPlanBlock.mockResolvedValue(plan);
    mockedApi.explainPlanBlock.mockResolvedValue({ plan_id: plan.id, plan_block_id: "block-study", title: "Study Macroeconomics", factors: [], summary: ["Strong afternoon completion evidence."] });
    renderCalendar();

    fireEvent.click(await screen.findByRole("button", { name: /why here study macroeconomics/i }));
    expect(await screen.findByText("Strong afternoon completion evidence.")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /^complete study macroeconomics$/i })[0]);
    fireEvent.click(screen.getByRole("button", { name: /partially complete study macroeconomics/i }));
    fireEvent.click(screen.getByRole("button", { name: /^skip study macroeconomics$/i }));
    await waitFor(() => expect(mockedApi.completePlanBlock).toHaveBeenCalled());
    expect(mockedApi.partialCompletePlanBlock).toHaveBeenCalled();
    expect(mockedApi.skipPlanBlock).toHaveBeenCalled();
  });

  it("submits an intention and can complete a planning-pool item", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.addAction.mockResolvedValue(actionFixture());
    mockedApi.completeAction.mockResolvedValue({ ...actionFixture(), status: "completed", version: 2 });
    renderCalendar();

    fireEvent.click(screen.getByRole("button", { name: /add intention/i }));
    await waitFor(() => expect(mockedApi.addAction).toHaveBeenCalled());
    expect(mockedApi.addAction.mock.calls[0][0]).toMatchObject({
      title: "Study Macroeconomics",
      domain: "learning",
      level: "goal_critical",
      estimated_minutes: 120
    });

    fireEvent.click(await screen.findByRole("button", { name: /complete study macroeconomics/i }));
    await waitFor(() => expect(mockedApi.completeAction).toHaveBeenCalledWith("action-1", 1));
  });

  it("invokes canonical commitment edit API from projection", async () => {
    mockedApi.calendarProjection.mockResolvedValue(projectionFixture());
    mockedApi.updateCommitment.mockResolvedValue({ ...commitmentFixture(), starts_at: "2026-09-16T10:00:00Z", version: 2 });
    renderCalendar();

    fireEvent.click(await screen.findByRole("button", { name: /save edit/i }));

    await waitFor(() => expect(mockedApi.updateCommitment).toHaveBeenCalled());
    expect(mockedApi.updateCommitment.mock.calls[0][0]).toBe("commitment-1");
    expect(mockedApi.updateCommitment.mock.calls[0][1]).toMatchObject({ expected_version: 1 });
  });

  it("shows a structured strategic proposal and applies it explicitly", async () => {
    const proposal: PlanProposal = {
      id: "proposal-1", exam_id: "exam-1", current_plan_id: "plan-1", current_plan_version: 1,
      current_world_revision: 8, trigger: "plan.block.missed", reason_code: "material_trajectory_shortfall",
      trajectory_snapshot: { exam_title: "Algorithms Final" }, deviation: {}, candidate_plan: {}, changes: [],
      expected_effects: {
        scheduled_minutes: { current: 60, proposed: 180, delta: 120 },
        projected_shortfall_minutes: { current: 240, proposed: 120 },
        protected_blocks_changed: 0
      },
      tradeoffs: [{ type: "EXAM_BUFFER" }], confidence: { data_completeness: 1 }, modification: {},
      authority_level: 2, attention_action: "PROPOSE", status: "PRESENTED", expires_at: "2026-09-20T00:00:00Z",
      policy_version: "plan-proposal-v1", planner_version: "v1.5-domain-intelligence",
      calculation_version: "trajectory-calculation-v1", created_at: "2026-09-16T06:30:00Z",
      updated_at: "2026-09-16T06:30:00Z", version: 1
    };
    mockedApi.planProposals.mockResolvedValue([proposal]);
    mockedApi.acceptPlanProposal.mockResolvedValue({ ...proposal, status: "ACCEPTED", applied_plan_id: "plan-2" });
    renderCalendar();

    expect(await screen.findByText("Algorithms Final")).toBeInTheDocument();
    expect(screen.getByText(/60m scheduled · 240m shortfall/i)).toBeInTheDocument();
    expect(screen.getByText(/180m scheduled · 120m shortfall/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(mockedApi.acceptPlanProposal).toHaveBeenCalled());
    expect(mockedApi.acceptPlanProposal.mock.calls[0][0]).toBe("proposal-1");
  });
});
