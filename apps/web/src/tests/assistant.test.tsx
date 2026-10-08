import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPage } from "../features/assistant/AssistantPage";
import { api } from "../services/api";
import type { AssistantResponse, ConversationThread } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    listAssistantThreads: vi.fn(),
    getAssistantThread: vi.fn(),
    createAssistantThread: vi.fn(),
    assistantMessage: vi.fn(),
    confirmAssistantProposal: vi.fn(),
    cancelAssistantProposal: vi.fn(),
    getFeedbackSession: vi.fn(),
    submitFeedbackClarification: vi.fn(),
    submitFeedbackResponse: vi.fn(),
    completeFeedback: vi.fn(),
    cancelFeedback: vi.fn()
    , morningBriefing: vi.fn()
    , foregroundWorkspace: vi.fn()
    , resumeWorkspace: vi.fn()
    , planProposals: vi.fn()
    , acceptPlanProposal: vi.fn()
    , rejectPlanProposal: vi.fn()
    , intelligenceSettings: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function responseFixture(overrides: Partial<AssistantResponse> = {}): AssistantResponse {
  return {
    message: "Here is the current summary.",
    role_used: "GENERAL_ASSISTANT",
    response_type: "INFORMATION",
    entity_references: [],
    request_id: crypto.randomUUID(),
    provider: "fake",
    model: "life-os-fake-standard",
    model_tier: "STANDARD",
    ...overrides
  };
}

function renderAssistant(initialPath = "/assistant") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(<AssistantPage />, { wrapper: Wrapper });
}

describe("Assistant page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listAssistantThreads.mockResolvedValue([]);
    mockedApi.intelligenceSettings.mockResolvedValue({ live_agents_enabled: false } as never);
    mockedApi.foregroundWorkspace.mockResolvedValue(null);
    mockedApi.planProposals.mockResolvedValue([]);
    mockedApi.morningBriefing.mockResolvedValue({
      context: {
        date: "2026-09-28", generated_at: "2026-09-28T07:30:00Z", fingerprint: "morning-1",
        plan_id: "plan-1", plan_version: 2, world_revision: 4,
        first_block: { ref_type: "plan_block", ref_id: "block-1", title: "Algorithms", starts_at: "2026-09-28T09:00:00Z", detail: "learning" },
        important_blocks: [{ ref_type: "plan_block", ref_id: "block-1", title: "Algorithms", starts_at: "2026-09-28T09:00:00Z", detail: "learning" }],
        protected_commitments: [], trajectory_changes: [], active_proposals: [], attention_items: [], kitchen_signals: [],
        omitted_categories: ["finance"], source_refs: ["plan:plan-1:v2"], briefing_policy_version: "morning-briefing-v1"
      },
      message: "Good morning. Algorithms at 09:00.", reused: true, plan_created: false
    });
  });

  it("renders empty state and submits a message", async () => {
    mockedApi.assistantMessage.mockResolvedValue(responseFixture({ provider: "fake", model: "life-os-fake-standard" }));
    renderAssistant();

    expect(screen.getByRole("heading", { name: "Self Core" })).toBeInTheDocument();
    expect(await screen.findByText("Good morning. Algorithms at 09:00.")).toBeInTheDocument();
    expect(screen.getByText("General Assistant")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "What workout is next?" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));

    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ message: "What workout is next?" })));
    expect(await screen.findByText("Here is the current summary.")).toBeInTheDocument();
    expect(screen.getByText("fake · life-os-fake-standard")).toBeInTheDocument();
    expect(await screen.findByRole("status")).toHaveTextContent("Deterministic test responses are active");
  });

  it("starts a clean conversation and fills a sample prompt without sending it", async () => {
    const thread: ConversationThread = {
      id: "new-thread", title: "New conversation", status: "active", default_skill: "self-core",
      last_message_at: "2026-09-28T09:00:00Z", created_at: "2026-09-28T09:00:00Z", updated_at: "2026-09-28T09:00:00Z", version: 1,
    };
    mockedApi.createAssistantThread.mockResolvedValue(thread);
    renderAssistant();

    fireEvent.click(await screen.findByRole("button", { name: "New conversation" }));
    expect(await screen.findByText("What would you like to work through today?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Which agents can I use?" }));
    expect(screen.getByLabelText(/message assistant/i)).toHaveValue("Which agents can I use?");
    expect(mockedApi.assistantMessage).not.toHaveBeenCalled();
  });

  it("surfaces the foreground workspace and relevant morning attention", async () => {
    mockedApi.foregroundWorkspace.mockResolvedValue({ id: "workspace-1", workspace_type: "COOKING", status: "ACTIVE", is_foreground: true, current_step: "Simmer", payload: {}, state_revision: 3 });
    mockedApi.morningBriefing.mockResolvedValue({
      context: {
        date: "2026-09-28", generated_at: "2026-09-28T07:30:00Z", fingerprint: "morning-2",
        plan_id: "plan-1", plan_version: 2, world_revision: 4, important_blocks: [], protected_commitments: [], trajectory_changes: [], active_proposals: [],
        attention_items: [{ ref_type: "attention_item", ref_id: "attention-1", title: "Review missed study", status: "MENTION_WHEN_NATURAL", detail: "study" }],
        active_workspace: { ref_type: "active_workspace", ref_id: "workspace-1", title: "Cooking", status: "ACTIVE", detail: "Simmer" },
        kitchen_signals: [], omitted_categories: [], source_refs: ["workspace:workspace-1:r3"], briefing_policy_version: "morning-briefing-v1"
      },
      message: "Good morning.", reused: true, plan_created: false
    });
    mockedApi.resumeWorkspace.mockResolvedValue({ id: "workspace-1", workspace_type: "COOKING", status: "ACTIVE", is_foreground: true, current_step: "Simmer", payload: {}, state_revision: 3 });
    renderAssistant();
    expect(await screen.findByRole("heading", { name: "cooking" })).toBeInTheDocument();
    expect(await screen.findByText("Review missed study")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(mockedApi.resumeWorkspace).toHaveBeenCalledWith("workspace-1"));
  });

  it("renders clarification, no-action, provider error, and explanation states", async () => {
    mockedApi.assistantMessage
      .mockResolvedValueOnce(responseFixture({ message: "What are your Energy and Mental State from 0-100?", response_type: "CLARIFICATION" }))
      .mockResolvedValueOnce(responseFixture({ message: "No Life OS data was changed.", response_type: "NO_ACTION" }))
      .mockResolvedValueOnce(responseFixture({ message: "Provider unavailable.", response_type: "ERROR", error_code: "provider_unavailable" }))
      .mockResolvedValueOnce(
        responseFixture({
          message: "Plan block explained.",
          explanation: { title: "Study Macroeconomics", summary: "Selected from stored decision factors.", factors: [{ factor: "urgency" }] }
        })
      );
    renderAssistant();

    for (const text of ["I feel worse", "Maybe I should skip gym", "provider failure", "Why is Macro scheduled?"]) {
      fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: text } });
      fireEvent.click(screen.getByRole("button", { name: /^send/i }));
      await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledTimes(["I feel worse", "Maybe I should skip gym", "provider failure", "Why is Macro scheduled?"].indexOf(text) + 1));
    }

    expect(await screen.findByText(/Energy and Mental State/i)).toBeInTheDocument();
    expect((await screen.findAllByText("No Life OS data was changed.")).length).toBeGreaterThan(0);
    expect(await screen.findByText("provider unavailable")).toBeInTheDocument();
    expect(await screen.findByText("Selected from stored decision factors.")).toBeInTheDocument();
  });

  it("renders proposal and confirms it", async () => {
    mockedApi.assistantMessage.mockResolvedValue(
      responseFixture({
        message: "Review this proposed action before I change Life OS.",
        response_type: "PROPOSAL",
        proposed_action: {
          id: "proposal-1",
          tool_name: "create_commitment",
          arguments: { title: "Meeting Friend", starts_at: "2026-09-16T11:00:00Z", ends_at: "2026-09-16T16:00:00Z" },
          summary: "Create commitment: Meeting Friend, tomorrow 11:00-16:00.",
          consequence_category: "consequential",
          expected_world_revision: 1,
          status: "pending",
          expires_at: "2026-09-15T12:00:00Z",
          confirmation_required: true,
          version: 1
        }
      })
    );
    mockedApi.confirmAssistantProposal.mockResolvedValue(
      responseFixture({
        message: "Commitment created: Meeting Friend.",
        response_type: "MUTATION_RESULT",
        mutation_result: { tool_name: "create_commitment", entity_type: "commitment", entity_id: "commitment-1", world_revision: 2, result: {} }
      })
    );
    renderAssistant();

    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "Meeting friend at university tomorrow at 11 for 5h" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));

    expect((await screen.findAllByText(/Create commitment/i)).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /^confirm/i }));

    await waitFor(() => expect(mockedApi.confirmAssistantProposal).toHaveBeenCalled());
    expect(mockedApi.confirmAssistantProposal.mock.calls[0][0]).toBe("proposal-1");
    expect(await screen.findByText("Commitment created: Meeting Friend.")).toBeInTheDocument();
    expect(await screen.findByText(/World revision 2/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^confirm/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^cancel/i })).toBeDisabled();
  });

  it("cancels a proposal and supports specialist role selection", async () => {
    mockedApi.assistantMessage.mockResolvedValue(
      responseFixture({
        role_used: "LEARNING_COACH",
        message: "Review this proposed action before I change Life OS.",
        response_type: "PROPOSAL",
        proposed_action: {
          id: "proposal-2",
          tool_name: "log_study_session",
          arguments: { duration_minutes: 50, quality_rating: 4 },
          summary: "Log study: 50 minutes, quality 4.",
          consequence_category: "consequential",
          expected_world_revision: 3,
          status: "pending",
          expires_at: "2026-09-15T12:00:00Z",
          confirmation_required: true,
          version: 1
        }
      })
    );
    mockedApi.cancelAssistantProposal.mockResolvedValue(responseFixture({ message: "Cancelled. No Life OS data was changed.", response_type: "NO_ACTION" }));
    renderAssistant();

    fireEvent.click(screen.getByRole("button", { name: "Learning" }));
    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "I studied macro for 50 minutes, quality 4." } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));

    expect((await screen.findAllByText(/Log study/i)).length).toBeGreaterThan(0);
    expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ role: "LEARNING_COACH" }));
    fireEvent.click(screen.getByRole("button", { name: /^cancel/i }));
    await waitFor(() => expect(mockedApi.cancelAssistantProposal).toHaveBeenCalled());
    expect(mockedApi.cancelAssistantProposal.mock.calls[0][0]).toBe("proposal-2");
    expect(await screen.findByText("Cancelled. No Life OS data was changed.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^confirm/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^cancel/i })).toBeDisabled();
  });

  it("prefills from Home Ask/Add query parameter", () => {
    renderAssistant("/assistant?q=Study%20macro");

    expect(screen.getByLabelText(/message assistant/i)).toHaveValue("Study macro");
  });

  it("keeps a drafted message from being sent while creating a new conversation", async () => {
    let resolveThread: ((thread: ConversationThread) => void) | undefined;
    mockedApi.createAssistantThread.mockImplementation(() => new Promise((resolve) => { resolveThread = resolve; }));
    mockedApi.assistantMessage.mockResolvedValue(responseFixture());
    renderAssistant();

    const draft = "Send this only after the new thread exists";
    fireEvent.click(screen.getByRole("button", { name: /new conversation/i }));
    const input = screen.getByLabelText(/message assistant/i);
    fireEvent.change(input, { target: { value: draft } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);

    expect(mockedApi.assistantMessage).not.toHaveBeenCalled();
    expect(input).toHaveValue(draft);
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    resolveThread?.({ id: "new-thread", title: "New conversation", status: "active", default_skill: "self-core", last_message_at: "", created_at: "", updated_at: "", version: 1 });
  });

  it("opens nested feedback and accepts score zero", async () => {
    const activeState = {
      result_code: "STARTED",
      session_id: "feedback-1",
      status: "ACTIVE" as const,
      current_question_index: 0,
      questions_planned_count: 1,
      questions_answered_count: 0,
      clarification: null,
      next_question: {
        question_id: "feedback.timing.v1",
        question_version: 1,
        dimension: "TIMING" as const,
        prompt: "Was the timing right?",
        low_label: "Completely wrong",
        high_label: "Exactly right"
      },
      resume_state: {}
    };
    mockedApi.assistantMessage.mockResolvedValueOnce(
      responseFixture({
        message: "Feedback session started.",
        response_type: "FEEDBACK",
        model_tier: "NO_AI",
        provider: null,
        model: null,
        feedback_session_id: "feedback-1",
        feedback_status: "ACTIVE"
      })
    ).mockResolvedValueOnce(responseFixture({ message: "Back to the original activity." }));
    mockedApi.getFeedbackSession.mockResolvedValue(activeState);
    mockedApi.submitFeedbackResponse.mockResolvedValue({
      ...activeState,
      result_code: "ANSWERED",
      current_question_index: 1,
      questions_answered_count: 1,
      next_question: null
    });
    mockedApi.completeFeedback.mockResolvedValue({
      ...activeState,
      result_code: "COMPLETED",
      status: "COMPLETED",
      current_question_index: 1,
      questions_answered_count: 1,
      next_question: null
    });
    renderAssistant();

    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "Log feedback" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));

    expect(await screen.findByRole("dialog", { name: /help life os learn/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Score 0" }));

    await waitFor(() =>
      expect(mockedApi.submitFeedbackResponse).toHaveBeenCalledWith(
        "feedback-1",
        expect.objectContaining({ score: 0, is_skipped: false })
      )
    );
    await waitFor(() => expect(mockedApi.completeFeedback).toHaveBeenCalledWith("feedback-1"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "Continue" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledTimes(2));
    expect(mockedApi.assistantMessage.mock.calls[1][0].recent_messages).toEqual([
      { role: "user", content: "Continue" }
    ]);
  });
  it("locks thread and role controls until the current response finishes", async () => {
    let finish: ((response: AssistantResponse) => void) | undefined;
    mockedApi.assistantMessage.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledOnce());
    expect(screen.getByLabelText("Conversation")).toBeDisabled();
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Chef" })).toBeDisabled();
    finish?.(responseFixture({ message: "Hello back" }));
    await screen.findByText("Hello back");
    expect(screen.getByRole("button", { name: "New conversation" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Chef" })).toBeEnabled();
  });
  it("restores specialist identity and validated work logs from saved messages", async () => {
    const thread: ConversationThread = { id: "saved-thread", title: "Saved quiz", status: "active", default_skill: "self-core", last_message_at: "", created_at: "", updated_at: "", version: 1 };
    mockedApi.listAssistantThreads.mockResolvedValueOnce([thread]);
    mockedApi.getAssistantThread.mockResolvedValueOnce({ ...thread, messages: [{
      id: "saved-message", thread_id: thread.id, role: "assistant", content: "One saved quiz question", skill_name: "learning-coach", sequence_number: 1, created_at: "",
      metadata_json: { response_type: "INFORMATION", work_log: [
        { sequence: 1, kind: "model", skill_name: "learning-coach", tool_name: null, status: "completed" },
        { sequence: 0, kind: "tool", skill_name: "learning-coach", tool_name: null, status: "completed" },
      ] },
    }] });
    renderAssistant();
    const message = await screen.findByText("One saved quiz question");
    expect(message.closest("article")).toHaveTextContent("Learning");
    expect(message.closest("article")).toHaveTextContent("Work log (1)");
    fireEvent.click(screen.getByRole("button", { name: "Chef" }));
    expect(message.closest("article")).toHaveTextContent("Learning");
  });

  it("restores an agent proposal card and keeps approval explicit after reload", async () => {
    const thread: ConversationThread = { id: "saved-proposal", title: "Saved meeting", status: "active", default_skill: "self-core", last_message_at: "", created_at: "", updated_at: "", version: 1 };
    mockedApi.listAssistantThreads.mockResolvedValueOnce([thread]);
    mockedApi.getAssistantThread.mockResolvedValueOnce({ ...thread, messages: [{
      id: "saved-action", thread_id: thread.id, role: "assistant", content: "I can add this meeting.", skill_name: "self-core", sequence_number: 1, created_at: "",
      metadata_json: { response_type: "PROPOSAL", proposed_action: { id: "proposal-saved", tool_name: "create_commitment", arguments: { title: "Meet Deniz" },
        summary: "Add meeting with Deniz", consequence_category: "consequential", expected_world_revision: 4, status: "pending", expires_at: "2026-10-03T12:00:00Z", confirmation_required: true, version: 1 } },
    }] });
    renderAssistant();
    expect(await screen.findByText("Add meeting with Deniz")).toBeInTheDocument();
    expect(mockedApi.confirmAssistantProposal).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("opens the exact saved conversation linked from a home proposal card", async () => {
    const threads = ["newer-thread", "proposal-thread"].map(id => ({
      id, title: id, status: "active", default_skill: "self-core", last_message_at: "", created_at: "", updated_at: "", version: 1,
    } as ConversationThread));
    mockedApi.listAssistantThreads.mockResolvedValueOnce(threads);
    mockedApi.getAssistantThread.mockResolvedValueOnce({ ...threads[1], messages: [{
      id: "proposal-message", thread_id: "proposal-thread", role: "assistant", content: "Review the meeting", skill_name: "self-core",
      sequence_number: 1, created_at: "", metadata_json: { response_type: "INFORMATION" },
    }] });
    renderAssistant("/self/assistant?thread=proposal-thread");
    await waitFor(() => expect(mockedApi.getAssistantThread).toHaveBeenCalledWith("proposal-thread"));
    expect(await screen.findByText("Review the meeting")).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation")).toHaveValue("proposal-thread");
  });
});
