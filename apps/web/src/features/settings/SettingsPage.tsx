import { Bell, BrainCircuit, Check, ChevronRight, Database, Download, Gauge, KeyRound, LogOut, MessageSquare, RefreshCw, ShieldCheck, SlidersHorizontal, Trash2, Wrench } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { FormEvent, MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signOut } from "../../lib/auth";
import { enablePushNotifications, type PushSetupResult } from "../../lib/push";
import { api } from "../../services/api";
import type { AgentProfile, AgentSettings, EmbeddingSettings, IntelligenceControlSurface, IntelligenceSettings } from "../../types/api";

type ProviderName = "openai" | "gemini";
type CredentialProvider = ProviderName | "jev";
type ModelPreferences = { provider: ProviderName; economy_model: string; fast_model: string; reasoning_model: string };

export function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const controlQuery = useQuery({ queryKey: ["intelligence-settings"], queryFn: typeof api.intelligenceSettings === "function" ? api.intelligenceSettings : async () => null });
  const [pushState, setPushState] = useState<PushSetupResult | "idle" | "working">("idle");
  const [exportState, setExportState] = useState<"idle" | "working" | "done" | "error">("idle");
  const [budgetDraft, setBudgetDraft] = useState("");
  const [providerModels, setProviderModels] = useState<Record<ProviderName, string[]>>({ openai: [], gemini: [] });
  const [modelRefreshState, setModelRefreshState] = useState<Partial<Record<ProviderName, "working" | "success" | "error">>>({});
  const updateSettings = useMutation({
    mutationFn: (payload: Partial<IntelligenceSettings>) => api.updateIntelligenceSettings({ ...payload, expected_version: controlQuery.data?.settings.version }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["intelligence-settings"] })
  });

  async function handlePush() { setPushState("working"); setPushState(await enablePushNotifications()); }
  async function handleExport() {
    setExportState("working");
    try {
      const payload = await api.exportData();
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = `life-os-export-${new Date().toISOString().slice(0, 10)}.json`; anchor.click();
      URL.revokeObjectURL(url); setExportState("done");
    } catch { setExportState("error"); }
  }
  async function handleLogout() { await signOut(); navigate("/login", { replace: true }); }
  async function refreshProviderModels(provider: ProviderName) {
    setModelRefreshState((state) => ({ ...state, [provider]: "working" }));
    try {
      const result = await api.providerModels(provider);
      setProviderModels((models) => ({ ...models, [provider]: result.models }));
      setModelRefreshState((state) => ({ ...state, [provider]: "success" }));
    } catch {
      setModelRefreshState((state) => ({ ...state, [provider]: "error" }));
    }
  }

  const control = controlQuery.data;
  const current = control?.settings;
  const budget = control?.usage;
  const budgetPercent = budget?.budget_eur ? Math.min(100, Math.round((budget.monthly_spend_eur / budget.budget_eur) * 100)) : 0;

  return (
    <div className="stack intelligence-settings-page">
      <header className="settings-command-band">
        <div><span className="eyebrow">Settings</span><h2>Intelligence controls</h2><p>Choose how Life OS remembers, asks, and steps forward.</p></div>
        <span className={`provider-state ${controlQuery.isLoading || controlQuery.isError ? "not-configured" : "available"}`}>
          {controlQuery.isLoading ? "Loading settings" : controlQuery.isError ? "Controls unavailable" : "Connected"}
        </span>
      </header>

      <section className="content-band settings-section">
        <SectionTitle icon={<SlidersHorizontal size={18} />} title="Initiative" copy="How often Life OS should surface non-urgent intelligence." />
        <div className="segmented-control" role="group" aria-label="Proactivity mode">
          {(["QUIET", "BALANCED", "PROACTIVE"] as const).map((mode) => <button key={mode} type="button" className={current?.proactivity_mode === mode ? "active" : ""} onClick={() => updateSettings.mutate({ proactivity_mode: mode })}>{mode.toLowerCase()}</button>)}
        </div>
        <div className="settings-toggle-grid">
          <SettingToggle label="Passive suggestions" checked={current?.passive_suggestions_enabled ?? true} onChange={(value) => updateSettings.mutate({ passive_suggestions_enabled: value })} />
          <SettingToggle label="Questions" checked={current?.questions_enabled ?? true} onChange={(value) => updateSettings.mutate({ questions_enabled: value })} />
          <SettingToggle label="Interruptions" checked={current?.interruptions_enabled ?? true} onChange={(value) => updateSettings.mutate({ interruptions_enabled: value })} />
        </div>
      </section>

      <section className="content-band settings-section">
        <SectionTitle icon={<BrainCircuit size={18} />} title="Memory and patterns" copy="Inspect, correct, pin, or forget what shapes context." />
        <div className="settings-summary-row"><span><strong>{sumCounts(control?.memory.counts)}</strong> memories</span><span><strong>{sumCounts(control?.patterns.counts)}</strong> patterns</span></div>
        <div className="settings-toggle-grid">
          <SettingToggle label="Use memories in context" checked={current?.memory_visible ?? true} onChange={(value) => updateSettings.mutate({ memory_visible: value })} />
          <SettingToggle label="Use learned patterns" checked={current?.patterns_visible ?? true} onChange={(value) => updateSettings.mutate({ patterns_visible: value })} />
        </div>
        <Link className="secondary-button inline-action" to="/settings/personal-model"><BrainCircuit size={16} />Open personal model</Link>
      </section>

      <EmbeddingSettingsPanel providerStates={control?.providers ?? []} />

      <section className="content-band settings-section">
        <SectionTitle icon={<MessageSquare size={18} />} title="Conversations" copy={control?.conversations.delete_semantics ?? "Archived conversations do not delete your Life OS records."} />
        <div className="settings-summary-row"><span><strong>{control?.conversations.counts.active ?? 0}</strong> active</span><span><strong>{control?.conversations.counts.archived ?? 0}</strong> archived</span></div>
        <Link className="secondary-button inline-action" to="/assistant"><MessageSquare size={16} />Manage conversations</Link>
      </section>

      <section className="content-band settings-section">
        <SectionTitle icon={<Wrench size={18} />} title="Skills" copy="Disabled skills stop receiving Self Core requests." />
        <div className="settings-skill-list">
          {(control?.skills ?? []).map((skill) => <div className="settings-skill-row" key={skill.name}>
            <div><strong>{skill.name.replaceAll("-", " ")}</strong><small>{skill.description}</small></div>
            <label className="switch-control"><input type="checkbox" checked={skill.enabled} disabled={!skill.configured_enabled || updateSettings.isPending} onChange={(event) => {
              const disabled = new Set(current?.disabled_skills ?? []); if (event.target.checked) disabled.delete(skill.name); else disabled.add(skill.name); updateSettings.mutate({ disabled_skills: [...disabled] });
            }} aria-label={`${skill.enabled ? "Disable" : "Enable"} ${skill.name}`} /><span /></label>
          </div>)}
        </div>
      </section>

      <section className="content-band settings-section">
        <SectionTitle icon={<KeyRound size={18} />} title="Providers" copy="Manage secure credentials for generation, embeddings, and decision layers." />
        {control && !control.credential_management_available ? <p className="settings-security-note" role="status">Secure hosted credential storage is not enabled yet. Keys cannot be saved until the Supabase Vault security setup is completed.</p> : null}
        <p className="settings-secret-note">Saved credentials are write-only here. Life OS never sends their values back to the browser; environment keys do not fill these account-scoped entries.</p>
        <p className="settings-secret-note">Jev (TypeSafe) is preferred for typed decisions. Laya remains available as the local fallback layer.</p>
        <div className="provider-list">
          {(["openai", "gemini", "jev"] as const).map((provider) => {
            const status = control?.providers.find((item) => item.id === provider && item.kind === (provider === "jev" ? "decision" : "agent"));
            return <ProviderCredentialRow key={provider} provider={provider} configured={status?.credential_configured}
              vaultReady={control?.credential_management_available ?? false}
              storageReady={(control?.credential_management_available ?? false) && (provider !== "jev" || status?.credential_storage_available === true)}
              refreshing={provider !== "jev" && modelRefreshState[provider] === "working"}
              refreshFailed={provider !== "jev" && modelRefreshState[provider] === "error"}
              refreshSucceeded={provider !== "jev" && modelRefreshState[provider] === "success"}
              refreshedCount={provider !== "jev" ? providerModels[provider].length : 0}
              onChanged={() => queryClient.invalidateQueries({ queryKey: ["intelligence-settings"] })}
              onRefreshModels={provider === "jev" ? undefined : () => refreshProviderModels(provider)} />;
          })}
          {(() => {
            const laya = control?.providers.find((item) => item.id === "laya_local" && item.kind === "decision");
            return <div className="provider-row">
              <div className="provider-identity"><strong>Laya (local fallback)</strong><small>{laya?.models[0] ?? "Local decision layer"} · no API key required</small></div>
              <span className={`provider-state ${laya?.enabled ? "available" : "not-configured"}`}>{laya?.enabled ? "Enabled" : "Available when configured"}</span>
            </div>;
          })()}
        </div>
      </section>

      <section className="content-band settings-section">
        <span id="agent-settings" />
        <SectionTitle icon={<BrainCircuit size={18} />} title="Agents" copy="Choose a provider and model tier for each Life OS specialist." />
        <ProviderCapabilityTests providers={control?.providers ?? []} />
        <div className="agent-runtime-status">
          <span className={`provider-state ${control?.live_agents_enabled ? "available" : "not-configured"}`}>
            {control?.live_agents_enabled ? "Live agents enabled" : "Live agents not enabled"}
          </span>
          <small>Model changes apply to future assistant requests; saving does not call a provider.</small>
        </div>
        <div className="settings-agent-list">
          {(control?.agents ?? []).map((agent) => <AgentSettingsEditor key={agent.skill_name} agent={agent}
            models={providerModels} providerModels={control?.providers ?? []}
            expectedVersion={control?.settings.version} onSaved={() => queryClient.invalidateQueries({ queryKey: ["intelligence-settings"] })} />)}
        </div>
      </section>

      <section className="content-band settings-section">
        <SectionTitle icon={<Gauge size={18} />} title="Usage and budget" copy="Measured from the provider usage ledger for this month." />
        <div className="budget-line"><strong>€{(budget?.monthly_spend_eur ?? 0).toFixed(2)}</strong><span>of €{(budget?.budget_eur ?? 0).toFixed(2)}</span></div>
        <div className="budget-meter" aria-label={`${budgetPercent}% of monthly AI budget used`}><span style={{ width: `${budgetPercent}%` }} /></div>
        <form className="budget-form" onSubmit={(event) => { event.preventDefault(); const value = Number(budgetDraft); if (Number.isFinite(value) && value >= 0) updateSettings.mutate({ monthly_ai_budget_eur: value }); }}>
          <label>Monthly limit<input type="number" min="0" step="1" value={budgetDraft} placeholder={String(budget?.budget_eur ?? 0)} onChange={(event) => setBudgetDraft(event.target.value)} /></label>
          <button className="secondary-button" type="submit" disabled={!budgetDraft || updateSettings.isPending}><Check size={16} />Set limit</button>
        </form>
        {budget?.optional_suppressed ? <p className="status-text">Optional AI work is paused until the budget resets.</p> : null}
      </section>

      <section className="content-band settings-section">
        <SectionTitle icon={<Database size={18} />} title="Privacy and data" copy="Export your records, archive conversations, or use Memory to correct and forget individual facts." />
        <div className="settings-actions">
          <button className="settings-action" type="button" onClick={handleExport} disabled={exportState === "working"}><Download size={18} /><span>{exportState === "working" ? "Preparing export" : "Export Life OS data"}</span></button>
          <Link className="settings-action" to="/settings/personal-model"><ShieldCheck size={18} /><span>Review memory and patterns</span></Link>
          <button className="settings-action" type="button" onClick={handlePush} disabled={pushState === "working"}><Bell size={18} /><span>{pushState === "working" ? "Enabling reminders" : "Enable reminders"}</span></button>
          <button className="settings-action" type="button" onClick={handleLogout}><LogOut size={18} /><span>Log out</span></button>
        </div>
        {pushState !== "idle" && pushState !== "working" ? <p className={`status-text ${pushState === "enabled" ? "success" : "error"}`}>{pushMessage(pushState)}</p> : null}
        {exportState === "done" ? <p className="status-text success">Export downloaded.</p> : null}
        {exportState === "error" ? <p className="status-text error">Export could not be prepared.</p> : null}
      </section>
      {updateSettings.isError ? <p className="status-text error">That setting could not be saved. Refresh and try again.</p> : null}
    </div>
  );
}

function ProviderCredentialRow({ provider, configured, storageReady, vaultReady, refreshing, refreshFailed, refreshSucceeded, refreshedCount, onChanged, onRefreshModels }: {
  provider: CredentialProvider; configured: boolean | undefined; storageReady: boolean; vaultReady: boolean; refreshing: boolean; refreshFailed: boolean;
  refreshSucceeded: boolean; refreshedCount: number;
  onChanged: () => void; onRefreshModels?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const title = provider === "openai" ? "OpenAI" : provider === "gemini" ? "Google Gemini" : "Jev (TypeSafe)";

  useEffect(() => {
    if (configured !== undefined) setEditing(!configured);
  }, [configured]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!storageReady) {
      setError("Secure Vault storage is not ready. This key was not sent or saved.");
      return;
    }
    const submittedKey = apiKey;
    setSaving(true); setError(""); setMessage("");
    try {
      await api.saveProviderCredential(provider, submittedKey);
      setApiKey("");
      setEditing(false); setMessage("Key saved securely."); onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save this key.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    const usage = provider === "jev" ? "Jev-backed decisions will stop until another key is added." : "Agents using this provider will stop until another key is added.";
    if (!window.confirm(`Remove the saved ${title} key? ${usage}`)) return;
    setRemoving(true); setError(""); setMessage("");
    try {
      await api.deleteProviderCredential(provider);
      setMessage("Key removed."); onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove this key.");
    } finally {
      setRemoving(false);
    }
  }

  return <div className="provider-row provider-credential-row">
    <div className="provider-identity">
      <strong>{title}</strong>
      <small>{configured === undefined ? "Checking credential status" : provider === "jev" ? <>Typed decisions · jev-latest · {configured ? <>key <span className="credential-mask" aria-label="Key hidden">••••••••••••</span></> : "no key saved"}</> : configured ? <>API key <span className="credential-mask" aria-label="Key hidden">••••••••••••</span></> : "No API key saved"}</small>
    </div>
    <div className="provider-row-actions">
      <span className={`provider-state ${configured === undefined ? "not-configured" : configured ? "available" : "not-configured"}`}>{configured === undefined ? "Checking" : configured ? "Connected" : "Not configured"}</span>
      <button className="secondary-button compact-button" type="button" disabled={configured === undefined || saving || removing} onClick={() => { setEditing(true); setError(""); }}>
        {configured ? "Change key" : "Add key"}
      </button>
      {onRefreshModels ? <button className="icon-button settings-icon-button" type="button" title={`Refresh ${title} models`} aria-label={`Refresh ${title} models`} disabled={!configured || refreshing} onClick={onRefreshModels}>
        <RefreshCw size={15} className={refreshing ? "spin" : ""} />
      </button> : null}
      {configured ? <button className="icon-button settings-icon-button danger" type="button" title={`Remove ${title} key`} aria-label={`Remove ${title} key`} disabled={!storageReady || removing} onClick={remove}><Trash2 size={15} /></button> : null}
    </div>
    {editing ? <form className="provider-key-form" onSubmit={save}>
      <label>{configured ? `Replace ${title} API key` : `${title} API key`}
        <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="new-password" autoCapitalize="none" spellCheck={false} required minLength={20} maxLength={512} placeholder="Paste new API key" disabled={saving} />
      </label>
      {!storageReady ? <small className="status-text">Key saving is unavailable until secure Vault storage is ready. This unsaved value stays only in this page.</small> : null}
      <button className="secondary-button" type="submit" disabled={!storageReady || !apiKey.trim() || saving}>{saving ? "Saving securely" : "Save key"}</button>
      <button className="icon-button settings-icon-button" type="button" title="Cancel key change" aria-label="Cancel key change" disabled={saving} onClick={() => { setEditing(false); setApiKey(""); }}><ChevronRight size={16} /></button>
    </form> : null}
    {message ? <p className="status-text success provider-inline-message">{message}</p> : null}
    {error ? <p className="status-text error provider-inline-message">{error}</p> : null}
    {refreshFailed ? <p className="status-text error provider-inline-message">Model list could not be refreshed. Saved model choices remain available.</p> : null}
    {refreshSucceeded ? <p className="status-text success provider-inline-message">Verified. {refreshedCount} chat models available.</p> : null}
    {provider === "jev" && vaultReady && !storageReady ? <p className="settings-security-note provider-inline-message">Apply the Jev Vault migration before saving this provider key.</p> : null}
  </div>;
}

function EmbeddingSettingsPanel({ providerStates }: { providerStates: IntelligenceControlSurface["providers"] }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["embedding-settings"], queryFn: api.embeddingSettings });
  const [provider, setProvider] = useState<EmbeddingSettings["provider"]>("default");
  const [model, setModel] = useState("text-embedding-3-small");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [tests, setTests] = useState<Partial<Record<ProviderName, "working" | "success" | "error">>>({});
  const [testResults, setTestResults] = useState<Partial<Record<ProviderName, string>>>({});

  useEffect(() => {
    if (query.data) {
      setProvider(query.data.provider);
      setModel(query.data.model);
    }
  }, [query.data]);

  const modelOptions = provider === "gemini"
    ? ["gemini-embedding-001"]
    : ["text-embedding-3-small", "text-embedding-3-large"];
  const hasCredential = (name: ProviderName) => providerStates.some((item) => item.id === name && item.credential_configured);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setSaved(false); setError("");
    try {
      await api.updateEmbeddingSettings({
        provider,
        model: provider === "default" ? null : model,
        expected_version: query.data?.version,
      });
      setSaved(true);
      await queryClient.invalidateQueries({ queryKey: ["embedding-settings"] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Embedding settings could not be saved.");
    } finally { setSaving(false); }
  }

  async function test(providerToTest: ProviderName) {
    setTests((current) => ({ ...current, [providerToTest]: "working" }));
    setTestResults((current) => ({ ...current, [providerToTest]: "" }));
    try {
      const result = await api.testEmbeddingProvider({
        provider: providerToTest,
        model: providerToTest === "gemini" ? "gemini-embedding-001" : "text-embedding-3-small",
      });
      setTests((current) => ({ ...current, [providerToTest]: "success" }));
      setTestResults((current) => ({ ...current, [providerToTest]: `${result.model} · ${result.dimensions} dimensions` }));
    } catch (cause) {
      setTests((current) => ({ ...current, [providerToTest]: "error" }));
      setTestResults((current) => ({ ...current, [providerToTest]: cause instanceof Error ? cause.message : "Connection test failed." }));
    }
  }

  return <section className="content-band settings-section">
    <SectionTitle icon={<BrainCircuit size={18} />} title="Semantic embeddings" copy="Choose the provider that creates memory-search vectors. This is separate from chat models." />
    <p className="settings-security-note">Hosted embeddings send indexed text and search queries to the selected provider. Changing providers does not automatically upload or rebuild older vectors; incompatible vectors are ignored until refreshed.</p>
    <div className="embedding-current-route">
      <span>Current route</span>
      <strong>{query.data ? `${query.data.effective_provider} · ${query.data.model} · ${query.data.dimensions} dimensions` : query.isError ? "Route unavailable" : "Loading route"}</strong>
    </div>
    <form className="embedding-settings-form" onSubmit={save}>
      <label>Embedding provider
        <select value={provider} onChange={(event) => {
          const nextProvider = event.target.value as EmbeddingSettings["provider"];
          setProvider(nextProvider);
          if (nextProvider === "openai") setModel("text-embedding-3-small");
          if (nextProvider === "gemini") setModel("gemini-embedding-001");
          setSaved(false); setError("");
        }}>
          <option value="default">Use backend default</option>
          <option value="openai">OpenAI</option>
          <option value="gemini">Google Gemini</option>
        </select>
      </label>
      {provider !== "default" ? <label>Embedding model
        <select value={modelOptions.includes(model) ? model : modelOptions[0]} onChange={(event) => { setModel(event.target.value); setSaved(false); }}>
          {modelOptions.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </label> : null}
      <button className="secondary-button" type="submit" disabled={saving || query.isLoading || (provider !== "default" && !hasCredential(provider))}>
        <Check size={15} />{saving ? "Saving route" : "Save embedding route"}
      </button>
    </form>
    {provider !== "default" && !hasCredential(provider) ? <p className="status-text">Save a {provider === "openai" ? "OpenAI" : "Gemini"} key in Providers before selecting it here.</p> : null}
    <div className="embedding-test-row" aria-label="Embedding connection tests">
      {(["openai", "gemini"] as const).map((item) => <div className="embedding-test-provider" key={item}>
        <button className="secondary-button compact-button" type="button" disabled={!hasCredential(item) || tests[item] === "working"} onClick={() => test(item)}>
          <RefreshCw size={14} className={tests[item] === "working" ? "spin" : ""} />
          {tests[item] === "working" ? "Testing" : `Test ${item === "openai" ? "OpenAI" : "Gemini"} embeddings`}
        </button>
        {tests[item] && tests[item] !== "working" ? <small className={`status-text ${tests[item] === "success" ? "success" : "error"}`} role="status">{testResults[item]}</small> : null}
      </div>)}
    </div>
    {saved ? <p className="status-text success">Embedding route saved. New indexing and search requests will use it.</p> : null}
    {error ? <p className="status-text error">{error}</p> : null}
  </section>;
}

function AgentSettingsEditor({ agent, models, providerModels, expectedVersion, onSaved }: {
  agent: AgentSettings; models: Record<ProviderName, string[]>; providerModels: IntelligenceControlSurface["providers"]; expectedVersion?: number;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<ModelPreferences>({
    provider: agent.provider, economy_model: agent.economy_model,
    fast_model: agent.fast_model, reasoning_model: agent.reasoning_model,
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const defaultProfile: AgentProfile = { display_name: titleCaseSlug(agent.skill_name), standing_instructions: "", response_style: "balanced", continuity_enabled: true, decision_routing_enabled: false };
  const initialProfile = { ...defaultProfile, ...agent.profile };
  const [profile, setProfile] = useState<AgentProfile>(initialProfile);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");
  const provider = providerModels.find((item) => item.id === draft.provider && item.kind === "agent");
  const modelOptions = Array.from(new Set([
    draft.economy_model, draft.fast_model, draft.reasoning_model,
    ...(provider?.models ?? []), ...models[draft.provider],
  ].filter(Boolean)));

  function update<K extends keyof ModelPreferences>(field: K, value: ModelPreferences[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setSaved(false); setError("");
  }

  async function saveProfile(event: FormEvent<HTMLFormElement> | ReactMouseEvent<HTMLButtonElement>) {
    event.preventDefault(); setProfileMessage(""); setError("");
    const displayName = profile.display_name.trim();
    if (!displayName || displayName.length > 60 || profile.standing_instructions.length > 1200) { setError("Display name is required (max 60 characters); standing instructions must be 1200 characters or fewer."); return; }
    setProfileSaving(true);
    try { await api.updateAgentProfile(agent.skill_name, { ...profile, display_name: displayName }, expectedVersion); setProfileMessage("Profile saved."); onSaved(); }
    catch (cause) { setError("This profile is out of date or could not be saved. Reload settings and try again."); }
    finally { setProfileSaving(false); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setSaved(false); setError("");
    try {
      await api.updateAgentModels({ [agent.skill_name]: draft });
      setSaved(true); onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Agent settings could not be saved.");
    } finally { setSaving(false); }
  }

  return <details className="agent-settings-row">
    <summary>
      <span className="agent-summary-copy"><strong>{profile.display_name || agent.name}</strong><small>{agent.description}</small></span>
      <span className={`provider-state ${provider?.credential_configured ? "available" : "not-configured"}`}>{provider?.credential_configured ? draft.provider : "Needs provider key"}</span>
      <ChevronRight className="agent-expand-icon" size={16} aria-hidden="true" />
    </summary>
    <div className="agent-settings-form">
      <form onSubmit={save}>
      <div className="agent-model-grid">
        <label>Provider<select value={draft.provider} onChange={(event) => {
          const nextProvider = event.target.value as ProviderName;
          const defaults = defaultModels(nextProvider, providerModels);
          setDraft((current) => ({ ...current, provider: nextProvider, ...defaults }));
          setSaved(false); setError("");
        }}>
          <option value="openai">OpenAI</option><option value="gemini">Google Gemini</option>
        </select></label>
        <ModelSelect label="Economy model" value={draft.economy_model} options={modelOptions} onChange={(value) => update("economy_model", value)} />
        <ModelSelect label="Fast model" value={draft.fast_model} options={modelOptions} onChange={(value) => update("fast_model", value)} />
        <ModelSelect label="Reasoning model" value={draft.reasoning_model} options={modelOptions} onChange={(value) => update("reasoning_model", value)} />
      </div>
      <div className="agent-memory-row">
        <div><strong>Memory</strong><span>{agent.memory_scopes.join(" · ") || "No scoped memories"}</span><small>{agent.memory_count} {agent.memory_count === 1 ? "memory" : "memories"} in {agent.memory_domain}</small></div>
        <Link className="secondary-button compact-button" to={`/settings/personal-model?domain=${encodeURIComponent(agent.memory_domain)}`}>Open {agent.name} memory</Link>
      </div>
      <div className="agent-save-row">
        <button className="secondary-button" type="submit" disabled={saving}><Check size={15} />{saving ? "Saving" : "Save agent settings"}</button>
        {!provider?.credential_configured ? <small>Preferences can be saved now. Add this provider's key in Providers before this agent can run.</small> : null}
        {saved ? <span className={`status-text ${provider?.credential_configured ? "success" : ""}`}>{provider?.credential_configured ? "Saved. Applies to the next assistant request." : "Preferences saved. Live execution starts after the provider key is stored securely."}</span> : null}
        {error ? <span className="status-text error">{error}</span> : null}
      </div>
      </form>
      <form className="agent-profile-form" noValidate onSubmit={saveProfile}>
        <h4>Profile</h4>
        <label>Display name<input maxLength={60} required value={profile.display_name} onChange={(event) => setProfile({ ...profile, display_name: event.target.value })} disabled={profileSaving} /></label>
        <label>Standing instructions<textarea maxLength={1200} value={profile.standing_instructions} onChange={(event) => setProfile({ ...profile, standing_instructions: event.target.value })} disabled={profileSaving} /></label>
        <label>Response style<select value={profile.response_style} onChange={(event) => setProfile({ ...profile, response_style: event.target.value as AgentProfile["response_style"] })} disabled={profileSaving}><option value="concise">Concise</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></label>
        <div className="settings-toggle"><span>Enable continuity</span><label className="switch-control"><input aria-label="Enable continuity" type="checkbox" checked={profile.continuity_enabled} onChange={(event) => setProfile({ ...profile, continuity_enabled: event.target.checked })} disabled={profileSaving} /><span /></label></div>
        {agent.skill_name === "self-core" ? <div className="settings-toggle"><span>Use Jev for ambiguous cross-domain routing</span><label className="switch-control"><input aria-label="Use Jev for ambiguous cross-domain routing" type="checkbox" checked={profile.decision_routing_enabled} onChange={(event) => setProfile({ ...profile, decision_routing_enabled: event.target.checked })} disabled={profileSaving} /><span /></label></div> : null}
        <div className="agent-save-row"><button className="secondary-button" type="submit" onClick={(event) => void saveProfile(event)} disabled={profileSaving}><Check size={15} />{profileSaving ? "Saving" : "Save profile"}</button><button className="secondary-button" type="button" disabled={profileSaving} onClick={() => setProfile(defaultProfile)}>Reset defaults</button>{profileMessage ? <span className="status-text success">{profileMessage}</span> : null}</div>
      </form>
    </div>
  </details>;
}

function titleCaseSlug(value: string) {
  return value.split("-").filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}

function defaultModels(provider: ProviderName, providers: IntelligenceControlSurface["providers"]) {
  const models = providers.find((item) => item.id === provider && item.kind === "agent")?.models ?? [];
  const defaults = provider === "gemini"
    ? ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.8-flash"]
    : ["gpt-5-nano", "gpt-5-mini", "gpt-5.1"];
  return {
    economy_model: models[0] ?? defaults[0],
    fast_model: models[1] ?? defaults[1],
    reasoning_model: models[2] ?? defaults[2],
  };
}

function ModelSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label>{label}<select value={value} onChange={(event) => onChange(event.target.value)}>
    {options.map((option) => <option key={option} value={option}>{option}</option>)}
  </select></label>;
}

function ProviderCapabilityTests({ providers }: { providers: IntelligenceControlSurface["providers"] }) {
  const openAI = providers.find((item) => item.id === "openai" && item.kind === "agent");
  const jev = providers.find((item) => item.id === "jev" && item.kind === "decision");
  const [openAIState, setOpenAIState] = useState<{ status: "idle" | "working" | "success" | "error"; text?: string }>({ status: "idle" });
  const [jevState, setJevState] = useState<{ status: "idle" | "working" | "success" | "error"; text?: string }>({ status: "idle" });

  async function runOpenAITest() {
    setOpenAIState({ status: "working" });
    try {
      const result = await api.testOpenAIChat();
      setOpenAIState({
        status: result.connected && result.passed ? "success" : "error",
        text: `${result.model} · ${result.response} · ${result.latency_ms} ms`,
      });
    } catch (cause) {
      setOpenAIState({ status: "error", text: cause instanceof Error ? cause.message : "OpenAI test failed." });
    }
  }

  async function runJevTest() {
    setJevState({ status: "working" });
    try {
      const result = await api.testJevDecision();
      setJevState({
        status: result.connected && result.passed ? "success" : "error",
        text: `${result.model} · ${result.selected_answer ? "TRUE" : "FALSE"} · ${Math.round(result.true_probability * 100)}% yes probability · ${result.latency_ms} ms`,
      });
    } catch (cause) {
      setJevState({ status: "error", text: cause instanceof Error ? cause.message : "Jev decision test failed." });
    }
  }

  return <div className="provider-capability-tests">
    <p>Run isolated checks with fixed synthetic input. These tests do not include conversations, memories, schedules, or domain records.</p>
    <div className="embedding-test-row">
      <div className="embedding-test-provider">
        <button className="secondary-button compact-button" type="button" onClick={runOpenAITest} disabled={!openAI?.credential_configured || openAIState.status === "working"}>
          <RefreshCw size={14} className={openAIState.status === "working" ? "spin" : ""} />
          {openAIState.status === "working" ? "Testing OpenAI" : "Test OpenAI chat"}
        </button>
        {openAIState.text ? <small className={`status-text ${openAIState.status === "success" ? "success" : "error"}`} role="status">{openAIState.text}</small> : null}
      </div>
      <div className="embedding-test-provider">
        <button className="secondary-button compact-button" type="button" onClick={runJevTest} disabled={!jev?.credential_configured || jevState.status === "working"}>
          <RefreshCw size={14} className={jevState.status === "working" ? "spin" : ""} />
          {jevState.status === "working" ? "Testing Jev" : "Test Jev decision"}
        </button>
        {jevState.text ? <small className={`status-text ${jevState.status === "success" ? "success" : "error"}`} role="status">{jevState.text}</small> : null}
      </div>
    </div>
  </div>;
}

function SectionTitle({ icon, title, copy }: { icon: ReactNode; title: string; copy: string }) { return <div className="section-heading-icon">{icon}<div><h3>{title}</h3><p>{copy}</p></div></div>; }
function SettingToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) { return <label className="settings-toggle"><span>{label}</span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /></label>; }
function sumCounts(counts?: Record<string, number>) { return Object.values(counts ?? {}).reduce((total, value) => total + value, 0); }
function pushMessage(state: PushSetupResult) { if (state === "enabled") return "Reminders enabled."; if (state === "denied") return "Notifications are blocked."; if (state === "unsupported") return "Notifications are not supported here."; if (state === "missing_config") return "Push is not configured for this environment."; return "Could not enable reminders."; }
