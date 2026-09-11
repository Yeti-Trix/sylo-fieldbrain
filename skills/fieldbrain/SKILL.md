---
name: fieldbrain
description: FieldBrain — shared shop knowledge (projects, document/brain libraries, hybrid search). Field notes and fault history live in brains. Requires sylo-fieldbrain.
metadata:
  sylo:
    category: domain
    icon: brain
routes:
  - id: fieldbrain
    title: FieldBrain
    icon: brain
    nav_section: domain
    entry: routes/fieldbrain/index.html
    fallback: routes/fieldbrain/fallback.md
route_protocol_version: 0
---

# FieldBrain

Shared shop knowledge inside Sylo: projects, document library, brain markdown, hybrid search. Field notes, faults, and fixes are **brain entries** (no separate log system). Works for PLC shops, manufacturing, or any domain where the team needs durable field notes in Postgres.

**Dashboard:** React + TypeScript route (`ui/` → Vite build), same pattern as Health and Think Tank.

**Tracker:** `features_tracker/active/2026-07-04_14-56-00_sylo_fieldbrain_package_migration.md`

## Prerequisites

1. **sylo-fieldbrain** optional package enabled (Capability manager).
2. **PostgreSQL** reachable (local server or LAN address in settings / `~/.sylo/fieldbrain/database_config.json`).
3. **pgvector** on that Postgres server (semantic search; guided setup if missing).
4. **Ollama** for embeddings (default `http://127.0.0.1:11434`).

## First run

1. `fieldbrain_status` — confirm package + config paths.
2. `fieldbrain_db_migrate` — only if auto-migrate on startup did not run (offline DB, etc.).
3. `fieldbrain_db_check` — verify connection, pgvector, schema version on every install.

## Document library — catalog flow (primary)

**Do not** run Marker/OCR or `fieldbrain_document_ingest` for normal library work. Search indexes a **catalog summary**, not every page of every PDF.

### Flow

1. **Attach** — `fieldbrain_document_attach` or `fieldbrain_document_catalog` with `file_path` registers bytes in Postgres (global shop library or project-local).
2. **Read** — use the matching Sylo skill on the same path (operator attachment or cached copy under `~/.sylo/fieldbrain/storage/documents/`).
3. **Catalog** — `fieldbrain_document_catalog` with your summary, category, tags, optional outline (TOC / sheet tabs / email thread subjects).
4. **Search** — `fieldbrain_search` finds the doc by summary; open the source file with the reader when you need detail.

### Supported file types (library)

| Extension | Read with | Typical category |
|-----------|-----------|------------------|
| `.pdf` | **sylo-pdf-reader** (`search_schematic_pdf`, region tools) | manual, datasheet, schematic |
| `.xlsx`, `.xlsm`, `.ods` | **sylo-spreadsheet** (`read_spreadsheet`) | spreadsheet, requirements |
| `.csv` | Pi **`read`** | spreadsheet, requirements |
| `.txt`, `.md` | Pi **`read`** | howto, guide, email (exported), markdown |
| `.docx` | **sylo-docx** (`read_docx`; `extract_docx_images` for embedded pictures; `render_docx` to create) | manual, requirements |
| `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp` | Vision on attachment — describe panels, labels, wiring | image |

Email chains: save as `.txt` / `.md` / `.eml` export, attach, read, catalog. Raw `.msg` not supported yet.

### Catalog tool fields

- **`description`** (required) — what it is, equipment, when to open it, key fault codes or part numbers if relevant.
- **`category`** — `manual`, `datasheet`, `requirements`, `email`, `howto`, `guide`, `schematic`, `spreadsheet`, `image`, `markdown`, `reference`, `other`.
- **`tags`** — comma-separated or JSON array (vendor, product line, machine name).
- **`outline_json`** — optional TOC or section list: `[{"level":1,"title":"Safety","page":12}]` (`page` is 0-based for PDFs).
- **`manufacturer`**, **`model`**, **`version`** — when known.

### Images (library + brains)

- Store photos/diagrams in the **global library** (`scope=global`) with `category=image` and a vision-written `description`.
- In **brain** markdown, reference the file path or note `document #id` in prose; embed `![caption](path)` when the image lives on disk the operator can open.
- Do not duplicate heavy binaries inside brain bodies; attach once, catalog once, link in brains.

## Tools

| Tool | When |
|------|------|
| `fieldbrain_status` | Start — paths and config |
| `fieldbrain_db_bootstrap` | One-time: create role + database (superuser), pgvector, migrate |
| `fieldbrain_db_migrate` | Apply Alembic migrations |
| `fieldbrain_db_check` | After migrate; repeat when connection fails |
| `fieldbrain_project_list` | List shared projects |
| `fieldbrain_project_create` | Create a new project (+ brain scaffold) |
| `fieldbrain_log_*` | **Legacy — do not use.** Field notes are brain entries now (see below). Read old rows with `fieldbrain_log_search` only if asked about pre-migration history. |
| `fieldbrain_document_list` | List global library or project documents |
| `fieldbrain_document_attach` | Register file bytes only (no search index) |
| `fieldbrain_document_catalog` | **Primary** — summary + tags + outline → search index |
| `fieldbrain_document_promote` | Promote project-local doc to global library (confirm with operator) |
| `fieldbrain_document_ingest` | Legacy full PDF/text chunk ingest (avoid for new docs) |
| `fieldbrain_brain_read` | Read brain markdown |
| `fieldbrain_brain_write` | Write or append brain markdown |
| `fieldbrain_brain_delete` | Soft-delete a brain doc |
| `fieldbrain_brain_restore` | Restore a soft-deleted brain doc |
| `fieldbrain_brain_revisions` | List brain doc revisions |
| `fieldbrain_search` | Hybrid keyword + semantic search |

## Field notes are brain entries (no separate log system)

Multiple people run their own Sylo against this shared database (controls engineers, electricians). Detail level varies; **you are the normalization layer**. Whether the operator gives a full writeup or one sentence, produce a consistently structured entry.

### Troubleshooting flow (search first)

1. **Problem reported → search before troubleshooting.** `fieldbrain_search` with the machine's `project_id` (global knowledge is included automatically). Someone may have already fixed this.
2. **Hit found:** surface it — file path, what fixed it last time.
3. **No hit:** troubleshoot with the operator (LogicForge for PLC logic if enabled; docs, observations).
4. **Resolved → write the after-action report** to the project brain. Offer this proactively when the operator says it's fixed; don't wait to be asked.

### After-action report (AAR)

New incident: `issues/YYYY-MM-DD_<slug>.md` via `fieldbrain_brain_write`. Header first, then whatever detail the operator gave:

```markdown
# <one-line symptom>
- date: 2026-07-04
- logged_by: <name — ask once if unknown>
- equipment: <machine/asset, if known>
- fault_code: <code(s), or "none — sequence stall / no fault">
- status: resolved | open

## What happened
## What fixed it
```

Rules:

- **Fault code is optional.** Many incidents are "machine not doing what it's supposed to" with no fault, or only a generic sequence alarm. Never invent a code; write the symptom instead.
- **Terse input is fine.** "Fault X, machine stops, sensor came loose" becomes a short but complete AAR. Do not pad or ask more than one clarifying question.
- **Same issue again:** append to the existing file (`mode=append`) instead of creating a duplicate — search `issues/` first.
- **Quick capture, no resolution yet:** `inbox/<slug>.md`; distill later.
- **Recurring pattern:** distill into `gotchas/` (project) or global brain if reusable across machines.
- **Procedures:** `runbooks/`.

One file per incident keeps concurrent writers from colliding. Brain docs are versioned and soft-deleted like logs were, and `fieldbrain_search` indexes them; the consistent header keeps fault codes and equipment findable regardless of who logged it.

## Scopes and search visibility (asymmetric)

Documents and brains have two scopes: **project** and **global**. Search visibility is one-way:

- **`fieldbrain_search` with `project_id`** — searches that project **plus** the global library/brain in one call. Do not run a second global search.
- **`fieldbrain_search` without `project_id`** — global only. Project-local knowledge stays invisible shop-wide until promoted. This is deliberate: one machine's fix can be wrong on another machine.
- Each hit carries `scope: global | project`. When citing a project hit outside its project, say so.

### What goes where

| Content | Scope |
|---------|-------|
| Machine/commissioning issues, machine-specific gotchas, production faults | **Project brain** (that machine's project or sub-project) |
| How-tos, general process steps, anything reusable across machines | **Global brain** |
| Docs for one job only | Project library |
| Manuals, datasheets, vendor docs useful shop-wide | Global library (or promote later) |

### Promotion

- **Documents:** `fieldbrain_document_promote` re-scopes a project-local doc to global (index rows move, embeddings kept, project link stays). Confirm with the operator first.
- **Brains:** no mechanical promote. Project brain notes are context-specific; to make one global, **rewrite it generically** and `fieldbrain_brain_write` to `scope=global`. Ask the operator before doing this.

## Project context before any write

There is **no** default or “active” project in Sylo. The dashboard lists projects and shows `#id`; it does not pick one for chat.

Before **any write** to FieldBrain (brain entry, project-scoped document attach/catalog, project-scoped search target):

1. Run **`fieldbrain_project_list --with-stats`** if you do not already know the ids.
2. If the operator named a job (`12345`) or sub-project (`12345-001`), match it to a row and use that **`project_id`**.
3. If unclear which level (job vs sub-project) or which id, **ask once** before writing: “Log this under project **12345** (#12) or sub-project **12345-001** (#15)?”
4. Do **not** guess, do **not** create a project silently, do **not** assume the last project mentioned in an old turn.

Global library docs (`scope=global`) do not need a project. Everything with `project_id` or `scope=project` does.

## Data split

| Data | Storage |
|------|---------|
| Chats, health, operator prefs | Sylo SQLite (private) |
| Projects, docs, brains | Postgres (shared; content in DB, soft delete + revisions) |

## UI

Dashboard source: `packages/sylo-fieldbrain/ui/` (TypeScript + React, Vite). Built artifacts land in `skills/fieldbrain/routes/fieldbrain/` via `npm run build:ui -w sylo-fieldbrain` (included in `start-sylo.cmd`).

Open **FieldBrain** (Dashboards) for **Projects** (create/list with `#id` and stats), documents, brains, and **Settings** (Postgres + Ollama).

## Projects

Two levels, both are separate rows in Postgres:

| Level | Example | Use for |
|-------|---------|---------|
| **Project** | `12345` | Job-wide notes, shared docs, program-level context |
| **Sub-project** | `12345-001` | Machine / line / unit-specific brains and docs |

Create in the **Projects** tab: project number `12345`, optional sub-project `001`. Or chat: `fieldbrain_project_create` with name `12345` or `12345-001`. Duplicate names rejected. List before creating. Use the `#id` shown in chat; confirm with the operator before logging.

**PLC logic** (L5X export, parse, ladder edits) lives in the **logicforge** skill (`sylo-logicforge` package), not FieldBrain.
