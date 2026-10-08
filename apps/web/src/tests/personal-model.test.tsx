import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { PersonalModelPage } from "../features/personal-model/PersonalModelPage";
import { api } from "../services/api";
import type { MemoryItem, PatternEvidence, PersonalModelSummary, PersonalModelVersion } from "../types/api";

vi.mock("../services/api", () => ({
  api: {
    personalModelSummary: vi.fn(),
    personalModels: vi.fn(),
    personalPatterns: vi.fn(),
    refreshPersonalModels: vi.fn(),
    correctPersonalPattern: vi.fn(),
    memories: vi.fn(),
    memoryDetail: vi.fn(),
    createMemory: vi.fn(),
    updateMemory: vi.fn(),
    pinMemory: vi.fn(),
    confirmMemory: vi.fn(),
    forgetMemory: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderPersonalModel(initialEntry = "/settings/personal-model") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter></QueryClientProvider>;
  }

  return render(<PersonalModelPage />, { wrapper: Wrapper });
}

function summaryFixture(overrides: Partial<PersonalModelSummary> = {}): PersonalModelSummary {
  return {
    feature_schema_version: "personal-features-v1",
    extraction_version: "personal-extractor-v1",
    status: "BASELINE_INSUFFICIENT_EVIDENCE",
    evidence_n: 6,
    active_model_count: 1,
    candidate_model_count: 0,
    rejected_model_count: 1,
    pattern_count: 1,
    corrected_pattern_count: 0,
    fallback_rate: 0.83,
    latest_refresh: null,
    snapshot: {
      status: "BASELINE_INSUFFICIENT_EVIDENCE",
      feature_schema_version: "personal-features-v1",
      model_revision: 2,
      active_model_ids: { completion: "model-1" },
      model_versions: { completion: 1 },
      parameters: {},
      confidence: { completion: 0.72 },
      evidence_counts: { completion: 24 },
      fallback_reasons: { capacity: "BASELINE / INSUFFICIENT_EVIDENCE" }
    },
    metrics: {},
    ...overrides
  };
}

function activeModelFixture(): PersonalModelVersion {
  return {
    id: "model-1",
    model_type: "completion",
    model_stage: "STAGE_1",
    version: 1,
    feature_schema_version: "personal-features-v1",
    status: "ACTIVE",
    parameters: {},
    evidence_start: "2026-09-01T08:00:00Z",
    evidence_end: "2026-09-15T08:00:00Z",
    evidence_n: 24,
    effective_evidence_n: 22.5,
    confidence: 0.72,
    metrics: {},
    baseline_metrics: {},
    promotion_reason: "PROMOTED: sufficient evidence, confidence, and baseline comparison.",
    promoted_at: "2026-09-15T08:00:00Z",
    supersedes_model_version_id: null,
    refresh_run_id: "refresh-1"
  };
}

function rejectedModelFixture(): PersonalModelVersion {
  return {
    ...activeModelFixture(),
    id: "model-2",
    model_type: "capacity",
    status: "REJECTED",
    confidence: 0.42,
    evidence_n: 6,
    promotion_reason: "INSUFFICIENT_EVIDENCE: requires 20, found 6."
  };
}

function patternFixture(): PatternEvidence {
  return {
    id: "pattern-1",
    pattern_type: "routine",
    scope: { domain: "learning" },
    claim: "Learning often works well in the morning.",
    evidence_n: 14,
    weighted_support: 0.78,
    confidence: 0.69,
    first_observed: "2026-09-01T08:00:00Z",
    last_observed: "2026-09-15T08:00:00Z",
    last_updated: "2026-09-15T08:00:00Z",
    status: "ACTIVE",
    correction_metadata: {},
    source_model_version_id: "model-1",
    version: 1
  };
}

function memoryFixture(): MemoryItem {
  return {
    id: "memory-1",
    memory_type: "preference",
    domain: "learning",
    content: "I prefer quiet study sessions",
    normalized_key: "quiet study sessions",
    polarity: 1,
    confidence: 0.92,
    effective_confidence: 0.92,
    importance: 0.7,
    status: "active",
    pinned: false,
    user_confirmed: true,
    source_kind: "explicit_user",
    first_observed_at: "2026-09-15T08:00:00Z",
    last_observed_at: "2026-09-15T08:00:00Z",
    last_confirmed_at: "2026-09-15T08:00:00Z",
    valid_from: "2026-09-15T08:00:00Z",
    valid_until: null,
    supersedes_memory_id: null,
    embedding_provider: "fake",
    embedding_model: "life-os-fake-embedding",
    embedding_dimension: 768,
    embedding_version: "memory-embedding-v1",
    created_at: "2026-09-15T08:00:00Z",
    updated_at: "2026-09-15T08:00:00Z",
    version: 1,
    evidence_count: 1
  };
}

describe("PersonalModelPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.personalModelSummary.mockResolvedValue(summaryFixture());
    mockedApi.personalModels.mockResolvedValue([activeModelFixture(), rejectedModelFixture()]);
    mockedApi.personalPatterns.mockResolvedValue([patternFixture()]);
    mockedApi.refreshPersonalModels.mockResolvedValue({ id: "refresh-1", status: "SUCCEEDED", evidence_n: 24, metrics_json: {} });
    mockedApi.correctPersonalPattern.mockResolvedValue({ ...patternFixture(), status: "INVALIDATED", correction_metadata: { preserved_history: true } });
    mockedApi.memories.mockResolvedValue([memoryFixture()]);
    mockedApi.memoryDetail.mockResolvedValue({
      ...memoryFixture(),
      evidence: [
        {
          id: "evidence-1",
          source_type: "conversation_message",
          source_id: "message-1",
          evidence_kind: "user_statement",
          direction: "supports",
          weight: 1,
          observed_at: "2026-09-15T08:00:00Z",
          excerpt: "I prefer quiet study sessions",
          metadata_json: {}
        }
      ]
    });
    mockedApi.createMemory.mockResolvedValue(memoryFixture());
    mockedApi.updateMemory.mockResolvedValue({ ...memoryFixture(), content: "I prefer silent study sessions", version: 2 });
    mockedApi.pinMemory.mockResolvedValue({ ...memoryFixture(), pinned: true, version: 2 });
    mockedApi.confirmMemory.mockResolvedValue(memoryFixture());
    mockedApi.forgetMemory.mockResolvedValue({ ...memoryFixture(), status: "forgotten", version: 2 });
  });

  it("renders baseline status, active models, patterns, and rejected candidates", async () => {
    renderPersonalModel();

    expect(await screen.findByRole("heading", { name: "Personal Learning" })).toBeInTheDocument();
    expect(await screen.findByText("BASELINE_INSUFFICIENT_EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("Baseline heuristics are active until enough real evidence supports personalization.")).toBeInTheDocument();
    expect(screen.getByText("completion")).toBeInTheDocument();
    expect(screen.getByText("Learning often works well in the morning.")).toBeInTheDocument();
    expect(screen.getByText("I prefer quiet study sessions")).toBeInTheDocument();
    expect(screen.getByText("INSUFFICIENT_EVIDENCE: requires 20, found 6.")).toBeInTheDocument();
  });

  it("refreshes models manually and lets the user invalidate a pattern", async () => {
    renderPersonalModel();

    fireEvent.click(await screen.findByRole("button", { name: /refresh personal model/i }));
    await waitFor(() => expect(mockedApi.refreshPersonalModels).toHaveBeenCalled());
    expect(await screen.findByText("Refresh complete.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /correct routine/i }));
    await waitFor(() => expect(mockedApi.correctPersonalPattern).toHaveBeenCalledWith("pattern-1", { reason: "user_says_wrong" }));
  });

  it("lets the user add, pin, correct, and forget memories", async () => {
    renderPersonalModel();
    expect(await screen.findByText("I prefer quiet study sessions")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Add memory" }), { target: { value: "Keep planning suggestions concise" } });
    fireEvent.click(screen.getByRole("button", { name: "Add memory" }));
    await waitFor(() => expect(mockedApi.createMemory).toHaveBeenCalledWith({ content: "Keep planning suggestions concise", memory_type: "preference", domain: "general" }));

    fireEvent.click(screen.getByRole("button", { name: "Pin I prefer quiet study sessions" }));
    await waitFor(() => expect(mockedApi.pinMemory).toHaveBeenCalledWith("memory-1", true));

    fireEvent.click(screen.getByRole("button", { name: "Correct I prefer quiet study sessions" }));
    fireEvent.change(screen.getByLabelText("Correct memory I prefer quiet study sessions"), { target: { value: "I prefer silent study sessions" } });
    fireEvent.click(screen.getByRole("button", { name: "Save memory correction" }));
    await waitFor(() => expect(mockedApi.updateMemory).toHaveBeenCalledWith("memory-1", { content: "I prefer silent study sessions", expected_version: 1 }));

    fireEvent.click(screen.getByRole("button", { name: "Forget I prefer quiet study sessions" }));
    await waitFor(() => expect(mockedApi.forgetMemory).toHaveBeenCalledWith("memory-1"));
  });

  it("shows deterministic memory provenance and applies filters", async () => {
    renderPersonalModel();
    expect(await screen.findByText("I prefer quiet study sessions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Why I prefer quiet study sessions" }));
    expect(await screen.findByText(/Supported by conversation message/)).toBeInTheDocument();
    expect(mockedApi.memoryDetail).toHaveBeenCalledWith("memory-1");

    fireEvent.change(screen.getByLabelText("Domain"), { target: { value: "learning" } });
    await waitFor(() => expect(mockedApi.memories).toHaveBeenCalledWith({ domain: "learning", memoryType: undefined, status: undefined }));
  });

  it("opens with the requested agent memory domain selected", async () => {
    renderPersonalModel("/settings/personal-model?domain=kitchen");
    expect(await screen.findByRole("heading", { name: "What Life OS Knows" })).toBeInTheDocument();
    expect(screen.getByLabelText("Domain")).toHaveValue("kitchen");
    expect(mockedApi.memories).toHaveBeenCalledWith({ domain: "kitchen", memoryType: undefined, status: undefined });
  });
});
