import { AlertTriangle, CalendarDays, Check, Clock3, Inbox, Info, MessageSquare, Play, Plus, RefreshCw, Search, Send, ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../../services/api";
import { parseAgentActivity } from "../../services/assistantStream";
import type { AgentSettings, AgentWorkActivity, AssistantResponse, AssistantRole, ConversationThreadDetail, FeedbackSessionState } from "../../types/api";
import "./AssistantPage.css";

type Entry = {
  id: string;
  kind: "user" | "assistant";
  text: string;
  response?: AssistantResponse;
  excludeFromContext?: boolean;
  workLog?: AgentWorkActivity[];
};

const ASSISTANT_ROLES = new Set<AssistantRole>([
  "GENERAL_ASSISTANT", "FITNESS_COACH", "LEARNING_COACH", "HOME_MANAGER", "CHEF", "FINANCE_ADVISOR"
]);

type RoleOption = { label: string; value: AssistantRole; skillName: string | null; configured: boolean };

const FALLBACK_ROLE: RoleOption = { label: "General", value: "GENERAL_ASSISTANT", skillName: "self-core", configured: false };

function roleOptions(agents: AgentSettings[] | undefined): RoleOption[] {
  if (!agents) return [FALLBACK_ROLE];
  const seen = new Set<AssistantRole>();
  const options: RoleOption[] = [];
  for (const agent of agents) {
    for (const rawRole of agent.roles) {
      const value = rawRole as AssistantRole;
      if (!ASSISTANT_ROLES.has(value) || seen.has(value)) continue;
      seen.add(value);
      options.push({
        label: agent.profile?.display_name || agent.name || value.replaceAll("_", " ").toLowerCase(),
        value,
        skillName: agent.skill_name,
        configured: agent.credential_configured
      });
    }
  }
  return options;
}

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
const ROLE_LABELS: Record<AssistantRole, string> = {
  GENERAL_ASSISTANT: "General", FITNESS_COACH: "Fitness", LEARNING_COACH: "Learning",
  HOME_MANAGER: "Home", CHEF: "Chef", FINANCE_ADVISOR: "Finance"
};

function roleLabel(role: AssistantRole, agents?: Array<{ skill_name?: string; roles: string[]; profile?: { display_name: string } }>, skillName?: string | null) {
  const agent = skillName ? agents?.find((item) => item.skill_name === skillName) : agents?.find((item) => item.roles.includes(role));
  return agent?.profile?.display_name ?? ROLE_LABELS[skillName ? SKILL_ROLES[skillName] ?? role : role] ?? "General";
}

function latestSupportedRole(thread: ConversationThreadDetail, options: RoleOption[]): AssistantRole {
  const supported = new Map(options.map((option) => [option.skillName, option.value]));
  for (let index = thread.messages.length - 1; index >= 0; index -= 1) {
    const saved = supported.get(thread.messages[index].skill_name ?? null);
    if (saved) return saved;
  }
  return supported.get(thread.default_skill) ?? options[0]?.value ?? "GENERAL_ASSISTANT";
}

function draftKey(threadId: string | null, workspaceKey?: "calendar" | "kitchen") {
  return workspaceKey
    ? `life-os:chat-draft:embedded:${workspaceKey}:${threadId ?? "new"}`
    : `life-os:chat-draft:${threadId ?? "new"}`;
}

function embeddedThreadKey(workspaceKey: "calendar" | "kitchen") {
  return `life-os:chat-thread:${workspaceKey}`;
}

function threadDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Recently" : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function activityLabel(activity: AgentWorkActivity) {
  const kind = { model: "Thinking", tool: "Using tool", delegation: "Delegating", routing: "Routing" }[activity.kind];
  const detail = activity.tool_name?.replaceAll("_", " ") ?? activity.skill_name.replaceAll("-", " ");
  return { owner: activity.skill_name.replaceAll("-", " "), action: `${kind} · ${detail}`, status: activity.status.replaceAll("_", " ") };
}

type AssistantPageProps = {
  mode?: "full";
  workspaceKey?: never;
  initialRole?: AssistantRole;
  onOpenFullChat?: (threadId: string | null) => void;
} | {
  mode: "embedded";
  workspaceKey: "calendar" | "kitchen";
  initialRole?: AssistantRole;
  onOpenFullChat?: (threadId: string | null) => void;
};

export function AssistantPage({ mode = "full", workspaceKey, initialRole, onOpenFullChat }: AssistantPageProps = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const embedded = mode === "embedded";
  const embeddedWorkspace = workspaceKey ?? "calendar";
  const [role, setRole] = useState<AssistantRole>(() => initialRole ?? (embeddedWorkspace === "kitchen" ? "CHEF" : "GENERAL_ASSISTANT"));
  const initialThreadId = embedded ? sessionStorage.getItem(embeddedThreadKey(embeddedWorkspace)) : searchParams.get("thread");
  const [message, setMessage] = useState(() => embedded
    ? sessionStorage.getItem(draftKey(initialThreadId, embeddedWorkspace)) ?? ""
    : searchParams.get("q") ?? sessionStorage.getItem(draftKey(initialThreadId)) ?? "");
  const [entries, setEntries] = useState<Entry[]>([]);
  const [threadId, setThreadId] = useState<string | null>(initialThreadId);
  const [threadSearch, setThreadSearch] = useState("");
  const [feedbackSession, setFeedbackSession] = useState<FeedbackSessionState | null>(null);
  const [feedbackExplanation, setFeedbackExplanation] = useState("");
  const [feedbackConfidence, setFeedbackConfidence] = useState("MEDIUM");
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [reviewEdits, setReviewEdits] = useState<Record<string, string>>({});
  const [pendingWorkLog, setPendingWorkLog] = useState<AgentWorkActivity[]>([]);
  const liveDraftRef = useRef(message);
  const loadedThreadRef = useRef<string | null>(null);
  const requestGenerationRef = useRef(0);
  const activeThreadRef = useRef<string | null>(initialThreadId);
  const requestedThreadRef = useRef(Boolean(initialThreadId) || embedded);
  const routeSignatureRef = useRef(embedded ? "" : searchParams.toString());

  const morningQuery = useQuery({ queryKey: ["self-core-morning"], queryFn: api.morningBriefing, staleTime: 60_000, enabled: !embedded });
  const workspaceQuery = useQuery({ queryKey: ["foreground-workspace"], queryFn: api.foregroundWorkspace, enabled: !embedded });
  const proposalsQuery = useQuery({ queryKey: ["plan-proposals"], queryFn: api.planProposals, enabled: !embedded });
  const intelligenceQuery = useQuery({ queryKey: ["intelligence-settings"], queryFn: api.intelligenceSettings, staleTime: 30_000, retry: false });
  const availableRoles = useMemo(() => roleOptions(intelligenceQuery.data?.agents), [intelligenceQuery.data?.agents]);
  const selectedRole = availableRoles.find((option) => option.value === role) ?? availableRoles[0] ?? FALLBACK_ROLE;
  const roleReady = intelligenceQuery.isLoading
    ? role === "GENERAL_ASSISTANT"
    : intelligenceQuery.isError
      ? role === "GENERAL_ASSISTANT"
      : availableRoles.some((option) => option.value === role);
  const activeProposal = proposalsQuery.data?.[0];
  const reviewQuery = useQuery({ queryKey: ["review-items"], queryFn: typeof api.reviewItems === "function" ? api.reviewItems : async () => [], enabled: !embedded });

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
    queryFn: api.listAssistantThreads,
    enabled: !embedded
  });

  const threadQuery = useQuery({
    queryKey: ["assistant-thread", threadId],
    queryFn: () => api.getAssistantThread(threadId ?? ""),
    enabled: Boolean(threadId)
  });

  const filteredThreads = useMemo(() => {
    const needle = threadSearch.trim().toLocaleLowerCase();
    return (threadsQuery.data ?? []).filter((thread) => !needle || thread.title.toLocaleLowerCase().includes(needle));
  }, [threadSearch, threadsQuery.data]);

  const recentMessages = useMemo(
    () =>
      entries.filter((entry) => !entry.excludeFromContext).slice(-6).map((entry) => ({
        role: entry.kind,
        content: entry.text
      })),
    [entries]
  );

  const sendMessage = useMutation({
    mutationFn: async ({ text, requestRole, targetThread, generation, context }: { text: string; requestRole: AssistantRole; targetThread: string | null; generation: number; context: typeof recentMessages }) => {
      const payload = { message: text, role: requestRole, thread_id: targetThread, recent_messages: context };
      const response = typeof api.assistantMessageStream === "function"
        ? await api.assistantMessageStream(payload, (activity) => { if (requestGenerationRef.current === generation) setPendingWorkLog((current) => [...current, activity]); })
        : await api.assistantMessage(payload);
      return { response, requestRole, targetThread, generation };
    },
    onSuccess: ({ response, targetThread, generation }) => {
      if (requestGenerationRef.current !== generation || activeThreadRef.current !== targetThread) return;
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
        activeThreadRef.current = response.thread_id;
        setThreadId(response.thread_id);
        if (embedded) {
          sessionStorage.setItem(embeddedThreadKey(embeddedWorkspace), response.thread_id);
        } else {
          const next = new URLSearchParams(searchParams);
          next.set("thread", response.thread_id);
          setSearchParams(next, { replace: true });
        }
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
    onError: (error, variables) => {
      if (requestGenerationRef.current !== variables.generation || activeThreadRef.current !== variables.targetThread) return;
      setPendingWorkLog([]);
      setEntries((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          kind: "assistant",
          text: error instanceof Error ? error.message : "Assistant is unavailable.",
          response: {
            message: error instanceof Error ? error.message : "Assistant is unavailable.",
            role_used: variables.requestRole,
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
    mutationFn: () => api.createAssistantThread({ default_skill: selectedRole.skillName ?? "self-core" }),
    onSuccess: (thread) => {
      const currentDraft = liveDraftRef.current;
      loadedThreadRef.current = thread.id;
      activeThreadRef.current = thread.id;
      requestedThreadRef.current = true;
      setThreadId(thread.id);
      setEntries([]);
      const nextDraft = currentDraft || sessionStorage.getItem(draftKey(thread.id, embedded ? embeddedWorkspace : undefined)) || "";
      setMessage(nextDraft);
      liveDraftRef.current = nextDraft;
      sessionStorage.setItem(draftKey(thread.id, embedded ? embeddedWorkspace : undefined), nextDraft);
      if (embedded) {
        sessionStorage.setItem(embeddedThreadKey(embeddedWorkspace), thread.id);
      } else {
        const next = new URLSearchParams(searchParams);
        next.set("thread", thread.id);
        next.delete("q");
        setSearchParams(next);
      }
      queryClient.invalidateQueries({ queryKey: ["assistant-threads"] });
    }
  });

  const confirmProposal = useMutation({
    mutationFn: ({ proposalId }: { proposalId: string; targetThread: string | null; generation: number }) => api.confirmAssistantProposal(proposalId),
    onSuccess: (response, { proposalId, targetThread, generation }) => {
      if (requestGenerationRef.current !== generation || activeThreadRef.current !== targetThread) return;
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
    mutationFn: ({ proposalId }: { proposalId: string; targetThread: string | null; generation: number }) => api.cancelAssistantProposal(proposalId),
    onSuccess: (response, { proposalId, targetThread, generation }) => {
      if (requestGenerationRef.current !== generation || activeThreadRef.current !== targetThread) return;
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
    liveDraftRef.current = message;
    sessionStorage.setItem(draftKey(threadId, embedded ? embeddedWorkspace : undefined), message);
  }, [embedded, embeddedWorkspace, message, threadId]);

  useEffect(() => {
    if (embedded) return;
    const signature = searchParams.toString();
    if (signature === routeSignatureRef.current) return;
    routeSignatureRef.current = signature;
    const routeThread = searchParams.get("thread");
    if (routeThread === activeThreadRef.current) {
      const routeQuery = searchParams.get("q");
      if (routeQuery !== null) setMessage(routeQuery);
      return;
    }
    sessionStorage.setItem(draftKey(activeThreadRef.current), message);
    requestGenerationRef.current += 1;
    activeThreadRef.current = routeThread;
    requestedThreadRef.current = Boolean(routeThread);
    loadedThreadRef.current = null;
    setThreadId(routeThread);
    setEntries([]);
    setMessage(searchParams.get("q") ?? sessionStorage.getItem(draftKey(routeThread)) ?? "");
  }, [embedded, searchParams]);

  useEffect(() => {
    if (embedded || requestedThreadRef.current || threadId || !threadsQuery.data?.length) return;
    const latest = threadsQuery.data[0].id;
    activeThreadRef.current = latest;
    loadedThreadRef.current = null;
    setThreadId(latest);
    setMessage(sessionStorage.getItem(draftKey(latest)) ?? message);
    const next = new URLSearchParams(searchParams);
    next.set("thread", latest);
    setSearchParams(next, { replace: true });
  }, [embedded, message, searchParams, setSearchParams, threadId, threadsQuery.data]);

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
  }, [threadQuery.data]);

  useEffect(() => {
    if (!threadQuery.data || !intelligenceQuery.data?.agents) return;
    setRole(latestSupportedRole(threadQuery.data, availableRoles));
  }, [availableRoles, intelligenceQuery.data?.agents, threadQuery.data]);

  useEffect(() => {
    if (intelligenceQuery.isError) {
      setRole("GENERAL_ASSISTANT");
      return;
    }
    if (!intelligenceQuery.data?.agents || availableRoles.some((option) => option.value === role)) return;
    if (availableRoles[0]) setRole(availableRoles[0].value);
  }, [availableRoles, intelligenceQuery.data?.agents, intelligenceQuery.isError, role]);

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
    if (!trimmed || !roleReady || sendMessage.isPending || createThread.isPending) {
      return;
    }
    const feedbackCommand = /^\s*log\s+feedback(?:\s*[.!?:]\s*.*?)?\s*$/is.test(trimmed);
    const generation = requestGenerationRef.current + 1;
    requestGenerationRef.current = generation;
    const targetThread = threadId;
    const requestRole = role;
    const context = recentMessages;
    setEntries((current) => [
      ...current,
      { id: crypto.randomUUID(), kind: "user", text: trimmed, excludeFromContext: feedbackCommand }
    ]);
    setMessage("");
    sessionStorage.removeItem(draftKey(threadId, embedded ? embeddedWorkspace : undefined));
    if (!embedded && searchParams.has("q")) {
      const next = new URLSearchParams(searchParams);
      next.delete("q");
      routeSignatureRef.current = next.toString();
      setSearchParams(next, { replace: true });
    }
    setPendingWorkLog([]);
    sendMessage.mutate({ text: trimmed, requestRole, targetThread, generation, context });
  }

  function selectThread(nextThreadId: string) {
    if (sendMessage.isPending || createThread.isPending || confirmProposal.isPending || cancelProposal.isPending || nextThreadId === threadId) return;
    sessionStorage.setItem(draftKey(threadId), message);
    requestGenerationRef.current += 1;
    activeThreadRef.current = nextThreadId;
    requestedThreadRef.current = true;
    loadedThreadRef.current = null;
    setThreadId(nextThreadId);
    setEntries([]);
    setMessage(sessionStorage.getItem(draftKey(nextThreadId)) ?? "");
    const next = new URLSearchParams(searchParams);
    next.set("thread", nextThreadId);
    next.delete("q");
    setSearchParams(next);
  }

  return (
    <div className={embedded ? "assistant-shell embedded" : "assistant-shell"}>
      {!embedded ? (
      <details className="assistant-secondary-controls">
        <summary>Today and Life OS controls</summary>
        <div className="assistant-secondary-controls__body">
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
        </div>
      </details>
      ) : null}
      {intelligenceQuery.data && !intelligenceQuery.data.live_agents_enabled ? <div className="assistant-runtime-banner" role="status">
        <Info size={16} aria-hidden="true" />
        <span>Deterministic test responses are active. Save a specialist's model settings to route new chat turns to a configured provider.</span>
        <Link to="/settings#agent-settings">Agent settings</Link>
      </div> : null}
      <section className={embedded ? "assistant-hub embedded" : "assistant-hub"} aria-label={embedded ? `${embeddedWorkspace} assistant` : "Chat workspace"}>
        {!embedded ? (
        <aside className="assistant-conversations" aria-label="Conversations">
          <div className="assistant-conversations__heading">
            <div><span className="eyebrow">Chat</span><h2>Conversations</h2></div>
            <button
              className="assistant-icon-action"
              type="button"
              aria-label="New conversation"
              title="New conversation"
              onClick={() => createThread.mutate()}
              disabled={sendMessage.isPending || createThread.isPending || confirmProposal.isPending || cancelProposal.isPending}
            >
              <Plus size={17} aria-hidden="true" />
            </button>
          </div>
          <label className="assistant-thread-search">
            <Search size={15} aria-hidden="true" />
            <input aria-label="Search conversations" value={threadSearch} onChange={(event) => setThreadSearch(event.target.value)} placeholder="Search conversations" />
          </label>
          <div className="assistant-thread-list">
            {threadsQuery.isLoading ? <p className="assistant-sidebar-state">Loading conversations…</p> : null}
            {threadsQuery.isError ? <p className="assistant-sidebar-state error">Conversations are unavailable.</p> : null}
            {!threadsQuery.isLoading && !threadsQuery.isError && filteredThreads.length === 0 ? (
              <div className="assistant-sidebar-state"><MessageSquare size={18} /><p>{threadSearch ? "No matching conversations." : "No saved conversations yet."}</p></div>
            ) : null}
            {filteredThreads.map((thread) => (
              <button
                key={thread.id}
                type="button"
                className={thread.id === threadId ? "assistant-thread-item active" : "assistant-thread-item"}
                aria-current={thread.id === threadId ? "page" : undefined}
                onClick={() => selectThread(thread.id)}
                disabled={sendMessage.isPending || createThread.isPending || confirmProposal.isPending || cancelProposal.isPending}
              >
                <span>{thread.title}</span>
                <time dateTime={thread.last_message_at}>{threadDate(thread.last_message_at)}</time>
                <small>{roleLabel(SKILL_ROLES[thread.default_skill] ?? "GENERAL_ASSISTANT", intelligenceQuery.data?.agents, thread.default_skill)}</small>
              </button>
            ))}
          </div>
        </aside>
        ) : null}
        <div className="assistant-hub__main">
      <header className="assistant-header">
        <div className="assistant-title-row">
          <div className="section-header">
            <span className="eyebrow">PHÉNGOS</span>
            <h1>{threadQuery.data?.title ?? (threadId ? "Loading conversation" : "New conversation")}</h1>
            <span>{threadQuery.data ? "Saved conversation" : "Pick up a conversation or start something new."}</span>
          </div>
          <div className="assistant-role-picker">
            <label htmlFor="assistant-role">Agent</label>
            <select
              id="assistant-role"
              aria-label="Assistant role"
              value={role}
              disabled={sendMessage.isPending || createThread.isPending || confirmProposal.isPending || cancelProposal.isPending || !roleReady}
              onChange={(event) => {
                setRole(event.target.value as AssistantRole);
              }}
            >
              {availableRoles.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}{intelligenceQuery.data && !option.configured ? " · not configured" : ""}
                </option>
              ))}
            </select>
            {intelligenceQuery.isLoading ? <small>Loading registered agents…</small> : null}
            {intelligenceQuery.isError ? <small>Agent registry unavailable. General is the safe fallback.</small> : null}
            {embedded ? <div className="assistant-embedded-actions">
              <button className="secondary-button" type="button" onClick={() => createThread.mutate()} disabled={sendMessage.isPending || createThread.isPending || confirmProposal.isPending || cancelProposal.isPending || !roleReady}>
                <Plus size={15} aria-hidden="true" /> New chat
              </button>
              <button className="secondary-button" type="button" onClick={() => onOpenFullChat?.(threadId)}>
                Open in Chat
              </button>
            </div> : null}
          </div>
        </div>
      </header>

      {threadQuery.isError ? <div className="assistant-thread-error" role="alert"><AlertTriangle size={18} /><div><strong>Conversation unavailable</strong><span>This link may be invalid or you may no longer have access. Choose another conversation or start a new one.</span></div></div> : null}

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
                    onClick={() => confirmProposal.mutate({ proposalId: entry.response?.proposed_action?.id ?? "", targetThread: threadId, generation: requestGenerationRef.current })}
                    disabled={confirmProposal.isPending || entry.response.proposed_action.status !== "pending"}
                  >
                    <span>{confirmProposal.isPending ? "Confirming" : "Confirm"}</span>
                    <Check size={16} aria-hidden="true" />
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => cancelProposal.mutate({ proposalId: entry.response?.proposed_action?.id ?? "", targetThread: threadId, generation: requestGenerationRef.current })}
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
        <textarea
          aria-label="Message assistant"
          value={message}
          onChange={(event) => { liveDraftRef.current = event.target.value; setMessage(event.target.value); }}
          placeholder={`Message ${selectedRole.label}…`}
          rows={3}
        />
        <button className="primary-button" type="submit" disabled={sendMessage.isPending || createThread.isPending || !roleReady || !message.trim()}>
          <span>{sendMessage.isPending ? "Sending" : "Send"}</span>
          <Send size={17} aria-hidden="true" />
        </button>
      </form>
        </div>
      </section>
      {createThread.isError ? <p className="status-text error" role="alert">Could not create a conversation. Your draft is still here.</p> : null}
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
