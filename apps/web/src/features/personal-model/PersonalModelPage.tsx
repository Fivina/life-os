import { Brain, Check, CircleHelp, Pencil, Pin, PinOff, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";

function pct(value?: number | null) {
  if (value == null) {
    return "--";
  }
  return `${Math.round(value * 100)}%`;
}

export function PersonalModelPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const summary = useQuery({ queryKey: ["personal-model-summary"], queryFn: api.personalModelSummary });
  const models = useQuery({ queryKey: ["personal-models"], queryFn: api.personalModels });
  const patterns = useQuery({ queryKey: ["personal-patterns"], queryFn: api.personalPatterns });
  const [memoryDomain, setMemoryDomain] = useState(() => searchParams.get("domain") ?? "");
  const [memoryType, setMemoryType] = useState("");
  const [memoryStatus, setMemoryStatus] = useState("");
  useEffect(() => setMemoryDomain(searchParams.get("domain") ?? ""), [searchParams]);
  const memories = useQuery({
    queryKey: ["memories", memoryDomain, memoryType, memoryStatus],
    queryFn: () => api.memories({ domain: memoryDomain || undefined, memoryType: memoryType || undefined, status: memoryStatus || undefined })
  });
  const [newMemory, setNewMemory] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const memoryDetail = useQuery({
    queryKey: ["memory-detail", detailId],
    queryFn: () => api.memoryDetail(detailId ?? ""),
    enabled: Boolean(detailId)
  });

  function refreshAll() {
    queryClient.invalidateQueries({ queryKey: ["personal-model-summary"] });
    queryClient.invalidateQueries({ queryKey: ["personal-models"] });
    queryClient.invalidateQueries({ queryKey: ["personal-patterns"] });
    queryClient.invalidateQueries({ queryKey: ["current-plan"] });
    queryClient.invalidateQueries({ queryKey: ["memories"] });
  }

  const refresh = useMutation({ mutationFn: api.refreshPersonalModels, onSuccess: refreshAll });
  const correctPattern = useMutation({
    mutationFn: (patternId: string) => api.correctPersonalPattern(patternId, { reason: "user_says_wrong" }),
    onSuccess: refreshAll
  });
  const addMemory = useMutation({
    mutationFn: (content: string) => api.createMemory({ content, memory_type: "preference", domain: "general" }),
    onSuccess: () => {
      setNewMemory("");
      refreshAll();
    }
  });
  const pinMemory = useMutation({ mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) => api.pinMemory(id, pinned), onSuccess: refreshAll });
  const confirmMemory = useMutation({ mutationFn: (id: string) => api.confirmMemory(id), onSuccess: refreshAll });
  const forgetMemory = useMutation({ mutationFn: (id: string) => api.forgetMemory(id), onSuccess: refreshAll });
  const updateMemory = useMutation({
    mutationFn: ({ id, content, version }: { id: string; content: string; version: number }) => api.updateMemory(id, { content, expected_version: version }),
    onSuccess: () => {
      setEditingId(null);
      setEditingContent("");
      refreshAll();
    }
  });

  const active = (models.data ?? []).filter((model) => model.status === "ACTIVE");
  const rejected = (models.data ?? []).filter((model) => model.status === "REJECTED").slice(0, 6);
  const activePatterns = (patterns.data ?? []).filter((pattern) => pattern.status === "ACTIVE");

  return (
    <div className="stack">
      <section className="stat-grid">
        <StatTile label="Evidence" value={`${summary.data?.evidence_n ?? 0}`} tone="blue" />
        <StatTile label="Active" value={`${summary.data?.active_model_count ?? 0}`} tone="green" />
        <StatTile label="Fallback" value={pct(summary.data?.fallback_rate)} tone="amber" />
        <StatTile label="Corrected" value={`${summary.data?.corrected_pattern_count ?? 0}`} tone="rose" />
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Personal Learning</h2>
          <span>{summary.data?.status ?? "loading"}</span>
        </div>
        <p className="status-text">
          {summary.data?.status === "BASELINE_INSUFFICIENT_EVIDENCE"
            ? "Baseline heuristics are active until enough real evidence supports personalization."
            : "Active estimates are bounded planner inputs, not commands."}
        </p>
        <div className="proposal-actions">
          <button className="secondary-button" type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            <span>{refresh.isPending ? "Refreshing" : "Refresh personal model"}</span>
            <RefreshCw size={16} aria-hidden="true" />
          </button>
        </div>
        {refresh.isSuccess ? <p className="status-text success">Refresh complete.</p> : null}
        {refresh.isError ? <p className="status-text error">Refresh failed or is already running.</p> : null}
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>What Life OS Knows</h2>
          <span>{memories.data?.length ?? 0}</span>
        </div>
        <div className="memory-filters" aria-label="Memory filters">
          <label>
            Domain
            <select value={memoryDomain} onChange={(event) => setMemoryDomain(event.target.value)}>
              <option value="">All</option>
              <option value="general">General</option>
              <option value="learning">Learning</option>
              <option value="fitness">Fitness</option>
              <option value="kitchen">Kitchen</option>
              <option value="home">Home</option>
              <option value="life">Life</option>
              <option value="finance">Finance</option>
              <option value="planning">Planning</option>
            </select>
          </label>
          <label>
            Type
            <select value={memoryType} onChange={(event) => setMemoryType(event.target.value)}>
              <option value="">All</option>
              <option value="preference">Preference</option>
              <option value="personal_fact">Personal fact</option>
              <option value="routine_preference">Routine</option>
              <option value="constraint_preference">Constraint</option>
              <option value="interaction_preference">Interaction</option>
              <option value="domain_preference">Domain preference</option>
            </select>
          </label>
          <label>
            Status
            <select value={memoryStatus} onChange={(event) => setMemoryStatus(event.target.value)}>
              <option value="">Current</option>
              <option value="active">Active</option>
              <option value="candidate">Candidate</option>
              <option value="uncertain">Uncertain</option>
            </select>
          </label>
        </div>
        <form
          className="memory-form"
          onSubmit={(event) => {
            event.preventDefault();
            const value = newMemory.trim();
            if (value) addMemory.mutate(value);
          }}
        >
          <label>
            Add memory
            <input value={newMemory} onChange={(event) => setNewMemory(event.target.value)} maxLength={1200} />
          </label>
          <button className="icon-button" type="submit" aria-label="Add memory" disabled={!newMemory.trim() || addMemory.isPending}>
            <Plus size={17} />
          </button>
        </form>
        <div className="kitchen-list">
          {(memories.data ?? []).map((memory) => (
            <article className="candidate-row memory-row" key={memory.id}>
              <div className="memory-copy">
                {editingId === memory.id ? (
                  <form
                    className="memory-edit-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const content = editingContent.trim();
                      if (content) updateMemory.mutate({ id: memory.id, content, version: memory.version });
                    }}
                  >
                    <input aria-label={`Correct memory ${memory.content}`} value={editingContent} onChange={(event) => setEditingContent(event.target.value)} />
                    <button className="icon-button" type="submit" aria-label="Save memory correction">
                      <Check size={16} />
                    </button>
                  </form>
                ) : (
                  <strong>{memory.content}</strong>
                )}
                <small>
                  {memory.domain} · {memory.memory_type.replaceAll("_", " ")} · confidence {pct(memory.effective_confidence)}
                </small>
                <small>
                  Status {memory.status} · {memory.pinned ? "pinned" : memory.user_confirmed ? "confirmed" : "inferred"} · {memory.source_kind.replaceAll("_", " ")} · updated{" "}
                  {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(memory.updated_at))}
                </small>
                {detailId === memory.id ? (
                  <div className="memory-detail" aria-live="polite">
                    {memoryDetail.isLoading ? <small>Loading provenance...</small> : null}
                    {(memoryDetail.data?.evidence ?? []).map((evidence) => (
                      <small key={evidence.id}>
                        {evidence.direction === "contradicts" ? "Contradicted by" : "Supported by"} {evidence.source_type.replaceAll("_", " ")} ·{" "}
                        {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(evidence.observed_at))}
                        {evidence.excerpt ? ` · ${evidence.excerpt}` : ""}
                      </small>
                    ))}
                    {!memoryDetail.isLoading && (memoryDetail.data?.evidence.length ?? 0) === 0 ? <small>No provenance records.</small> : null}
                  </div>
                ) : null}
              </div>
              <div className="memory-actions">
                <button
                  className="icon-button"
                  type="button"
                  aria-label={`Why ${memory.content}`}
                  title="Why?"
                  onClick={() => setDetailId((current) => (current === memory.id ? null : memory.id))}
                >
                  <CircleHelp size={16} />
                </button>
                {!memory.user_confirmed ? (
                  <button className="icon-button" type="button" aria-label={`Confirm ${memory.content}`} onClick={() => confirmMemory.mutate(memory.id)}>
                    <Check size={16} />
                  </button>
                ) : null}
                <button
                  className="icon-button"
                  type="button"
                  aria-label={`${memory.pinned ? "Unpin" : "Pin"} ${memory.content}`}
                  onClick={() => pinMemory.mutate({ id: memory.id, pinned: !memory.pinned })}
                >
                  {memory.pinned ? <PinOff size={16} /> : <Pin size={16} />}
                </button>
                <button
                  className="icon-button"
                  type="button"
                  aria-label={`Correct ${memory.content}`}
                  onClick={() => {
                    setEditingId(memory.id);
                    setEditingContent(memory.content);
                  }}
                >
                  <Pencil size={16} />
                </button>
                <button className="icon-button" type="button" aria-label={`Forget ${memory.content}`} onClick={() => forgetMemory.mutate(memory.id)}>
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          ))}
          {!memories.isLoading && (memories.data?.length ?? 0) === 0 ? <p className="status-text">No saved memories.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Active Models</h2>
          <Brain size={17} aria-hidden="true" />
        </div>
        <div className="kitchen-list">
          {active.map((model) => (
            <article className="candidate-row" key={model.id}>
              <div>
                <strong>{model.model_type.replaceAll("_", " ")}</strong>
                <small>
                  v{model.version} · confidence {pct(model.confidence)} · evidence {model.evidence_n}
                </small>
                <small>{model.promotion_reason}</small>
              </div>
              <Check size={18} aria-hidden="true" />
            </article>
          ))}
          {!summary.isLoading && active.length === 0 ? <p className="status-text">No active personal models. Stage-0 baseline is being used.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>What Life OS Has Observed</h2>
          <span>{activePatterns.length}</span>
        </div>
        <div className="kitchen-list">
          {activePatterns.map((pattern) => (
            <article className="candidate-row" key={pattern.id}>
              <div>
                <strong>{pattern.pattern_type.replaceAll("_", " ")}</strong>
                <small>{pattern.claim}</small>
                <small>
                  Confidence {pct(pattern.confidence)} · evidence {pattern.evidence_n}
                </small>
              </div>
              <button className="icon-button" type="button" aria-label={`Correct ${pattern.pattern_type}`} onClick={() => correctPattern.mutate(pattern.id)}>
                <X size={16} />
              </button>
            </article>
          ))}
          {!patterns.isLoading && activePatterns.length === 0 ? <p className="status-text">No patterns are above the display threshold.</p> : null}
        </div>
      </section>

      <section className="content-band">
        <div className="section-header">
          <h2>Recent Rejections</h2>
          <span>guardrails</span>
        </div>
        <div className="kitchen-list">
          {rejected.map((model) => (
            <article className="candidate-row" key={model.id}>
              <div>
                <strong>{model.model_type.replaceAll("_", " ")}</strong>
                <small>
                  Evidence {model.evidence_n} · confidence {pct(model.confidence)}
                </small>
                <small>{model.promotion_reason}</small>
              </div>
            </article>
          ))}
          {!models.isLoading && rejected.length === 0 ? <p className="status-text">No rejected candidate models yet.</p> : null}
        </div>
      </section>
    </div>
  );
}
