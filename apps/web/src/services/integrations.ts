import { apiRequest } from "./api";

export type IntegrationScope = "tenant" | "installation";
export type IntegrationEnvironment = "sandbox" | "production";
export type IntegrationErrorCode =
  | "not_configured"
  | "client_id_required"
  | "test_unavailable"
  | "authentication_failed"
  | "rate_limited"
  | "provider_unavailable"
  | "provider_rejected"
  | "invalid_response"
  | "timeout"
  | "network_error";

export type IntegrationProvider = {
  id: string;
  name: string;
  kind: "api" | "public" | "import";
  configured: boolean;
  credential_management_available: boolean;
  scope: IntegrationScope;
  environment: IntegrationEnvironment;
  capabilities: string[];
  last_success_at?: string | null;
  last_attempt_at?: string | null;
  error_code?: IntegrationErrorCode | null;
  language?: string | null;
  region?: string | null;
  client_id?: string | null;
  attribution?: string | null;
};
export type CredentialResult = { provider: string; configured: boolean; scope: IntegrationScope };
export type IntegrationTestResult = CredentialResult & {
  success: boolean;
  error_code?: IntegrationErrorCode | null;
  last_attempt_at: string;
  last_success_at?: string | null;
};

export type IntegrationsResponse = {
  providers: IntegrationProvider[];
  credential_management_available: boolean;
};

export type IntegrationCredentialPayload = {
  api_key: string;
  client_id?: string | null;
  scope: IntegrationScope;
  environment?: IntegrationEnvironment;
  language?: string | null;
  region?: string | null;
};

export const integrationsService = {
  list: (scope: IntegrationScope) => apiRequest<IntegrationsResponse>(`/settings/integrations?scope=${scope}`),
  saveCredential: (providerId: string, payload: IntegrationCredentialPayload) =>
    apiRequest<CredentialResult>(`/settings/integrations/${encodeURIComponent(providerId)}/credentials`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  removeCredential: (providerId: string, scope: IntegrationScope) =>
    apiRequest<CredentialResult>(`/settings/integrations/${encodeURIComponent(providerId)}/credentials?scope=${scope}`, { method: "DELETE" }),
  test: (providerId: string, scope: IntegrationScope) =>
    apiRequest<IntegrationTestResult>(`/settings/integrations/${encodeURIComponent(providerId)}/test?scope=${scope}`, { method: "POST" })
};
