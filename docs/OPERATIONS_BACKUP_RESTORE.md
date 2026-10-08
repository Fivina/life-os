# Backup And Restore

## Backup Strategy

Use Supabase managed backups/snapshots before migrations and production deploys. For local development, use `pg_dump` against the configured PostgreSQL database.

Example local backup:

```powershell
pg_dump "$env:DATABASE_URL" --format=custom --file life-os-backup.dump
```

Do not store backups in the frontend bundle or public repository.

## Restore Rehearsal

Recommended rehearsal:

1. Create a disposable PostgreSQL database.
2. Restore the backup into it.
3. Point a local backend at the disposable database.
4. Run `python -m alembic current`.
5. Smoke test `/api/v1/me`, `/api/v1/export`, current plan, Fitness, Learning, Kitchen, Assistant, and Personal Learning.

The automated v2.0 rehearsal performs this safely with synthetic data in two uniquely named disposable databases:

```powershell
cd backend
$env:POSTGRES_BIN = 'C:\Program Files\PostgreSQL\17\bin'
.\.venv\Scripts\python.exe ..\scripts\verify_backup_restore.py --artifact-dir E:\LifeOSBuild\release-smoke
```

The script migrates and seeds a source database through real Life OS services, creates a custom-format `pg_dump`, restores it with `pg_restore`, checks the Alembic revision and canonical row/revision integrity, starts the application against the restored database, removes the temporary dump, and drops only database names matching its strict disposable-name pattern. The PostgreSQL client major version must be at least the server major version.

## Current Status

The v2.0 release gate includes an automated full logical backup/restore rehearsal against the configured PostgreSQL server. Managed Supabase snapshots remain the preferred production backup and must still be checked in the Supabase project before deployment.

## Recovery Notes

Prefer application rollback before database downgrade. Database downgrade should only be used after a safe rehearsal for the exact revision pair.
