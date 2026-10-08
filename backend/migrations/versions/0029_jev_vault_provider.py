"""Allow Jev as an account-scoped Supabase Vault provider.

Revision ID: 0029_jev_vault_provider
Revises: 0028_provider_secrets_vault
"""

from alembic import op


revision = "0029_jev_vault_provider"
down_revision = "0028_provider_secrets_vault"
branch_labels = None
depends_on = None


def _replace_provider_allowlist(providers: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{provider}'" for provider in providers)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION private.set_lifeos_provider_secret(
            p_user_id text, p_provider text, p_secret text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        DECLARE secret_name text; secret_id uuid;
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            IF p_user_id IS NULL OR p_provider IS NULL OR p_provider NOT IN ({allowed})
               OR length(p_secret) < 20 OR length(p_secret) > 512 THEN
                RAISE EXCEPTION 'Invalid provider credential';
            END IF;
            secret_name := 'lifeos:' || p_user_id || ':' || p_provider;
            SELECT id INTO secret_id FROM vault.secrets WHERE name = secret_name;
            IF secret_id IS NULL THEN
                PERFORM vault.create_secret(p_secret, secret_name, 'Life OS provider credential');
            ELSE
                PERFORM vault.update_secret(secret_id, p_secret, secret_name, 'Life OS provider credential');
            END IF;
        END;
        $$
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION private.get_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS text
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ({allowed}) THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            RETURN (
                SELECT decrypted_secret FROM vault.decrypted_secrets
                WHERE name = 'lifeos:' || p_user_id || ':' || p_provider
                LIMIT 1
            );
        END;
        $$
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION private.has_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS boolean
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ({allowed}) THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            RETURN EXISTS (
                SELECT 1 FROM vault.secrets
                WHERE name = 'lifeos:' || p_user_id || ':' || p_provider
            );
        END;
        $$
    """)
    op.execute(f"""
        CREATE OR REPLACE FUNCTION private.delete_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ({allowed}) THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            DELETE FROM vault.secrets
            WHERE name = 'lifeos:' || p_user_id || ':' || p_provider;
        END;
        $$
    """)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _replace_provider_allowlist(("openai", "gemini", "jev"))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM vault.secrets WHERE name LIKE 'lifeos:%:jev') THEN
                    RAISE EXCEPTION 'Cannot remove Jev Vault support while Jev credentials are stored';
                END IF;
            END $$;
        """)
        _replace_provider_allowlist(("openai", "gemini"))
