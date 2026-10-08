"""Allow backend fixture execution to read its fixed installation Vault secret."""
from alembic import op

revision = "0033_fixture_runtime_secret"
down_revision = "0032_daily_fixture_cadence"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE FUNCTION private.get_lifeos_fixture_installation_secret()
        RETURNS text LANGUAGE sql SECURITY DEFINER
        SET search_path = pg_catalog, vault AS $$
            SELECT decrypted_secret FROM vault.decrypted_secrets
            WHERE name = 'lifeos:installation:api-football' LIMIT 1;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION private.get_lifeos_fixture_installation_secret() FROM PUBLIC, anon, authenticated, service_role")
    op.execute("GRANT EXECUTE ON FUNCTION private.get_lifeos_fixture_installation_secret() TO CURRENT_USER")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS private.get_lifeos_fixture_installation_secret()")
