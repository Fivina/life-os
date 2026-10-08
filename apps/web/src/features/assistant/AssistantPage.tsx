import { AlertTriangle, CalendarDays, Check, Clock3, Inbox, Info, Play, Plus, RefreshCw, Send, ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../../services/api";
import { parseAgentActivity } from "../../services/assistantStream";
import type { AgentWorkActivity, AssistantResponse, AssistantRole, FeedbackSessionState } from "../../types/api";

type Entry = {
  id: string;
  kind: "user" | "assistant";
  text: string;
  response?: AssistantResponse;
  excludeFromContext?: boolean;
  workLog?: AgentWorkActivity[];
};

const ROLE_OPTIONS: Array<{ label: string; value: AssistantRole }> = [
  { label: "General", value: "GENERAL_ASSISTANT" },
  { label: "Fitness", value: "FITNESS_COACH" },
  { label: "Learning", value: "LEARNING_COACH" },
  { label: "Home", value: "HOME_MANAGER" },
  { label: "Chef", value: "CHEF" },
  { label: "Finance", value: "FINANCE_ADVISOR" }
];

function statusLabel(response: AssistantResponse) {
  return response.response_type.replaceAll("_", " ").toLowerCase();
}

function formatArgumentValue(value: unknown) {
  if (value == null) {
    return "--";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

const SKILL_ROLES: Record<string, AssistantRole> = {
  "self-core": "GENERAL_ASSISTANT", chef: "CHEF", "learning-coach": "LEARNING_COACH",
  "fitness-coach": "FITNESS_COACH", "home-manager": "HOME_MANAGER", finance: "FINANCE_ADVISOR",
};

function roleLabel(role: AssistantRole, agents?: Array<{ skill_name?: string; roles: string[]; profile?: { display_name: string } }>, skillName?: string | null) {
  const agent = skillName ? agents?.find((item) => item.skill_name === skillName) : agents?.find((item) => item.roles.includes(role));
  return agent?.profile?.display_name ?? ROLE_OPTIONS.find((item) => item.value === (skillName ? SKILL_ROLES[skillName] ?? role : role))?.label ?? "General";
}

function activityLabel(activity: AgentWorkActivity) {
  const kind = { model: "Thinking", tool: "Using tool", delegation: "Delegating", routing: "Routing" }[activity.kind];
  const detail = activity.tool_name?.replaceAll("_", " ") ?? activity.skill_name.replaceAll("-", " ");
  return { owner: activity.skill_name.replaceAll("-", " "), action: `${kind} · ${detail}`, status: activity.status.replaceAll("_", " ") };
}

export function AssistantPage() {
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<AssistantRole>("GENERAL_ASSISTANT");
  const [message, setMessage] = useState(searchParams.get("q") ?? "");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [threadId, setThreadId] = useState<string | null>(searchParams.get("thread"));
  const [feedbackSession, setFeedbackSession] = useState<FeedbackSessionState | null>(null);
  const [feedbackExplanation, setFeedbackExplanation] = useState("");
  const [feedbackConfidence, setFeedbackConfidence] = useState("MEDIUM");
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [reviewEdits, setReviewEdits] = useState<Record<string, string>>({});
  const [pendingWorkLog, setPendingWorkLog] = useState<AgentWorkActivity[]>([]);
  const loadedThreadRef = useRef<string | null>(null);
  const requestGenerationRef = useRef(0);

  const morningQuery = useQuery({ queryKey: ["self-core-morning"], queryFn: api.morningBriefing, staleTime: 60_000 });
  const workspaceQuery = useQuery({ queryKey: ["foreground-workspace"], queryFn: api.foregroundWorkspace });
  const proposalsQuery = useQuery({ queryKey: ["plan-proposals"], queryFn: api.planProposals });
  const intelligenceQuery = useQuery({ queryKey: ["intelligence-settings"], queryFn: api.intelligenceSettings, staleTime: 30_000, retry: false });
  const activeProposal = proposalsQuery.data?.[0];
  const reviewQuery = useQuery({ queryKey: ["review-items"], queryFn: typeof api.reviewItems === "function" ? api.reviewItems : async () => [] });

  const applyCapture = useMutation({
    mutationFn: ({ id, version }: { id: string; version: number }) => api.applyQuickCapture(id, version),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-items"] }); invalidateLifeOsQueries(); }
  });
  const resolveReview = useMutation({
    mutationFn: ({ id, action, version, category }: { id: string; action: "EDIT_AND_ACCEPT" | "REJECT"; version: number; category?: string }) =>
      api.resolveReviewItem(id, action, version, category ? { category } : {}),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["review-items"] }); invalidateLifeOsQueries(); }
  });

  const resumeWorkspace = useMutation({
    mutationFn: (workspaceId: string) => api.resumeWorkspace(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["foreground-workspace"] });
      queryClient.invalidateQueries({ queryKey: ["self-core-morning"] });
    }
  });
  const acceptPlanProposal = useMutation({
    mutationFn: (proposalId: string) => api.acceptPlanProposal(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-proposals"] });
      queryClient.invalidateQueries({ queryKey: ["self-core-morning"] });
      invalidateLifeOsQueries();
    }
  });
  const rejectPlanProposal = useMutation({
    mutationFn: (proposalId: string) => api.rejectPlanProposal(proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-proposals"] });
      queryClient.invalidateQueries({ queryKey: ["self-core-morning"] });
    }
  });

  const threadsQuery = useQuery({
    queryKey: ["assistant-threads"],
    queryFn: api.listAssistantThreads
  });

  const threadQuery = useQuery({
    queryKey: ["assistant-thread", threadId],
    queryFn: () => api.getAssistantThread(threadId ?? ""),
    enabled: Boolean(threadId)
  });

  const recentMessages = useMemo(
    () =>
      entries.filter((entry) => !entry.excludeFromContext).slice(-6).map((entry) => ({
        role: entry.kind,
        content: entry.text
      })),
    [entries]
  );

  const sendMessage = useMutation({
    mutationFn: async (text: string) => {
      const payload = { message: text, role, thread_id: threadId, recent_messages: recentMessages };
      const generation = requestGenerationRef.current;
      if (typeof api.assistantMessageStream === "function") return api.assistantMessageStream(payload, (activity) => { if (requestGenerationRef.current === generation) setPendingWorkLog((current) => [...current, activity]); });
      return api.assistantMessage(payload);
    },
    onSuccess: (response) => {
      setEntries((current) => [
        ...current,
        {
          id: response.request_id,
          kind: "assistant",
          text: response.message,
          response,
          excludeFromContext: response.response_type === "FEEDBACK", workLog: response.work_log ?? pendingWorkLog
        }
      ]);
      setPendingWorkLog([]);
      if (response.thread_id) {
        loadedThreadRef.current = response.thread_id;
        setThreadId(response.thread_id);
      }
      queryClient.invalidateQueries({ queryKey: ["assistant-threads"] });
      if (response.proposed_action) queryClient.invalidateQueries({ queryKey: ["assistant-pending-proposals"] });
      if (response.response_type === "MUTATION_RESULT") {
        invalidateLifeOsQueries();
        queryClient.invalidateQueries({ queryKey: ["assistant-pending-proposals"] });
      }
      if (response.orchestration_route === "quick_capture") {
        queryClient.invalidateQueries({ queryKey: ["review-items"] });
      }
      if (response.response_type === "FEEDBACK" && response.feedback_session_id) {
        api.getFeedbackSession(response.feedback_session_id).then(setFeedbackSession).catch(() => undefined);
      }
    },
    onError: (error) => {
      setPendingWorkLog([]);
      setEntries((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          kind: "assistant",
          text: error instanceof Error ? error.message : "Assistant is unavailable.",
          response: {
            message: error instanceof Error ? error.message : "Assistant is unavailable.",
            role_used: role,
            response_type: "ERROR",
            entity_references: [],
            request_id: crypto.randomUUID(),
            model_tier: "NO_AI",
            error_code: "network_error"
          }
        }
      ]);
    }
  });

  const createThread = useMutation({
    mutationFn: () => api.createAssistantThread(),
    onSuccess: (thread) => {
      loadedThreadRef.current = thread.id;
      setThreadId(thread.id);
      setEntries([]);
      queryClient.invalidateQueries({ queryKey: ["assistant-threads"] });
    }
  });

  const confirmProposal = useMutation({
    mutationFn: api.confirmAssistantProposal,
    onSuccess: (response, proposalId) => {
      setEntries((current) => [...current.map((entry) => entry.response?.proposed_action?.id === proposalId && response.response_type === "MUTATION_RESULT"
        ? { ...entry, response: { ...entry.response, proposed_action: { ...entry.response.proposed_action, status: "confirmed" } } }
        : entry), { id: response.request_id, kind: "assistant", text: response.message, response }]);
      if (response.response_type === "MUTATION_RESULT") {
        invalidateLifeOsQueries();
        queryClient.invalidateQueries({ queryKey: ["assistant-pending-proposals"] });
      }
    }
  });

  const cancelProposal = useMutation({
    mutationFn: api.cancelAssistantProposal,
    onSuccess: (response, proposalId) => {
      setEntries((current) => [...current.map((entry) => entry.response?.proposed_action?.id === proposalId && response.response_type === "NO_ACTION" && response.message.startsWith("Cancelled.")
        ? { ...entry, response: { ...entry.response, proposed_action: { ...entry.response.proposed_action, status: "cancelled" } } }
        : entry), { id: response.request_id, kind: "assistant", text: response.message, response }]);
      if (response.response_type === "NO_ACTION") queryClient.invalidateQueries({ queryKey: ["assistant-pending-proposals"] });
    }
  });

  const completeFeedback = useMutation({
    mutationFn: (sessionId: string) => api.completeFeedback(sessionId),
    onSuccess: () => {
      setFeedbackSession(null);
      setFeedbackExplanation("");
      setClarificationAnswer("");
    }
  });

  const answerFeedback = useMutation({
    mutationFn: ({ score, skipped }: { score: number | null; skipped: boolean }) => {
      const sessionId = feedbackSession?.session_id;
      const question = feedbackSession?.next_question;
      if (!sessionId || !question) {
        throw new Error("No active feedback question.");
      }
      return api.submitFeedbackResponse(sessionId, {
        question_id: question.question_id,
        question_version: question.question_version,
        score,
        is_skipped: skipped,
        feedback_scope: "EXACT_CASE",
        feedback_confidence: feedbackConfidence,
        explanation: feedbackExplanation.trim() || null
      });
    },
    onSuccess: (state) => {
      setFeedbackSession(state);
      setFeedbackExplanation("");
      if (!state.next_question && !state.clarification && state.session_id) {
        completeFeedback.mutate(state.session_id);
      }
    }
  });

  const clarifyFeedback = useMutation({
    mutationFn: () => {
      if (!feedbackSession?.session_id) {
        throw new Error("No active feedback session.");
      }
      return api.submitFeedbackClarification(feedbackSession.session_id, clarificationAnswer.trim());
    },
    onSuccess: (state) => {
      setFeedbackSession(state);
      setClarificationAnswer("");
    }
  });

  const cancelFeedback = useMutation({
    mutationFn: (sessionId: string) => api.cancelFeedback(sessionId),
    onSuccess: () => {
      setFeedbackSession(null);
      setFeedbackExplanation("");
      setClarificationAnswer("");
    }
  });

  useEffect(() => {
    const initial = searchParams.get("q");
    if (initial) {
      setMessage(initial);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!threadId && threadsQuery.data?.length) {
      setThreadId(threadsQuery.data[0].id);
    }
  }, [threadId, threadsQuery.data]);

  useEffect(() => {
    const thread = threadQuery.data;
    if (!thread || loadedThreadRef.current === thread.id) {
      return;
    }
    const restored = thread.messages.map<Entry>((item) => {
      const responseType = String(item.metadata_json.response_type ?? "INFORMATION") as AssistantResponse["response_type"];
      const rawWorkLog = item.metadata_json.work_log;
      const restoredProposal = item.metadata_json.proposed_action;
      const workLog = Array.isArray(rawWorkLog)
        ? rawWorkLog.slice(0, 64).map(parseAgentActivity).filter((value): value is AgentWorkActivity => value !== null)
        : [];
      return {
        id: item.id,
        kind: item.role === "user" ? "user" : "assistant",
        text: item.content,
        response:
          item.role === "assistant"
            ? {
                message: item.content,
                role_used: item.skill_name ? SKILL_ROLES[item.skill_name] ?? role : role,
                response_type: responseType,
                entity_references: [],
                request_id: item.request_id ?? item.id,
                model_tier: "NO_AI",
                skill_name: item.skill_name,
                thread_id: item.thread_id,
                provider: typeof item.metadata_json.provider === "string" ? item.metadata_json.provider : null,
                model: typeof item.metadata_json.model === "string" ? item.metadata_json.model : null,
                error_code: typeof item.metadata_json.error_code === "string" ? item.metadata_json.error_code : null,
                proposed_action: restoredProposal && typeof restoredProposal === "object" && !Array.isArray(restoredProposal)
                  && typeof (restoredProposal as Record<string, unknown>).id === "string"
                  ? restoredProposal as AssistantResponse["proposed_action"] : null,
                work_log: workLog
              }
            : undefined,
        workLog
      };
    });
    setEntries(restored);
    loadedThreadRef.current = thread.id;
  }, [role, threadQuery.data]);

  function invalidateLifeOsQueries() {
    queryClient.invalidateQueries({ queryKey: ["latest-state"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
    queryClient.invalidateQueries({ queryKey: ["calendar-projection"] });
    queryClient.invalidateQueries({ queryKey: ["fitness-status"] });
    queryClient.invalidateQueries({ queryKey: ["learning-status"] });
    queryClient.invalidateQueries({ queryKey: ["kitchen-status"] });
    queryClient.invalidateQueries({ queryKey: ["kitchen-recommendations"] });
    queryClient.invalidateQueries({ queryKey: ["shopping-needs"] });
    queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
    queryClient.invalidateQueries({ queryKey: ["meal-plans"] });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || sendMessage.isPending || createThread.isPending) {
      return;
    }
    const feedbackCommand = /^\s*log\s+feedback(?:\s*[.!?:]\s*.*?)?\s*$/is.test(trimmed);
    requestGenerationRef.current += 1;
    setEntries((current) => [
      ...current,
      { id: crypto.randomUUID(), kind: "user", text: trimmed, excludeFromContext: feedbackCommand }
    ]);
    setMessage("");
    setPendingWorkLog([]);
    sendMessage.mutate(trimmed);
  }

  return (
    <div className="stack assistant-shell">
      <section className="self-core-morning" aria-labelledby="self-core-morning-title">
        <div className="self-core-morning-copy">
          <span className="eyebrow">Today</span>
          <h2 id="self-core-morning-title">{morningQuery.data ? new Date(morningQuery.data.context.date + "T12:00:00").toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }) : "Preparing your day"}</h2>
          <p>{morningQuery.data?.message ?? (morningQuery.isError ? "Your morning view is temporarily unavailable. Conversation still works." : "Reading the current plan and relevant state...")}</p>
          <div className="self-core-day-meta">
            {morningQuery.data?.context.first_block ? <span><Clock3 size={14} />{morningQuery.data.context.first_block.title}</span> : null}
            {morningQuery.data ? <span><CalendarDays size={14} />Plan v{morningQuery.data.context.plan_version}</span> : null}
          </div>
        </div>
        <div className="self-core-day-rail">
          {(morningQuery.data?.context.important_blocks ?? []).slice(0, 4).map((block) => (
            <div className="self-core-day-block" key={block.ref_id}>
              <time>{block.starts_at ? new Date(block.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Today"}</time>
              <strong>{block.title}</strong>
              <small>{block.detail ?? block.status}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="self-core-context-grid">
        {workspaceQuery.data ? (
          <article className="content-band self-core-context-card">
            <span className="eyebrow">Current activity</span>
            <h3>{workspaceQuery.data.workspace_type.toLowerCase()}</h3>
            <p>{workspaceQuery.data.current_step ?? String(workspaceQuery.data.payload.session_phase ?? "Ready to continue")}</p>
            <button className="primary-button" type="button" onClick={() => workspaceQuery.data && resumeWorkspace.mutate(workspaceQuery.data.id)} disabled={resumeWorkspace.isPending}>
              <Play size={16} /><span>Continue</span>
            </button>
          </article>
        ) : null}
        {activeProposal ? (
          <article className="content-band self-core-context-card self-core-proposal-card">
            <span className="eyebrow">Plan proposal</span>
            <h3>{activeProposal.reason_code.replaceAll("_", " ")}</h3>
            <p>{activeProposal.changes.length} proposed change{activeProposal.changes.length === 1 ? "" : "s"}. Nothing changes until you apply it.</p>
            <div className="proposal-actions">
              <button className="primary-button" type="button" onClick={() => acceptPlanProposal.mutate(activeProposal.id)} disabled={acceptPlanProposal.isPending}>Apply</button>
              <button className="secondary-button" type="button" onClick={() => setMessage("Modify this proposal: ")}>Modify</button>
              <button className="secondary-button" type="button" onClick={() => rejectPlanProposal.mutate(activeProposal.id)} disabled={rejectPlanProposal.isPending}>Reject</button>
            </div>
          </article>
        ) : null}
        {(reviewQuery.data ?? []).slice(0, 3).map((item) => {
          const finance = item.review_type === "FINANCE_CLASSIFICATION";
          const category = reviewEdits[item.id] ?? "";
          return <article className="content-band self-core-context-card review-context-card" key={item.id}>
            <span className="eyebrow"><Inbox size={13} /> Needs review</span>
            <h3>{item.summary}</h3>
            <p>{item.question}</p>
            {finance ? <select aria-label={`Category for ${item.summary}`} value={category} onChange={(event) => setReviewEdits((current) => ({ ...current, [item.id]: event.target.value }))}>
              <option value="">Choose category</option><option>Groceries</option><option>Dining</option><option>Housing</option><option>Transport</option><option>Health</option><option>Entertainment</option><option>Shopping</option><option>Subscriptions</option><option>Other</option>
            </select> : null}
            <div className="proposal-actions">
              <button className="primary-button" type="button" disabled={resolveReview.isPending || (finance && !category)} onClick={() => resolveReview.mutate({ id: item.id, action: "EDIT_AND_ACCEPT", version: item.version, category })}>Accept</button>
              <button className="secondary-button" type="button" disabled={resolveReview.isPending} onClick={() => resolveReview.mutate({ id: item.id, action: "REJECT", version: item.version })}>Reject</button>
            </div>
          </article>;
        })}
        {(morningQuery.data?.context.attention_items ?? []).slice(0, 2).map((item) => (
          <article className="content-band self-core-context-card" key={item.ref_id}>
            <span className="eyebrow">Worth noting</span>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>
      {intelligenceQuery.data && !intelligenceQuery.data.live_agents_enabled ? <div className="assistant-runtime-banner" role="status">
        <Info size={16} aria-hidden="true" />
        <span>Deterministic test responses are active. Save a specialist's model settings to route new chat turns to a configured provider.</span>
        <Link to="/settings#agent-settings">Agent settings</Link>
      </div> : null}
      <section className="content-band assistant-header">
        <div className="assistant-title-row">
          <div className="section-header">
            <h2>Self Core</h2>
          <span>{threadQuery.data ? "Saved conversation" : "New conversation"}</span>
          </div>
          <div className="assistant-thread-controls">
            <select
              aria-label="Conversation"
              value={threadId ?? ""}
              disabled={sendMessage.isPending || createThread.isPending}
              onChange={(event) => {
                requestGenerationRef.current += 1;
                loadedThreadRef.current = null;
                setEntries([]);
                setThreadId(event.target.value || null);
              }}
            >
              {!threadsQuery.data?.length ? <option value="">Current conversation</option> : null}
              {threadsQuery.data?.map((thread) => (
                <option key={thread.id} value={thread.id}>
                  {thread.title}
                </option>
              ))}
            </select>
            <button
              className="secondary-button assistant-new-thread"
              type="button"
              aria-label="New conversation"
              onClick={() => createThread.mutate()}
              disabled={sendMessage.isPending || createThread.isPending}
            >
              <Plus size={16} aria-hidden="true" />{createThread.isPending ? "Creating" : "New conversation"}
            </button>
          </div>
        </div>
        <div className="assistant-role-row" role="group" aria-label="Assistant role">
          {ROLE_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={role === option.value ? "role-chip active" : "role-chip"}
              type="button"
              onClick={() => setRole(option.value)}
              disabled={sendMessage.isPending || createThread.isPending}
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      <section className="content-band assistant-thread" aria-live="polite">
        {entries.length === 0 ? (
          <div className="assistant-empty">
            <ShieldCheck size={22} aria-hidden="true" />
            <h2>{roleLabel(role, intelligenceQuery.data?.agents)} Assistant</h2>
            <p className="status-text">What would you like to work through today?</p>
            <div className="assistant-prompt-starters" aria-label="Try a message">
              {["Hi", "Which agents can I use?", "What is on today?"].map((prompt) => <button key={prompt} type="button" className="secondary-button compact-button" onClick={() => setMessage(prompt)}>{prompt}</button>)}
            </div>
          </div>
        ) : null}
        {entries.map((entry, index) => (
          <article key={`${entry.kind}-${entry.id}-${index}`} className={`assistant-entry ${entry.kind}`}>
            <div className="assistant-entry-meta">
              <span>{entry.kind === "user" ? "You" : roleLabel(entry.response?.role_used ?? role, intelligenceQuery.data?.agents, entry.response?.skill_name)}</span>
              {entry.response ? <span>{statusLabel(entry.response)}</span> : null}
              {entry.response?.provider ? <span className="assistant-provider-label">{entry.response.provider}{entry.response.model ? ` · ${entry.response.model}` : ""}</span> : null}
            </div>
            <p>{entry.text}</p>
            {entry.workLog?.length ? <details className="assistant-work-log"><summary>Work log ({entry.workLog.length})</summary><ul>{entry.workLog.map((activity) => { const label = activityLabel(activity); return <li key={`${activity.sequence}-${activity.status}`}><span>{label.owner}</span><span>{label.action}</span><span>{label.status}</span></li>; })}</ul></details> : null}
            {entry.response?.explanation ? (
              <div className="assistant-result info">
                <Info size={16} aria-hidden="true" />
                <div>
                  <strong>{entry.response.explanation.title ?? "Explanation"}</strong>
                  <span>{entry.response.explanation.summary}</span>
                </div>
              </div>
            ) : null}
            {entry.response?.mutation_result ? (
              <div className={`assistant-result ${entry.response.mutation_result.tool_name === "quick_capture.propose" ? "info" : "success"}`}>
                {entry.response.mutation_result.tool_name === "quick_capture.propose" ? <Info size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}
                <div>
                  <strong>{entry.response.mutation_result.tool_name.replaceAll("_", " ")}</strong>
                  <span>{entry.response.mutation_result.tool_name === "quick_capture.propose" ? "Nothing changed yet" : `World revision ${entry.response.mutation_result.world_revision ?? "--"}`}</span>
                </div>
              </div>
            ) : null}
            {entry.response?.mutation_result?.tool_name === "quick_capture.propose" ? (
              <div className="capture-preview">
                <dl>{Object.entries((entry.response.mutation_result.result.structured_preview as Record<string, unknown>) ?? {}).filter(([, value]) => value != null).slice(0, 8).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{formatArgumentValue(value)}</dd></div>)}</dl>
                {!entry.response.mutation_result.result.review_item_id ? <button className="primary-button" type="button" disabled={applyCapture.isPending} onClick={() => applyCapture.mutate({ id: entry.response?.mutation_result?.entity_id ?? "", version: Number(entry.response?.mutation_result?.result.capture_version ?? 1) })}><Check size={16} />Apply change</button> : <span className="status-text">Added to Review Queue.</span>}
              </div>
            ) : null}
            {entry.response?.error_code ? (
              <div className="assistant-result error">
                <AlertTriangle size={16} aria-hidden="true" />
                <div>
                  <strong>{entry.response.error_code.replaceAll("_", " ")}</strong>
                  <span>{entry.response.error_code === "network_error" ? "Reload the saved conversation before retrying; the request may have completed." : "No Life OS data was changed."}</span>
                </div>
              </div>
            ) : null}
            {entry.response?.proposed_action ? (
              <div className="proposal-panel">
                <div>
                  <span>Phengos proposes · {entry.response.proposed_action.tool_name.replaceAll("_", " ")}</span>
                  <strong>{entry.response.proposed_action.summary}</strong>
                  <small>Expected world revision {entry.response.proposed_action.expected_world_revision ?? "--"}</small>
                  <small>Status: {entry.response.proposed_action.status}</small>
                </div>
                <dl>
                  {Object.entries(entry.response.proposed_action.arguments)
                    .filter(([, value]) => value != null)
                    .slice(0, 8)
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{key.replaceAll("_", " ")}</dt>
                        <dd>{formatArgumentValue(value)}</dd>
                      </div>
                    ))}
                </dl>
                <div className="proposal-actions">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() => confirmProposal.mutate(entry.response?.proposed_action?.id ?? "")}
                    disabled={confirmProposal.isPending || entry.response.proposed_action.status !== "pending"}
                  >
                    <span>{confirmProposal.isPending ? "Confirming" : "Confirm"}</span>
                    <Check size={16} aria-hidden="true" />
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => cancelProposal.mutate(entry.response?.proposed_action?.id ?? "")}
                    disabled={cancelProposal.isPending || entry.response.proposed_action.status !== "pending"}
                  >
                    <span>{cancelProposal.isPending ? "Cancelling" : "Cancel"}</span>
                    <X size={16} aria-hidden="true" />
                  </button>
                </div>
              </div>
            ) : null}
          </article>
        ))}
        {sendMessage.isPending ? (
          <div className="assistant-entry assistant">
            <div className="assistant-entry-meta">
              <span>{roleLabel(role, intelligenceQuery.data?.agents)}</span>
              <span>sending</span>
            </div>
            {pendingWorkLog.length ? <details open className="assistant-work-log"><summary>Working ({pendingWorkLog.length})</summary><ul>{pendingWorkLog.map((activity) => { const label = activityLabel(activity); return <li key={`${activity.sequence}-${activity.status}`}><span>{label.owner}</span><span>{label.action}</span><span>{label.status}</span></li>; })}</ul></details> : <p className="assistant-loading"><RefreshCw size={15} aria-hidden="true" /> Reading bounded context...</p>}
          </div>
        ) : null}
      </section>

      <form className="assistant-composer" onSubmit={handleSubmit}>
        <input
          aria-label="Message assistant"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Add appointment, log study, ask about today..."
        />
        <button className="primary-button" type="submit" disabled={sendMessage.isPending || createThread.isPending || !message.trim()}>
          <span>{sendMessage.isPending ? "Sending" : "Send"}</span>
          <Send size={17} aria-hidden="true" />
        </button>
      </form>
      {confirmProposal.isError || cancelProposal.isError ? (
        <p className="status-text error">Could not update that proposal. Refresh and try again.</p>
      ) : null}
      {feedbackSession?.session_id && feedbackSession.status === "ACTIVE" ? (
        <div className="feedback-overlay" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
          <section className="feedback-dialog">
            <header>
              <div>
                <span className="eyebrow">Intelligence feedback</span>
                <h2 id="feedback-title">Help Life OS learn</h2>
              </div>
              <button
                className="icon-button"
                type="button"
                aria-label="Cancel feedback"
                title="Cancel feedback"
                onClick={() => cancelFeedback.mutate(feedbackSession.session_id ?? "")}
                disabled={cancelFeedback.isPending}
              >
                <X size={17} aria-hidden="true" />
              </button>
            </header>
            <div className="feedback-progress" aria-label={`Question ${Math.min(feedbackSession.questions_answered_count + 1, feedbackSession.questions_planned_count)} of ${feedbackSession.questions_planned_count}`}>
              <span>{feedbackSession.questions_answered_count} answered</span>
              <span>{feedbackSession.questions_planned_count} total</span>
            </div>
            {feedbackSession.clarification ? (
              <div className="feedback-question">
                <p>{feedbackSession.clarification.prompt}</p>
                <textarea
                  aria-label="Feedback clarification"
                  value={clarificationAnswer}
                  onChange={(event) => setClarificationAnswer(event.target.value)}
                  rows={3}
                />
                <button
                  className="primary-button"
                  type="button"
                  disabled={!clarificationAnswer.trim() || clarifyFeedback.isPending}
                  onClick={() => clarifyFeedback.mutate()}
                >
                  Continue
                </button>
              </div>
            ) : feedbackSession.next_question ? (
              <div className="feedback-question">
                <p>{feedbackSession.next_question.prompt}</p>
                <div className="feedback-scale" role="group" aria-label="Feedback score from 0 to 5">
                  {[0, 1, 2, 3, 4, 5].map((score) => (
                    <button
                      key={score}
                      type="button"
                      onClick={() => answerFeedback.mutate({ score, skipped: false })}
                      disabled={answerFeedback.isPending}
                      aria-label={`Score ${score}`}
                    >
                      {score}
                    </button>
                  ))}
                </div>
                <div className="feedback-scale-labels">
                  <span>{feedbackSession.next_question.low_label}</span>
                  <span>{feedbackSession.next_question.high_label}</span>
                </div>
                <label className="feedback-field">
                  <span>Why? (optional)</span>
                  <textarea value={feedbackExplanation} onChange={(event) => setFeedbackExplanation(event.target.value)} rows={3} />
                </label>
                <label className="feedback-field">
                  <span>How certain are you?</span>
                  <select value={feedbackConfidence} onChange={(event) => setFeedbackConfidence(event.target.value)}>
                    <option value="LOW">Not sure</option>
                    <option value="MEDIUM">Fairly sure</option>
                    <option value="HIGH">Certain</option>
                  </select>
                </label>
                <div className="feedback-actions">
                  <button className="secondary-button" type="button" onClick={() => answerFeedback.mutate({ score: null, skipped: true })} disabled={answerFeedback.isPending}>
                    Skip
                  </button>
                  {feedbackSession.questions_answered_count > 0 ? (
                    <button className="secondary-button" type="button" onClick={() => completeFeedback.mutate(feedbackSession.session_id ?? "")} disabled={completeFeedback.isPending}>
                      Finish
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
            {answerFeedback.isError || clarifyFeedback.isError || completeFeedback.isError || cancelFeedback.isError ? (
              <p className="status-text error">Could not save feedback. Your active session is still available.</p>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}
