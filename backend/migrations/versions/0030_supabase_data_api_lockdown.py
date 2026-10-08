"""Close public-schema data access through Supabase's Data API.

Revision ID: 0030_supabase_data_api_lockdown
Revises: 0029_jev_vault_provider
"""

from alembic import op


revision = "0030_supabase_data_api_lockdown"
down_revision = "0029_jev_vault_provider"
branch_labels = None
depends_on = None


API_ROLES = "PUBLIC, anon, authenticated, service_role"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {API_ROLES}")
    op.execute(f"REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {API_ROLES}")
    op.execute("""
        DO $$
        DECLARE
            target record;
        BEGIN
            FOR target IN
                SELECT c.relname
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p')
                  AND NOT c.relrowsecurity
            LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', target.relname);
            END LOOP;
        END
        $$;
    """)
    op.execute(f"""
        DO $$
        DECLARE
            migration_role name := current_user;
        BEGIN
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TABLES FROM {API_ROLES}',
                migration_role
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {API_ROLES}',
                migration_role
            );
            EXECUTE format(
                'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM {API_ROLES}',
                migration_role
            );
        END
        $$;
    """)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        DO $$
        DECLARE
            target record;
        BEGIN
            FOR target IN
                SELECT c.relname
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relkind IN ('r', 'p')
                  AND c.relrowsecurity
            LOOP
                EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', target.relname);
            END LOOP;
        END
        $$;
    """)
