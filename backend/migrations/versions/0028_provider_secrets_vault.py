"""Store per-user provider credentials behind private Supabase Vault functions.

Revision ID: 0028_provider_secrets_vault
Revises: 0027_capture_review_settings
"""

from alembic import op


revision = "0028_provider_secrets_vault"
down_revision = "0027_capture_review_settings"
branch_labels = None
depends_on = None


FUNCTIONS = (
    "private.set_lifeos_provider_secret(text, text, text)",
    "private.get_lifeos_provider_secret(text, text)",
    "private.has_lifeos_provider_secret(text, text)",
    "private.delete_lifeos_provider_secret(text, text)",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault")
    op.execute("""
        DO $$ BEGIN
            IF (to_regprocedure('vault.create_secret(text,text,text)') IS NULL
                AND to_regprocedure('vault.create_secret(text,text,text,uuid)') IS NULL)
               OR (to_regprocedure('vault.update_secret(uuid,text,text,text)') IS NULL
                   AND to_regprocedure('vault.update_secret(uuid,text,text,text,uuid)') IS NULL) THEN
                RAISE EXCEPTION 'Supabase Vault must be enabled before applying provider secret storage';
            END IF;
        END $$;
    """)
    op.execute("CREATE SCHEMA IF NOT EXISTS private AUTHORIZATION CURRENT_USER")
    op.execute("REVOKE ALL ON SCHEMA private FROM PUBLIC, anon, authenticated, service_role")
    op.execute("GRANT USAGE ON SCHEMA private TO CURRENT_USER")
    op.execute("""
        CREATE OR REPLACE FUNCTION private.set_lifeos_provider_secret(
            p_user_id text, p_provider text, p_secret text
        ) RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        DECLARE
            secret_name text;
            secret_id uuid;
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            IF p_user_id IS NULL OR p_provider IS NULL OR p_provider NOT IN ('openai', 'gemini')
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
    op.execute("""
        CREATE OR REPLACE FUNCTION private.get_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ('openai', 'gemini') THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            RETURN (
                SELECT decrypted_secret
                FROM vault.decrypted_secrets
                WHERE name = 'lifeos:' || p_user_id || ':' || p_provider
                  AND p_provider IN ('openai', 'gemini')
                LIMIT 1
            );
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION private.has_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ('openai', 'gemini') THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            RETURN EXISTS (
                SELECT 1 FROM vault.secrets
                WHERE name = 'lifeos:' || p_user_id || ':' || p_provider
                  AND p_provider IN ('openai', 'gemini')
            );
        END;
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION private.delete_lifeos_provider_secret(
            p_user_id text, p_provider text
        ) RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, vault
        AS $$
        BEGIN
            IF current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ('openai', 'gemini') THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            DELETE FROM vault.secrets
            WHERE name = 'lifeos:' || p_user_id || ':' || p_provider
              AND p_provider IN ('openai', 'gemini');
        END;
        $$
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC, anon, authenticated, service_role")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO CURRENT_USER")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for function in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION IF EXISTS {function}")
