"""Extend the existing Vault boundary with integration metadata and scoped secrets.

Revision ID: 0031_integration_credentials
Revises: 0030_supabase_data_api_lockdown
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_integration_credentials"
down_revision = "0030_supabase_data_api_lockdown"
branch_labels = None
depends_on = None

API_ROLES = "PUBLIC, anon, authenticated, service_role"
LEGACY_PROVIDERS = ("openai", "gemini", "jev")
INTEGRATION_PROVIDERS = ("api-football", "usda", "tmdb", "plaid")


def _tenant_functions(providers):
    allowed = ", ".join(f"'{provider}'" for provider in providers)
    for operation in ("set", "get", "has", "delete"):
        write = operation == "set"
        arguments = "p_user_id text, p_provider text" + (", p_secret text" if write else "")
        result = {"set": "void", "get": "text", "has": "boolean", "delete": "void"}[operation]
        validation = """
            IF p_secret IS NULL OR length(p_secret) < 20 OR length(p_secret) > 512 THEN
                RAISE EXCEPTION 'Invalid provider credential';
            END IF;
        """ if write else ""
        action = {
            "set": """
                PERFORM pg_advisory_xact_lock(hashtextextended(secret_name, 0));
                SELECT id INTO secret_id FROM vault.secrets WHERE name = secret_name;
                IF secret_id IS NULL THEN
                    PERFORM vault.create_secret(p_secret, secret_name, 'Life OS provider credential');
                ELSE
                    PERFORM vault.update_secret(secret_id, p_secret, secret_name, 'Life OS provider credential');
                END IF;
            """,
            "get": "RETURN (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = secret_name LIMIT 1);",
            "has": "RETURN EXISTS (SELECT 1 FROM vault.secrets WHERE name = secret_name);",
            "delete": "PERFORM pg_advisory_xact_lock(hashtextextended(secret_name, 0)); DELETE FROM vault.secrets WHERE name = secret_name;",
        }[operation]
        op.execute(f"""
            CREATE OR REPLACE FUNCTION private.{operation}_lifeos_provider_secret({arguments}) RETURNS {result}
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, vault AS $$
            DECLARE secret_name text; secret_id uuid;
            BEGIN
                IF p_user_id IS NULL OR current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
                   OR p_provider IS NULL OR p_provider NOT IN ({allowed}) THEN
                    RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
                END IF;
                {validation}
                secret_name := 'lifeos:' || p_user_id || ':' || p_provider;
                {action}
            END; $$;
        """)
        signature = f"private.{operation}_lifeos_provider_secret(text,text" + (",text)" if write else ")")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {API_ROLES}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO CURRENT_USER")


def _scoped_functions():
    op.execute("""
        CREATE FUNCTION private.lifeos_integration_secret_name(
            p_user_id text, p_scope text, p_provider text, p_connection_id text
        ) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
        BEGIN
            IF p_user_id IS NULL OR p_user_id !~ '^[a-f0-9-]{36}$'
               OR current_setting('app.user_id', true) IS DISTINCT FROM p_user_id
               OR p_provider IS NULL OR p_provider NOT IN ('openai', 'api-football', 'usda', 'tmdb', 'plaid') THEN
                RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
            END IF;
            IF p_scope = 'installation' AND p_connection_id IS NULL
               AND current_setting('app.integration_installation_admin', true) = 'true' THEN
                RETURN 'lifeos:installation:' || p_provider;
            ELSIF p_scope = 'connection' AND p_provider = 'plaid'
               AND p_connection_id IS NOT NULL AND p_connection_id ~ '^[a-f0-9-]{36}$' THEN
                -- Cast validates UUID syntax as well as the bounded namespace alphabet.
                PERFORM p_connection_id::uuid;
                PERFORM p_user_id::uuid;
                RETURN 'lifeos:connection:' || p_user_id || ':' || p_provider || ':' || p_connection_id;
            END IF;
            RAISE EXCEPTION 'Provider credential access denied' USING ERRCODE = '42501';
        END; $$;
    """)
    op.execute(f"REVOKE ALL ON FUNCTION private.lifeos_integration_secret_name(text,text,text,text) FROM {API_ROLES}")
    op.execute("GRANT EXECUTE ON FUNCTION private.lifeos_integration_secret_name(text,text,text,text) TO CURRENT_USER")
    for operation in ("set", "get", "has", "delete"):
        write = operation == "set"
        result = {"set": "void", "get": "text", "has": "boolean", "delete": "void"}[operation]
        arguments = "p_user_id text, p_scope text, p_provider text, p_connection_id text" + (", p_secret text" if write else "")
        validation = """
            IF p_secret IS NULL OR length(p_secret) < 20 OR length(p_secret) > 512 THEN
                RAISE EXCEPTION 'Invalid provider credential';
            END IF;
        """ if write else ""
        action = {
            "set": """
                PERFORM pg_advisory_xact_lock(hashtextextended(secret_name, 0));
                SELECT id INTO secret_id FROM vault.secrets WHERE name = secret_name;
                IF secret_id IS NULL THEN
                    PERFORM vault.create_secret(p_secret, secret_name, 'Life OS scoped provider credential');
                ELSE
                    PERFORM vault.update_secret(secret_id, p_secret, secret_name, 'Life OS scoped provider credential');
                END IF;
            """,
            "get": "RETURN (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name = secret_name LIMIT 1);",
            "has": "RETURN EXISTS (SELECT 1 FROM vault.secrets WHERE name = secret_name);",
            "delete": "PERFORM pg_advisory_xact_lock(hashtextextended(secret_name, 0)); DELETE FROM vault.secrets WHERE name = secret_name;",
        }[operation]
        op.execute(f"""
            CREATE FUNCTION private.{operation}_lifeos_scoped_provider_secret({arguments}) RETURNS {result}
            LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, vault AS $$
            DECLARE secret_name text; secret_id uuid;
            BEGIN
                secret_name := private.lifeos_integration_secret_name(p_user_id,p_scope,p_provider,p_connection_id);
                {validation}
                {action}
            END; $$;
        """)
        signature = f"private.{operation}_lifeos_scoped_provider_secret(text,text,text,text" + (",text)" if write else ")")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM {API_ROLES}")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO CURRENT_USER")


def upgrade():
    op.create_table(
        "integration_configurations",
        sa.Column("scope", sa.String(20), primary_key=True),
        sa.Column("owner_id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(40), primary_key=True),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("language", sa.String(10)),
        sa.Column("region", sa.String(2)),
        sa.Column("client_id", sa.String(128)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(40)),
        sa.CheckConstraint("scope IN ('tenant', 'installation')", name="ck_integration_configuration_scope"),
        sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_integration_configuration_environment"),
        sa.CheckConstraint("error_code IS NULL OR error_code IN ('not_configured', 'client_id_required', 'test_unavailable', 'authentication_failed', 'rate_limited', 'provider_unavailable', 'provider_rejected', 'invalid_response', 'timeout', 'network_error')", name="ck_integration_configuration_error_code"),
        sa.CheckConstraint("(scope = 'installation' AND owner_id = 'installation') OR (scope = 'tenant' AND owner_id <> 'installation')", name="ck_integration_configuration_owner"),
    )
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f"REVOKE ALL ON TABLE public.integration_configurations FROM {API_ROLES}")
    op.execute("ALTER TABLE public.integration_configurations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY integration_configuration_backend_owner ON public.integration_configurations
        USING ((scope = 'tenant' AND owner_id = current_setting('app.user_id', true))
            OR (scope = 'installation' AND current_setting('app.integration_installation_admin', true) = 'true'))
        WITH CHECK ((scope = 'tenant' AND owner_id = current_setting('app.user_id', true))
            OR (scope = 'installation' AND current_setting('app.integration_installation_admin', true) = 'true'))
    """)
    _tenant_functions(LEGACY_PROVIDERS + INTEGRATION_PROVIDERS)
    _scoped_functions()


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        # Never orphan scoped secrets or remove support while newly added keys exist.
        op.execute("""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM vault.secrets WHERE name LIKE 'lifeos:installation:%'
                    OR name LIKE 'lifeos:connection:%'
                    OR name ~ '^lifeos:[^:]+:(api-football|usda|tmdb|plaid)$') THEN
                    RAISE EXCEPTION 'Cannot downgrade while integration credentials are stored';
                END IF;
            END $$;
        """)
        for operation in ("set", "get", "has", "delete"):
            signature = f"private.{operation}_lifeos_scoped_provider_secret(text,text,text,text" + (",text)" if operation == "set" else ")")
            op.execute(f"DROP FUNCTION {signature}")
        op.execute("DROP FUNCTION private.lifeos_integration_secret_name(text,text,text,text)")
        _tenant_functions(LEGACY_PROVIDERS)
    op.drop_table("integration_configurations")
