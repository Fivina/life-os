import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps, PropsWithChildren } from "react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
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
let navigateFromTest: ReturnType<typeof useNavigate>;

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

function renderAssistant(initialPath = "/assistant", props: ComponentProps<typeof AssistantPage> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    function RouterProbe() {
      const location = useLocation();
      navigateFromTest = useNavigate();
      return <div data-testid="router-location">{location.pathname}{location.search}{location.hash}</div>;
    }
    return (
      <MemoryRouter initialEntries={[initialPath]}>
        <QueryClientProvider client={queryClient}><RouterProbe />{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(<AssistantPage {...props} />, { wrapper: Wrapper });
}

describe("Assistant page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockedApi.listAssistantThreads.mockResolvedValue([]);
    mockedApi.intelligenceSettings.mockResolvedValue({
      live_agents_enabled: false,
      agents: [
        { skill_name: "self-core", name: "General", roles: ["GENERAL_ASSISTANT"], credential_configured: true, profile: { display_name: "General" } },
        { skill_name: "learning-coach", name: "Learning", roles: ["LEARNING_COACH"], credential_configured: true, profile: { display_name: "Learning" } },
        { skill_name: "chef", name: "Chef", roles: ["CHEF"], credential_configured: false, profile: { display_name: "Chef" } }
      ]
    } as never);
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

    expect(screen.getByRole("heading", { name: "New conversation" })).toBeInTheDocument();
    expect(await screen.findByText("Good morning. Algorithms at 09:00.")).toBeInTheDocument();
    expect(screen.getByText("General Assistant")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "What workout is next?" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));

    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ message: "What workout is next?" })));
    expect(await screen.findByText("Here is the current summary.")).toBeInTheDocument();
    expect(screen.getByText("fake · life-os-fake-standard")).toBeInTheDocument();
    expect(await screen.findByText(/Deterministic test responses are active/)).toBeInTheDocument();
  });

  it("starts a clean conversation and fills a sample prompt without sending it", async () => {
    const thread: ConversationThread = {
      id: "new-thread", title: "New conversation", status: "active", default_skill: "self-core",
      last_message_at: "2026-09-28T09:00:00Z", created_at: "2026-09-28T09:00:00Z", updated_at: "2026-09-28T09:00:00Z", version: 1,
    };
    mockedApi.createAssistantThread.mockResolvedValue(thread);
    mockedApi.getAssistantThread.mockResolvedValue({ ...thread, messages: [] });
    renderAssistant();

    fireEvent.click(await screen.findByRole("button", { name: "New conversation" }));
    await waitFor(() => expect(mockedApi.createAssistantThread).toHaveBeenCalledWith({ default_skill: "self-core" }));
    await waitFor(() => expect(screen.getByTestId("router-location")).toHaveTextContent("thread=new-thread"));
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

    await screen.findByRole("option", { name: "Learning" });
    fireEvent.change(screen.getByLabelText("Assistant role"), { target: { value: "LEARNING_COACH" } });
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
    const created = { id: "new-thread", title: "New conversation", status: "active", default_skill: "self-core", last_message_at: "", created_at: "", updated_at: "", version: 1 } as ConversationThread;
    mockedApi.getAssistantThread.mockResolvedValue({ ...created, messages: [] });
    resolveThread?.(created);
    await waitFor(() => expect(screen.getByLabelText(/message assistant/i)).toHaveValue(draft));
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
    expect(mockedApi.assistantMessage.mock.calls[1][0].recent_messages).toEqual([]);
  });
  it("locks thread and role controls until the current response finishes", async () => {
    let finish: ((response: AssistantResponse) => void) | undefined;
    mockedApi.assistantMessage.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/message assistant/i), { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: /^send/i }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledOnce());
    expect(screen.getByRole("button", { name: "New conversation" })).toBeDisabled();
    expect(screen.getByLabelText("Assistant role")).toBeDisabled();
    finish?.(responseFixture({ message: "Hello back" }));
    await screen.findByText("Hello back");
    expect(screen.getByRole("button", { name: "New conversation" })).toBeEnabled();
    expect(screen.getByLabelText("Assistant role")).toBeEnabled();
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
    fireEvent.change(screen.getByLabelText("Assistant role"), { target: { value: "CHEF" } });
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
    expect(screen.getByRole("button", { name: /proposal-thread/i })).toHaveAttribute("aria-current", "page");
  });

  it("shows only registered roles and reports their configuration truthfully", async () => {
    renderAssistant();
    expect(await screen.findByRole("option", { name: "Chef · not configured" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "General" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /calendar/i })).not.toBeInTheDocument();
  });

  it("filters persisted threads and preserves a separate draft for each thread", async () => {
    const threads = ["alpha-thread", "beta-thread"].map((id) => ({
      id, title: id === "alpha-thread" ? "Alpha plan" : "Beta review", status: "active", default_skill: "self-core",
      last_message_at: "2026-10-08T10:00:00Z", created_at: "2026-10-08T09:00:00Z", updated_at: "2026-10-08T10:00:00Z", version: 1
    } as ConversationThread));
    mockedApi.listAssistantThreads.mockResolvedValue(threads);
    mockedApi.getAssistantThread.mockImplementation(async (id) => ({ ...threads.find((thread) => thread.id === id)!, messages: [] }));
    renderAssistant("/chat?thread=alpha-thread");
    await screen.findByRole("heading", { name: "Alpha plan" });
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "alpha draft" } });
    fireEvent.change(screen.getByLabelText("Search conversations"), { target: { value: "Beta" } });
    expect(screen.queryByRole("button", { name: /Alpha plan/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Beta review/i }));
    expect(screen.getByTestId("router-location")).toHaveTextContent("thread=beta-thread");
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "beta draft" } });
    fireEvent.change(screen.getByLabelText("Search conversations"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Alpha plan/i }));
    expect(screen.getByLabelText("Message assistant")).toHaveValue("alpha draft");
  });

  it("keeps an invalid deep link selected instead of opening an unrelated latest thread", async () => {
    const latest: ConversationThread = { id: "latest", title: "Latest", status: "active", default_skill: "self-core", last_message_at: "2026-10-08T10:00:00Z", created_at: "", updated_at: "", version: 1 };
    mockedApi.listAssistantThreads.mockResolvedValue([latest]);
    mockedApi.getAssistantThread.mockRejectedValue(new Error("not found"));
    renderAssistant("/chat?thread=missing");
    expect(await screen.findByRole("alert")).toHaveTextContent("Conversation unavailable");
    expect(mockedApi.getAssistantThread).toHaveBeenCalledWith("missing");
    expect(mockedApi.getAssistantThread).not.toHaveBeenCalledWith("latest");
    expect(screen.getByTestId("router-location")).toHaveTextContent("thread=missing");
  });

  it("does not place a late response into a thread opened through browser history", async () => {
    const threads = ["thread-a", "thread-b"].map((id) => ({
      id, title: id, status: "active", default_skill: "self-core", last_message_at: "2026-10-08T10:00:00Z", created_at: "", updated_at: "", version: 1
    } as ConversationThread));
    mockedApi.listAssistantThreads.mockResolvedValue(threads);
    mockedApi.getAssistantThread.mockImplementation(async (id) => ({ ...threads.find((thread) => thread.id === id)!, messages: id === "thread-b" ? [{
      id: "b-message", thread_id: id, role: "assistant", content: "Thread B history", skill_name: "self-core", request_id: "b-request",
      sequence_number: 1, metadata_json: { response_type: "INFORMATION" }, created_at: "2026-10-08T10:00:00Z"
    }] : [] }));
    let finish: ((response: AssistantResponse) => void) | undefined;
    mockedApi.assistantMessage.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    renderAssistant("/chat?thread=thread-a");
    await screen.findByRole("heading", { name: "thread-a" });
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "slow request" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledOnce());
    navigateFromTest("/chat?thread=thread-b");
    expect(await screen.findByText("Thread B history")).toBeInTheDocument();
    finish?.(responseFixture({ message: "Late response for A", thread_id: "thread-a" }));
    await waitFor(() => expect(screen.queryByText("Late response for A")).not.toBeInTheDocument());
    expect(screen.getByText("Thread B history")).toBeInTheDocument();
  });

  it("sends in embedded mode without reading or changing the host route", async () => {
    mockedApi.assistantMessage.mockResolvedValue(responseFixture({ message: "Calendar answer", thread_id: "calendar-thread" }));
    const openFull = vi.fn();
    renderAssistant("/calendar?day=2026-10-08#agenda", { mode: "embedded", workspaceKey: "calendar", onOpenFullChat: openFull });
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "What is next?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Calendar answer")).toBeInTheDocument();
    expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ role: "GENERAL_ASSISTANT", thread_id: null }));
    expect(screen.getByTestId("router-location")).toHaveTextContent("/calendar?day=2026-10-08#agenda");
    expect(sessionStorage.getItem("life-os:chat-thread:calendar")).toBe("calendar-thread");
    expect(mockedApi.listAssistantThreads).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Open in Chat" }));
    expect(openFull).toHaveBeenCalledWith("calendar-thread");
  });

  it("restores the embedded workspace thread and unsent draft after remount", async () => {
    const thread: ConversationThread = { id: "kitchen-thread", title: "Meal prep", status: "active", default_skill: "chef", last_message_at: "2026-10-08T10:00:00Z", created_at: "", updated_at: "", version: 1 };
    sessionStorage.setItem("life-os:chat-thread:kitchen", thread.id);
    sessionStorage.setItem("life-os:chat-draft:embedded:kitchen:kitchen-thread", "Use the spinach");
    mockedApi.getAssistantThread.mockResolvedValue({ ...thread, messages: [] });
    const first = renderAssistant("/kitchen?tab=fridge#item", { mode: "embedded", workspaceKey: "kitchen" });
    expect(await screen.findByRole("heading", { name: "Meal prep" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message assistant")).toHaveValue("Use the spinach");
    first.unmount();
    renderAssistant("/kitchen?tab=fridge#item", { mode: "embedded", workspaceKey: "kitchen" });
    expect(await screen.findByRole("heading", { name: "Meal prep" })).toBeInTheDocument();
    expect(screen.getByLabelText("Message assistant")).toHaveValue("Use the spinach");
    expect(screen.getByTestId("router-location")).toHaveTextContent("/kitchen?tab=fridge#item");
  });

  it("isolates an invalid embedded saved thread and can start a replacement", async () => {
    sessionStorage.setItem("life-os:chat-thread:calendar", "missing-calendar-thread");
    mockedApi.getAssistantThread.mockRejectedValue(new Error("not found"));
    mockedApi.createAssistantThread.mockResolvedValue({ id: "replacement", title: "New conversation", status: "active", default_skill: "self-core", last_message_at: "2026-10-08T10:00:00Z", created_at: "", updated_at: "", version: 1 });
    renderAssistant("/calendar?view=week", { mode: "embedded", workspaceKey: "calendar" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Conversation unavailable");
    expect(mockedApi.getAssistantThread).toHaveBeenCalledWith("missing-calendar-thread");
    expect(mockedApi.listAssistantThreads).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    await waitFor(() => expect(sessionStorage.getItem("life-os:chat-thread:calendar")).toBe("replacement"));
    expect(screen.getByTestId("router-location")).toHaveTextContent("/calendar?view=week");
  });

  it("starts Kitchen with its registered role and permits an explicit role switch", async () => {
    mockedApi.assistantMessage.mockResolvedValue(responseFixture({ message: "Learning answer", role_used: "LEARNING_COACH", thread_id: "kitchen-learning" }));
    renderAssistant("/kitchen", { mode: "embedded", workspaceKey: "kitchen" });
    await screen.findByRole("option", { name: "Learning" });
    expect(screen.getByLabelText("Assistant role")).toHaveValue("CHEF");
    fireEvent.change(screen.getByLabelText("Assistant role"), { target: { value: "LEARNING_COACH" } });
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "Explain this technique" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ role: "LEARNING_COACH" })));
    expect(await screen.findByText("Learning answer")).toBeInTheDocument();
    expect(screen.getByTestId("router-location")).toHaveTextContent("/kitchen");
  });

  it("does not append a deferred approval result after history opens another thread", async () => {
    const threads = ["approval-a", "thread-b"].map((id) => ({ id, title: id, status: "active", default_skill: "self-core", last_message_at: "2026-10-08T10:00:00Z", created_at: "", updated_at: "", version: 1 } as ConversationThread));
    mockedApi.listAssistantThreads.mockResolvedValue(threads);
    mockedApi.getAssistantThread.mockImplementation(async (id) => ({ ...threads.find((item) => item.id === id)!, messages: id === "approval-a" ? [{
      id: "proposal-message", thread_id: id, role: "assistant", content: "Approve this", skill_name: "self-core", sequence_number: 1, created_at: "",
      metadata_json: { response_type: "PROPOSAL", proposed_action: { id: "deferred-proposal", tool_name: "create_commitment", arguments: {}, summary: "Create it", consequence_category: "consequential", status: "pending", expires_at: "2026-10-09T10:00:00Z", confirmation_required: true, version: 1 } }
    }] : [{ id: "b", thread_id: id, role: "assistant", content: "Thread B stays clean", skill_name: "self-core", sequence_number: 1, created_at: "", metadata_json: { response_type: "INFORMATION" } }] }));
    let finish: ((response: AssistantResponse) => void) | undefined;
    mockedApi.confirmAssistantProposal.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    renderAssistant("/chat?thread=approval-a");
    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /thread-b/i })).toBeDisabled());
    expect(screen.getByLabelText("Assistant role")).toBeDisabled();
    navigateFromTest("/chat?thread=thread-b");
    expect(await screen.findByText("Thread B stays clean")).toBeInTheDocument();
    finish?.(responseFixture({ message: "Approval finished for A", response_type: "MUTATION_RESULT" }));
    await waitFor(() => expect(screen.queryByText("Approval finished for A")).not.toBeInTheDocument());
  });

  it("normalizes an unavailable Kitchen default to a registered role before sending", async () => {
    mockedApi.intelligenceSettings.mockResolvedValue({ live_agents_enabled: true, agents: [
      { skill_name: "self-core", name: "General", roles: ["GENERAL_ASSISTANT"], credential_configured: true, profile: { display_name: "General" } }
    ] } as never);
    mockedApi.assistantMessage.mockResolvedValue(responseFixture({ message: "General response", thread_id: "general-thread" }));
    renderAssistant("/kitchen", { mode: "embedded", workspaceKey: "kitchen" });
    await waitFor(() => expect(screen.getByLabelText("Assistant role")).toHaveValue("GENERAL_ASSISTANT"));
    fireEvent.change(screen.getByLabelText("Message assistant"), { target: { value: "Help me" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(mockedApi.assistantMessage).toHaveBeenCalledWith(expect.objectContaining({ role: "GENERAL_ASSISTANT" })));
  });
});
