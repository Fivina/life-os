import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LifePage } from "../features/life/LifePage";
import { api } from "../services/api";
import type { Goal, GoalsOverview, HouseholdOverview, HouseholdTask } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    goalsOverview: vi.fn(),
    householdOverview: vi.fn(),
    createGoal: vi.fn(),
    createHouseholdTask: vi.fn(),
    completeHouseholdTask: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderLife() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return render(<LifePage />, { wrapper: Wrapper });
}

function goalFixture(): Goal {
  return {
    id: "goal-1",
    title: "Finish the semester strongly",
    domain: "learning",
    status: "active",
    priority: 80,
    target_date: "2026-12-15T00:00:00Z",
    progress_mode: "derived",
    active: true,
    progress: 62,
    trajectory: {
      id: "trajectory-1",
      goal_id: "goal-1",
      name: "Exam preparation",
      metric_name: "readiness",
      target_value: 100,
      current_value: 62,
      unit: "%",
      status: "on_track",
      risk: "low",
      on_track: true,
      target_date: "2026-12-15T00:00:00Z",
      metadata_json: {}
    },
    milestones: [],
    linked_upcoming_actions: [],
    version: 1
  };
}

function householdTaskFixture(): HouseholdTask {
  return {
    id: "task-1",
    title: "Laundry",
    category: "cleaning",
    recurrence: { type: "interval", days: 7 },
    estimated_duration_minutes: 45,
    minimum_duration_minutes: 20,
    location: "home",
    priority: 50,
    next_due_at: "2026-09-21T08:00:00Z",
    active: true,
    due_status: "due",
    version: 3
  };
}

describe("Life domain intelligence", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const goals: GoalsOverview = {
      goals: [goalFixture()],
      weekly_focus: [{ id: "focus-1", week_start: "2026-09-21", goal_id: "goal-1", title: "Exam week", priority_boost: 15, active: true, version: 1 }]
    };
    const household: HouseholdOverview = {
      due: [householdTaskFixture()],
      upcoming: [],
      recently_completed: [],
      active_count: 1
    };

    mockedApi.goalsOverview.mockResolvedValue(goals);
    mockedApi.householdOverview.mockResolvedValue(household);
    mockedApi.createGoal.mockResolvedValue(goalFixture());
    mockedApi.createHouseholdTask.mockResolvedValue(householdTaskFixture());
    mockedApi.completeHouseholdTask.mockResolvedValue({ ...householdTaskFixture(), due_status: "upcoming", version: 4 });
  });

  it("renders and operates the goals and household loops", async () => {
    renderLife();

    expect(await screen.findByText("Finish the semester strongly")).toBeInTheDocument();
    expect(screen.getByText("Laundry")).toBeInTheDocument();
    expect(screen.getByText("Active goals").closest("article")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: "Complete Laundry" }));
    await waitFor(() => expect(mockedApi.completeHouseholdTask).toHaveBeenCalledWith("task-1", 3));

    fireEvent.change(screen.getByPlaceholderText("Meaningful outcome"), { target: { value: "Run a half marathon" } });
    fireEvent.click(screen.getByRole("button", { name: /add goal/i }));
    await waitFor(() => expect(mockedApi.createGoal).toHaveBeenCalled());
    expect(mockedApi.createGoal.mock.calls[0][0]).toMatchObject({ title: "Run a half marathon" });

    fireEvent.click(screen.getByRole("button", { name: /add recurrence/i }));
    await waitFor(() => expect(mockedApi.createHouseholdTask).toHaveBeenCalled());
    expect(mockedApi.createHouseholdTask.mock.calls[0][0]).toMatchObject({
      title: "Laundry",
      recurrence: { type: "interval", days: 7 },
      estimated_duration_minutes: 45
    });
  });
});
