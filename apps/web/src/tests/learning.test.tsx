import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LearningPage } from "../features/learning/LearningPage";
import { api } from "../services/api";
import type { LearningStatus } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    learningStatus: vi.fn(),
    createLearningCourse: vi.fn(),
    addExam: vi.fn(),
    addLearningTopic: vi.fn(),
    logStudySession: vi.fn(),
    syncLearningCandidateActions: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderLearning() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return render(<LearningPage />, { wrapper: Wrapper });
}

function statusFixture(overrides: Partial<LearningStatus> = {}): LearningStatus {
  const trajectory = {
    exam_id: "exam-1",
    strategy_version: "learning-trajectory-v1",
    target_preparation_minutes: 12000,
    raw_completed_minutes: 2400,
    quality_adjusted_completed_minutes: 2520,
    remaining_quality_adjusted_minutes: 9480,
    days_remaining: 75,
    hours_remaining: 1800,
    future_capacity_minutes: 13200,
    required_daily_minutes: 127,
    required_weekly_hours: 14.8,
    load_ratio: 0.72,
    risk: "moderate",
    feasible: true,
    shortfall_minutes: 0,
    shortfall_hours: 0,
    readiness_score: 28,
    readiness_label: "early",
    topic_coverage_ratio: 0.15,
    latest_safe_start: "2026-10-01T09:00:00Z",
    behind_safe_pace: false,
    calculation_notes: {}
  };
  const course = { id: "course-1", name: "Macroeconomics", code: "MACRO", description: null, institution: null, status: "active", version: 1 };
  const topic = {
    id: "topic-1",
    exam_id: "exam-1",
    title: "National Accounting",
    order_index: 0,
    importance_weight: 1,
    estimated_required_minutes: 240,
    prerequisite_topic_id: null,
    completed_minutes: 66,
    status: "open",
    version: 1
  };
  const exam = {
    id: "exam-1",
    course_id: "course-1",
    title: "Macroeconomics Final",
    exam_date: "2026-12-20",
    exam_at: "2026-12-20T09:00:00Z",
    estimated_required_hours: 200,
    completed_hours: 40,
    target_preparation_minutes: 12000,
    minimum_required_preparation_minutes: null,
    target_quality_adjusted_minutes: 12000,
    strategy_version: "learning-trajectory-v1",
    importance: "goal_critical",
    attempts_remaining: null,
    final_attempt: false,
    exam_format: null,
    location: null,
    notes: null,
    status: "planned",
    version: 1,
    course,
    topics: [topic],
    trajectory
  };
  return {
    courses: [course],
    exams: [exam],
    active_exam: exam,
    candidates: [
      {
        candidate_id: "learning:exam-1:topic-1:standard",
        title: "Macroeconomics Final: National Accounting (standard)",
        exam_id: "exam-1",
        course_id: "course-1",
        topic_id: "topic-1",
        duration_minutes: 60,
        minimum_minutes: 35,
        maximum_minutes: 60,
        variant: "standard",
        commitment_level: "goal_critical",
        cognitive_load: 78,
        activation_difficulty: 44,
        trajectory_value: 62,
        urgency: 18,
        neglect_cost: 22,
        deadline: "2026-12-20T09:00:00Z",
        prerequisite_satisfied: true,
        expected_state_effect: {},
        metadata: {}
      }
    ],
    recent_sessions: [],
    current_learning_plan_window: [],
    ...overrides
  };
}

describe("Learning page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.learningStatus.mockResolvedValue(statusFixture());
    mockedApi.createLearningCourse.mockResolvedValue(statusFixture().courses[0]);
    mockedApi.addExam.mockResolvedValue(statusFixture().exams[0]);
    mockedApi.addLearningTopic.mockResolvedValue(statusFixture().exams[0].topics[0]);
    mockedApi.logStudySession.mockResolvedValue({
      id: "session-1",
      course_id: "course-1",
      exam_id: "exam-1",
      topic_id: "topic-1",
      source_action_id: null,
      source_plan_block_id: null,
      occurred_at: "2026-09-21T08:00:00Z",
      started_at: "2026-09-21T07:15:00Z",
      completed_at: "2026-09-21T08:00:00Z",
      duration_minutes: 45,
      quality_rating: 4,
      quality_multiplier: 1.1,
      quality_adjusted_minutes: 50,
      source: "manual",
      notes: null,
      version: 1
    });
    mockedApi.syncLearningCandidateActions.mockResolvedValue([]);
  });

  it("renders trajectory, candidates, and exam progress", async () => {
    renderLearning();

    await screen.findByRole("heading", { name: "Macroeconomics Final" });
    expect(screen.getAllByText("moderate").length).toBeGreaterThan(0);
    expect(screen.getByText("Readiness")).toBeInTheDocument();
    expect(screen.getByText(/Macroeconomics Final: National Accounting/)).toBeInTheDocument();
    expect(screen.getByText(/42h \/ 200h/)).toBeInTheDocument();
  });

  it("creates course, exam, topic, logs study, and syncs candidates", async () => {
    renderLearning();

    fireEvent.click(await screen.findByRole("button", { name: /create course/i }));
    await waitFor(() => expect(mockedApi.createLearningCourse).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: /create exam/i }));
    await waitFor(() => expect(mockedApi.addExam.mock.calls[0][0]).toEqual(expect.objectContaining({ target_preparation_minutes: 12000 })));

    fireEvent.click(screen.getByRole("button", { name: /add topic/i }));
    await waitFor(() => expect(mockedApi.addLearningTopic).toHaveBeenCalledWith("exam-1", expect.objectContaining({ title: "IS-LM Model" })));

    fireEvent.click(screen.getByRole("button", { name: /log study/i }));
    await waitFor(() => expect(mockedApi.logStudySession).toHaveBeenCalledWith(expect.objectContaining({ duration_minutes: 45, quality_rating: 4 })));

    fireEvent.click(screen.getByRole("button", { name: /sync to planner/i }));
    await waitFor(() => expect(mockedApi.syncLearningCandidateActions).toHaveBeenCalled());
  });

  it("renders explicit infeasibility", async () => {
    const data = statusFixture();
    data.active_exam = {
      ...data.active_exam!,
      trajectory: {
        ...data.active_exam!.trajectory!,
        feasible: false,
        risk: "infeasible",
        shortfall_minutes: 2400,
        shortfall_hours: 40
      }
    };
    data.exams = [data.active_exam];
    mockedApi.learningStatus.mockResolvedValue(data);

    renderLearning();

    expect(await screen.findByText("Infeasible Under Current Assumptions")).toBeInTheDocument();
    expect(screen.getByText(/40h short/)).toBeInTheDocument();
  });
});
