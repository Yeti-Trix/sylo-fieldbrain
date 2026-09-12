# sylo-fieldbrain

Pi package: **FieldBrain** — shared shop knowledge (projects, docs, brains, maintenance notes, hybrid search).

**Tracker:** `features_tracker/active/2026-07-04_14-56-00_sylo_fieldbrain_package_migration.md`

## Skill

| Skill | Role |
|-------|------|
| **fieldbrain** | Projects, docs, brains, maintenance notes, search, Settings UI |

PLC logic (`.acd` export, L5X parse, ladder edits) lives in **sylo-logicforge** (`logicforge` skill), not FieldBrain.

## Postgres config

Sylo **FieldBrain → Settings** syncs to:

1. `SYLO_FIELDBRAIN_DATABASE_URL` (host env when set)
2. `%USERPROFILE%\.sylo\fieldbrain\database_config.json`
3. Default: `postgresql://fieldbrain:fieldbrain@localhost:5432/fieldbrain`

## UI build

Source: `packages/sylo-fieldbrain/ui/` (React + TypeScript). Built by `npm run build:ui -w sylo-fieldbrain` (runs automatically via `start-sylo.cmd`).

| Tool | Purpose |
|------|---------|
| `fieldbrain_status` | Package paths and config hint |
| `fieldbrain_db_check` | Postgres + pgvector + schema version check |
| `fieldbrain_db_migrate` | Apply Alembic migrations |
| `fieldbrain_search` | Hybrid search over brains, docs, maintenance notes |


## Install

`pi install npm:sylo-fieldbrain` — or from the **Capability manager → Pi.dev package catalog** in Sylo (it appears in the Sylo packages strip).

Releases publish automatically from GitHub Actions (npm trusted publishing, with provenance): bump `version` in `package.json`, commit, tag `vX.Y.Z`, push the tag.
