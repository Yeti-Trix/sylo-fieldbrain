# LogicScout shared data

**Canonical storage:** Postgres (schema v3+). Brain markdown and document file bytes live in the database so every Sylo install sees the same data.

Optional local cache under `shared/storage/` is not authoritative.

Config: `%USERPROFILE%\.sylo\fieldbrain\database_config.json` (synced from Sylo FieldBrain Settings).
