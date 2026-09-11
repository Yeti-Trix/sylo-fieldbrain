# FieldBrain route unavailable

Enable **sylo-fieldbrain** in Capability manager, then restart Sylo via `start-sylo.cmd`.

Configure Postgres in **FieldBrain → Settings** or `%USERPROFILE%\.sylo\fieldbrain\database_config.json`.

Run `fieldbrain_db_migrate` once on the server database, then `fieldbrain_db_check` on this install.
