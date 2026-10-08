import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { SettingsPage } from "../features/settings/SettingsPage";
import { api } from "../services/api";
import type { IntelligenceControlSurface } from "../types/api";

const control = {
  settings: {
    schema_version: "intelligence-settings-v1", proactivity_mode: "BALANCED", memory_visible: true,
    patterns_visible: true, passive_suggestions_enabled: true, questions_enabled: true,
    interruptions_enabled: true, prospective_resurfacing_enabled: true,
    opportunity_suggestions_enabled: true, monthly_ai_budget_eur: 12, disabled_skills: [], version: 1,
  },
  memory: { visible: true, counts: { active: 2 }, controls: [] },
  patterns: { visible: true, counts: { active: 1 }, controls: [] },
  conversations: { counts: { active: 1, archived: 0 }, controls: [], delete_semantics: "Archived conversations remain available." },
  skills: [],
  providers: [
    { id: "openai", kind: "agent", enabled: true, configured: false, credential_configured: false, state: "not_configured", capabilities: ["ECONOMY", "FAST", "REASONING"], models: ["gpt-5-nano", "gpt-5-mini", "gpt-5.1"] },
    { id: "gemini", kind: "agent", enabled: true, configured: false, credential_configured: false, state: "not_configured", capabilities: ["ECONOMY", "FAST", "REASONING"], models: ["gemini-3.5-flash-lite", "gemini-3.8-flash"] },
    { id: "jev", kind: "decision", enabled: false, configured: false, credential_configured: false, credential_source: "supabase_vault", state: "disabled", capabilities: ["typed_decision"], models: ["jev-latest"] },
    { id: "laya_local", kind: "decision", enabled: false, configured: false, state: "disabled", capabilities: ["categorical_decision"], models: ["auto"] },
  ],
  agents: [{
    skill_name: "chef", name: "Chef", description: "Kitchen inventory and meal assistance.", roles: ["CHEF"],
    provider: "openai", economy_model: "gpt-5-nano", fast_model: "gpt-5-mini", reasoning_model: "gpt-5.1",
    memory_scopes: ["semantic-memory", "episodic-memory"], memory_domain: "kitchen", memory_count: 4,
    credential_configured: false,
  }],
  active_agent_runtime: "legacy", live_agents_enabled: false, credential_management_available: false,
  usage: { monthly_spend_eur: 0, budget_eur: 12, warning: false, economy_only: false, optional_suppressed: false, by_provider: {}, by_model: {}, by_capability: {}, by_skill: {} },
  privacy: { export_endpoint: "/api/v1/export", memory_forget_endpoint: "/api/v1/memories/{id}/forget", memory_correct_endpoint: "/api/v1/memories/{id}", conversation_archive_endpoint: "/api/v1/assistant/threads/{id}/archive", account_delete_supported: false },
} as IntelligenceControlSurface;

function renderSettings(settingsControl: IntelligenceControlSurface = control, intelligenceSettings = vi.fn().mockResolvedValue(settingsControl)) {
  vi.spyOn(api, "intelligenceSettings").mockImplementation(intelligenceSettings);
  vi.spyOn(api, "embeddingSettings").mockResolvedValue({ provider: "default", model: "life-os-fake-embedding", effective_provider: "fake", dimensions: 768, credential_configured: true, version: 1 });
  vi.spyOn(api, "updateEmbeddingSettings").mockResolvedValue({ provider: "default", model: "life-os-fake-embedding", effective_provider: "fake", dimensions: 768, credential_configured: true, version: 2 });
  vi.spyOn(api, "testEmbeddingProvider").mockResolvedValue({ provider: "openai", model: "text-embedding-3-small", dimensions: 768, connected: true });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/settings"]}><SettingsPage /></MemoryRouter></QueryClientProvider>);
}

describe("Settings provider and agent controls", () => {
  it("lets provider key rows open and accept temporary typing while secure saving is unavailable", async () => {
    renderSettings();
    expect(await screen.findByRole("heading", { name: "Providers" })).toBeInTheDocument();
    const openAiKey = await screen.findByLabelText("OpenAI API key");
    expect(openAiKey).toBeEnabled();
    expect(screen.getByLabelText("Google Gemini API key")).toBeEnabled();
    expect(screen.getByLabelText("Jev (TypeSafe) API key")).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "Add key" })).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Add key" }).every((button) => !(button as HTMLButtonElement).disabled)).toBe(true);
    fireEvent.change(openAiKey, { target: { value: "temporary-not-saved-provider-key" } });
    expect(openAiKey).toHaveValue("temporary-not-saved-provider-key");
    expect(screen.getAllByRole("button", { name: "Save key" }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
    const openAiRow = openAiKey.closest(".provider-credential-row");
    expect(openAiRow).not.toBeNull();
    const addOpenAiKey = within(openAiRow as HTMLElement).getByRole("button", { name: "Add key" });
    const saveCredential = vi.spyOn(api, "saveProviderCredential");
    fireEvent.submit((openAiRow as HTMLElement).querySelector("form") as HTMLFormElement);
    expect(saveCredential).not.toHaveBeenCalled();
    fireEvent.click(within(openAiRow as HTMLElement).getByRole("button", { name: "Cancel key change" }));
    expect(screen.queryByLabelText("OpenAI API key")).not.toBeInTheDocument();
    fireEvent.click(addOpenAiKey);
    expect(screen.getByLabelText("OpenAI API key")).toBeEnabled();
    expect(screen.getByText("Laya (local fallback)")).toBeInTheDocument();
    expect(screen.getByText(/Jev \(TypeSafe\) is preferred for typed decisions/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Supabase Vault security setup");
  });

  it("does not claim credentials are absent when settings loading fails", async () => {
    renderSettings(control, vi.fn().mockRejectedValue(new Error("settings unavailable")));
    await screen.findByText("Controls unavailable");
    expect(screen.queryByText("No API key saved")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Add key" }).every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
  });

  it("keeps a credential draft after a failed save", async () => {
    const configured = structuredClone(control);
    configured.credential_management_available = true;
    const openai = configured.providers.find((item) => item.id === "openai");
    if (openai) openai.credential_storage_available = true;
    vi.spyOn(api, "saveProviderCredential").mockRejectedValue(new Error("Save failed"));
    renderSettings(configured);
    const input = await screen.findByLabelText("OpenAI API key");
    fireEvent.change(input, { target: { value: "failed-save-provider-key-123" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(await screen.findByText("Save failed")).toBeInTheDocument();
    expect(input).toHaveValue("failed-save-provider-key-123");
  });

  it("resets all agent model tiers to the selected provider defaults", async () => {
    renderSettings();
    fireEvent.click(await screen.findByText("Chef"));
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "gemini" } });
    expect(screen.getByLabelText("Economy model")).toHaveValue("gemini-3.5-flash-lite");
    expect(screen.getByLabelText("Fast model")).toHaveValue("gemini-3.8-flash");
    expect(screen.getByLabelText("Reasoning model")).toHaveValue("gemini-3.8-flash");
  });

  it("clears the credential draft after a successful save", async () => {
    const configured = structuredClone(control);
    configured.credential_management_available = true;
    const openai = configured.providers.find((item) => item.id === "openai");
    if (openai) openai.credential_storage_available = true;
    vi.spyOn(api, "saveProviderCredential").mockResolvedValue({ provider: "openai", configured: true });
    renderSettings(configured);
    const input = await screen.findByLabelText("OpenAI API key");
    fireEvent.change(input, { target: { value: "successful-save-provider-key-123" } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(await screen.findByText("Key saved securely.")).toBeInTheDocument();
    const row = screen.getByText("OpenAI", { selector: "strong" }).closest(".provider-credential-row") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Add key" }));
    expect(screen.getByLabelText("OpenAI API key")).toHaveValue("");
  });

  it("opens an agent's model tiers and domain-scoped memory link", async () => {
    renderSettings();
    expect(await screen.findByText("Chef")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Chef"));
    expect(screen.getByLabelText("Economy model")).toBeInTheDocument();
    expect(screen.getByLabelText("Fast model")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Chef memory" })).toHaveAttribute("href", "/settings/personal-model?domain=kitchen");
  });

  it("saves an agent profile with the control version and resets draft defaults", async () => {
    const save = vi.spyOn(api, "updateAgentProfile").mockResolvedValue({ ...control.agents[0], profile: { display_name: "Chef", standing_instructions: "", response_style: "balanced", continuity_enabled: true, decision_routing_enabled: false } });
    renderSettings();
    fireEvent.click(await screen.findByText("Chef"));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Kitchen guide" } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("chef", expect.objectContaining({ display_name: "Kitchen guide" }), 1));
    fireEvent.change(screen.getByLabelText("Display name"), { target: { value: "Changed again" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset defaults" }));
    expect(screen.getByLabelText("Display name")).toHaveValue("Chef");
  });

  it("submits the profile form directly without triggering model save", async () => {
    const profileSave = vi.spyOn(api, "updateAgentProfile").mockResolvedValue({ ...control.agents[0], profile: { display_name: "Chef", standing_instructions: "", response_style: "concise", continuity_enabled: true, decision_routing_enabled: false } });
    const modelSave = vi.spyOn(api, "updateAgentModels").mockResolvedValue([]);
    renderSettings();
    fireEvent.click(await screen.findByText("Chef"));
    fireEvent.change(screen.getByLabelText("Response style"), { target: { value: "concise" } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
    await waitFor(() => expect(profileSave).toHaveBeenCalledWith("chef", expect.objectContaining({ response_style: "concise" }), 1));
    expect(modelSave).not.toHaveBeenCalled();
  });

  it("allows saving model preferences before securely stored provider credentials exist", async () => {
    const save = vi.spyOn(api, "updateAgentModels").mockResolvedValue([]);
    renderSettings();
    fireEvent.click(await screen.findByText("Chef"));

    expect(screen.getByText("Preferences can be saved now. Add this provider's key in Providers before this agent can run.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save agent settings" }));

    expect(await screen.findByText("Preferences saved. Live execution starts after the provider key is stored securely.")).toBeInTheDocument();
    expect(save).toHaveBeenCalledWith({ chef: {
      provider: "openai", economy_model: "gpt-5-nano", fast_model: "gpt-5-mini", reasoning_model: "gpt-5.1",
    } });
  });

  it("runs the isolated OpenAI chat and Jev typed-decision checks from Settings", async () => {
    const configured = structuredClone(control);
    for (const provider of configured.providers) {
      if (provider.id === "openai" || provider.id === "jev") {
        provider.credential_configured = true;
        provider.configured = true;
      }
    }
    expect(configured.providers.find((provider) => provider.id === "openai" && provider.kind === "agent")?.credential_configured).toBe(true);
    const openAI = vi.spyOn(api, "testOpenAIChat").mockResolvedValue({
      provider: "openai", model: "gpt-5-mini", connected: true, passed: true,
      response: "LIFE OS OPENAI TEST OK", latency_ms: 300,
    });
    const jev = vi.spyOn(api, "testJevDecision").mockResolvedValue({
      provider: "jev", model: "jev-latest", connected: true, passed: true,
      selected_answer: true, true_probability: 0.95, trace_id: "trace-test", latency_ms: 120,
    });
    const view = renderSettings(configured);

    const openAITestButton = await screen.findByRole("button", { name: "Test OpenAI chat" });
    await waitFor(() => expect(openAITestButton).toBeEnabled());
    fireEvent.click(openAITestButton);
    await waitFor(() => expect(openAI).toHaveBeenCalledOnce());
    expect(view.container.querySelector(".provider-capability-tests")?.textContent).toContain("gpt-5-mini · LIFE OS OPENAI TEST OK");
    const jevTestButton = screen.getByRole("button", { name: "Test Jev decision" });
    await waitFor(() => expect(jevTestButton).toBeEnabled());
    fireEvent.click(jevTestButton);
    await waitFor(() => expect(jev).toHaveBeenCalledOnce());
    expect(view.container.querySelector(".provider-capability-tests")?.textContent).toContain("jev-latest · TRUE · 95% yes probability");
  });

  it("shows the active embedding route and can explicitly test and save OpenAI", async () => {
    const configured = structuredClone(control);
    const openai = configured.providers.find((item) => item.id === "openai");
    if (openai) { openai.credential_configured = true; openai.configured = true; }
    const save = vi.mocked(api.updateEmbeddingSettings);
    const testProvider = vi.mocked(api.testEmbeddingProvider);
    renderSettings(configured);

    expect(await screen.findByText("fake · life-os-fake-embedding · 768 dimensions")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Test OpenAI embeddings" }));
    expect(await screen.findByText("text-embedding-3-small · 768 dimensions")).toBeInTheDocument();
    expect(testProvider).toHaveBeenCalledWith({ provider: "openai", model: "text-embedding-3-small" });

    fireEvent.change(screen.getByLabelText("Embedding provider"), { target: { value: "openai" } });
    fireEvent.change(screen.getByLabelText("Embedding model"), { target: { value: "text-embedding-3-large" } });
    fireEvent.click(screen.getByRole("button", { name: "Save embedding route" }));
    expect(await screen.findByText("Embedding route saved. New indexing and search requests will use it.")).toBeInTheDocument();
    expect(save).toHaveBeenCalledWith({ provider: "openai", model: "text-embedding-3-large", expected_version: 1 });
  });
});
