import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { LetterboxdImportPanel } from "../movies/LetterboxdImportPanel";
import { integrationsService, type IntegrationCredentialPayload, type IntegrationErrorCode, type IntegrationProvider, type IntegrationScope, type IntegrationTestResult } from "../../services/integrations";
import "./integrations.css";

const errorLabels: Record<IntegrationErrorCode, string> = {
  not_configured: "No credential is configured.",
  client_id_required: "A Plaid client ID is required.",
  test_unavailable: "Connection testing is unavailable.",
  authentication_failed: "The provider rejected the credential.",
  rate_limited: "The provider rate limit was reached.",
  provider_unavailable: "The provider is temporarily unavailable.",
  provider_rejected: "The provider rejected the request.",
  invalid_response: "The provider returned an invalid response.",
  timeout: "The provider did not respond in time.",
  network_error: "The provider could not be reached."
};

function statusLabel(provider: IntegrationProvider) {
  if (provider.kind === "import") return "Import source";
  if (provider.kind === "public") return "Public catalog";
  if (!provider.credential_management_available) return "Vault unavailable";
  return provider.configured ? "Configured" : "Missing";
}

function statusClass(provider: IntegrationProvider) {
  if (provider.kind !== "api") return "informational";
  return provider.configured ? "available" : "not-configured";
}

export function IntegrationsPage() {
  const { provider: providerId } = useParams<{ provider?: string }>();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<IntegrationScope>("tenant");
  const isLetterboxd = providerId === "letterboxd";
  const query = useQuery({ queryKey: ["integrations", scope], queryFn: () => integrationsService.list(scope), retry: false, enabled: !isLetterboxd });
  const providers = query.data?.providers ?? [];
  const focused = providerId ? providers.filter((item) => item.id === providerId) : providers;

  return <div className="stack integrations-page">
    <header className="settings-command-band"><div><span className="eyebrow">Settings</span><h2>Integrations</h2><p>Manage external connections and scoped, write-only credentials.</p></div><Link className="secondary-button" to="/settings">Back to settings</Link></header>
    {isLetterboxd ? <section className="content-band settings-section integrations-list"><article className="integration-card"><header><div><h3>Letterboxd</h3><p>Import source</p></div><span className="provider-state informational">Import source</span></header><LetterboxdImportPanel /></article></section> : <>
    <div className="integration-scope-control"><label htmlFor="integration-scope">Credential scope</label><select id="integration-scope" value={scope} onChange={(event) => setScope(event.target.value as IntegrationScope)}><option value="tenant">My account</option><option value="installation">Installation</option></select><small>Installation scope is available only to explicitly configured administrators.</small></div>
    {!query.isLoading && query.isError ? <p className="status-text error" role="alert">{scope === "installation" ? "Installation-scoped access is unavailable for this account." : "Integrations could not be loaded."}</p> : null}
    {!query.data?.credential_management_available && query.data ? <p className="settings-security-note" role="status">Secure Vault storage is unavailable. New credentials cannot be saved.</p> : null}
    <section className="content-band settings-section integrations-list">{focused.map((provider) => <IntegrationCard key={`${scope}:${provider.id}`} provider={provider} scope={scope} queryClient={queryClient} />)}{!query.isLoading && !query.isError && focused.length === 0 ? <p>No integration provider was found.</p> : null}</section>
    </>}
  </div>;
}

function IntegrationCard({ provider, scope, queryClient }: { provider: IntegrationProvider; scope: IntegrationScope; queryClient: ReturnType<typeof useQueryClient> }) {
  const initialEnvironment = provider.environment ?? "sandbox";
  const initialLanguage = provider.language ?? "";
  const initialRegion = provider.region ?? "";
  const initialClientId = provider.client_id ?? "";
  const [secret, setSecret] = useState("");
  const [clientId, setClientId] = useState(initialClientId);
  const [environment, setEnvironment] = useState(initialEnvironment);
  const [language, setLanguage] = useState(initialLanguage);
  const [region, setRegion] = useState(initialRegion);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const save = useMutation({ mutationFn: () => {
    const payload: IntegrationCredentialPayload = { api_key: secret, scope };
    if (environment !== initialEnvironment) payload.environment = environment;
    if (language !== initialLanguage) payload.language = language || null;
    if (region !== initialRegion) payload.region = region || null;
    if (clientId !== initialClientId) payload.client_id = clientId || null;
    return integrationsService.saveCredential(provider.id, payload);
  }, onSuccess: () => { setSecret(""); setMessage("Credentials saved securely."); setError(""); void queryClient.invalidateQueries({ queryKey: ["integrations", scope] }); }, onError: () => { setSecret(""); setMessage(""); setError(scope === "installation" ? "Installation-scoped credentials could not be saved for this account." : "Credentials could not be saved."); } });
  const remove = useMutation({ mutationFn: () => integrationsService.removeCredential(provider.id, scope), onSuccess: () => { setMessage("Credential removed."); setError(""); void queryClient.invalidateQueries({ queryKey: ["integrations", scope] }); }, onError: () => setError(scope === "installation" ? "Installation-scoped credentials could not be removed for this account." : "Credentials could not be removed.") });
  const testConnection = useMutation({ mutationFn: () => integrationsService.test(provider.id, scope), onSuccess: async (result: IntegrationTestResult) => { if (result.success) { setMessage("Connection test succeeded."); setError(""); } else { setMessage(""); setError(result.error_code ? `Connection test failed. ${errorLabels[result.error_code]}` : "Connection test failed."); } await queryClient.invalidateQueries({ queryKey: ["integrations", scope] }); }, onError: () => { setMessage(""); setError(scope === "installation" ? "Installation-scoped connection testing is unavailable for this account." : "Connection test failed."); } });

  return <article className="integration-card">
    <header><div><h3><Link to={`/settings/integrations/${provider.id}`}>{provider.name}</Link></h3><p>{provider.kind === "import" ? "Import source" : provider.kind === "public" ? "Public catalog" : "API connection"}</p></div><span className={`provider-state ${statusClass(provider)}`}>{statusLabel(provider)}</span></header>
    {provider.id === "tmdb" ? <p className="integration-attribution">{provider.attribution ?? "This product uses the TMDB API but is not endorsed or certified by TMDB."}</p> : null}
    {provider.id === "letterboxd" ? <><p>Preview and confirm an official Letterboxd CSV export.</p><Link className="secondary-button integration-open-link" to="/settings/integrations/letterboxd">Import from Letterboxd</Link></> : null}
    {provider.kind === "api" ? <form className="integration-form" onSubmit={(event) => { event.preventDefault(); setMessage(""); setError(""); save.mutate(); }}><label>New API key<input aria-label={`New ${provider.name} API key`} type="password" minLength={20} autoComplete="new-password" value={secret} onChange={(event) => setSecret(event.target.value)} placeholder={provider.configured ? "Replace saved key" : "Enter key"} disabled={!provider.credential_management_available || save.isPending} /></label>{provider.id === "plaid" ? <label>Client ID<input aria-label="Plaid client ID" value={clientId} onChange={(event) => setClientId(event.target.value)} disabled={!provider.credential_management_available || save.isPending} /></label> : null}<label>Environment<select aria-label={`${provider.name} environment`} value={environment} onChange={(event) => setEnvironment(event.target.value as "sandbox" | "production")} disabled={!provider.credential_management_available || save.isPending}><option value="sandbox">Sandbox</option><option value="production">Production</option></select></label><label>Language<input aria-label={`${provider.name} language`} value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="Optional, for example en" /></label><label>Region<input aria-label={`${provider.name} region`} value={region} onChange={(event) => setRegion(event.target.value)} placeholder="Optional, for example DE" /></label><div className="integration-actions"><button className="primary-button" type="submit" disabled={!secret || !provider.credential_management_available || save.isPending}>Save credential</button>{provider.configured ? <button className="secondary-button" type="button" onClick={() => remove.mutate()} disabled={remove.isPending}>Remove</button> : null}<button className="secondary-button" type="button" onClick={() => testConnection.mutate()} disabled={!provider.configured || testConnection.isPending}>{testConnection.isPending ? "Testing" : "Test connection"}</button></div></form> : null}
    {message ? <p className="status-text success" role="status">{message}</p> : null}{error ? <p className="status-text error" role="alert">{error}</p> : null}{provider.last_attempt_at ? <small>Last attempt: {new Date(provider.last_attempt_at).toLocaleString()}</small> : null}{provider.last_success_at ? <small>Last success: {new Date(provider.last_success_at).toLocaleString()}</small> : null}{provider.error_code ? <small>Last result: {errorLabels[provider.error_code]}</small> : null}
  </article>;
}
