# Agent Provider Credentials

OpenAI/Gemini agent-generation credentials and the Jev typed-decision credential are configured from **Settings → Providers**. Key inputs are write-only: the API accepts a new key but never returns it. Status responses expose only whether a key is configured. Keys are scoped to the authenticated Life OS user and stored in Supabase Vault through private backend-only database functions; they are not stored in browser storage, user settings JSON, or a local `.env` file.

The backend retrieves a key only for the current authenticated user and only when that user's selected agent or Jev decision route needs the corresponding provider. Jev's key is held only by a request-scoped adapter; the shared gateway never adopts a host environment key. The selected provider necessarily receives its key as request authentication. Other providers and other Life OS users do not receive it. Database statement parameters are hidden from SQLAlchemy engine logs, and upstream provider errors are sanitized before returning to the UI.

Each agent has independent OpenAI/Gemini provider selection and Economy, Fast, and Reasoning model choices. These preferences are stored in the user's existing intelligence-settings metadata; they contain model identifiers, never credentials. Saving preferences enables the SDK runtime for that user on later assistant requests. It does not make a provider request by itself. Specialist delegation resolves the specialist's own provider and model.

## Deployment Gate

OpenAI/Gemini write controls require migration `0028_provider_secrets_vault`; Jev additionally requires `0029_jev_vault_provider`. Both require Supabase Vault and the private backend database role/function grants and must be applied after the Supabase security review. They have not been applied to the configured database. Do not paste keys into `.env` as a substitute for this hosted account-scoped flow.
