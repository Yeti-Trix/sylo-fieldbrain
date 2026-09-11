/**
 * FieldBrain — shared shop knowledge (projects, docs, brains, search). Field notes are brain entries.
 */
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent'
import { Type } from 'typebox'

import { runPythonScript } from './python-runner.js'

export function registerFieldBrainTools(pi: ExtensionAPI): void {
  pi.registerTool({
    name: 'fieldbrain_status',
    label: 'FieldBrain status',
    description:
      'Package paths, Postgres config location, and Ollama endpoint hint. Run before other FieldBrain tools.',
    parameters: Type.Object({}),
    async execute() {
      return runPythonScript('status.py', [])
    },
  })

  pi.registerTool({
    name: 'fieldbrain_db_check',
    label: 'FieldBrain database check',
    description:
      'Verify Postgres connection, pgvector extension, and schema version. Use --guided in script for setup steps when failing.',
    parameters: Type.Object({
      guided: Type.Optional(
        Type.Boolean({ description: 'Include guided setup steps when a check fails' }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args: string[] = []
      if (params.guided === true) args.push('--guided')
      return runPythonScript('db_check.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_db_bootstrap',
    label: 'FieldBrain create database',
    description:
      'One-time setup: connect as Postgres superuser, create the FieldBrain role + database, enable pgvector if installed, and migrate. Superuser password is not stored.',
    parameters: Type.Object({
      admin_username: Type.Optional(
        Type.String({ description: 'Postgres superuser (default postgres)' }),
      ),
      admin_password: Type.String({ description: 'Postgres superuser password (not saved)' }),
      host: Type.Optional(Type.String({ description: 'Postgres host (default localhost)' })),
      port: Type.Optional(Type.Integer({ description: 'Postgres port (default 5432)' })),
      app_database: Type.Optional(Type.String({ description: 'Database name to create (default fieldbrain)' })),
      app_username: Type.Optional(Type.String({ description: 'App role name (default fieldbrain)' })),
      app_password: Type.Optional(
        Type.String({ description: 'Password for the FieldBrain role (default fieldbrain)' }),
      ),
      skip_migrate: Type.Optional(Type.Boolean({ description: 'Create role/DB only; do not run migrations' })),
    }),
    async execute(_toolCallId, params) {
      const args = [
        '--admin-user',
        params.admin_username?.trim() || 'postgres',
        '--admin-password',
        params.admin_password,
      ]
      if (params.host) args.push('--host', params.host)
      if (params.port != null) args.push('--port', String(params.port))
      if (params.app_database) args.push('--app-database', params.app_database)
      if (params.app_username) args.push('--app-username', params.app_username)
      if (params.app_password) args.push('--app-password', params.app_password)
      if (params.skip_migrate === true) args.push('--skip-migrate')
      return runPythonScript('db_bootstrap.py', args, 180_000)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_db_migrate',
    label: 'FieldBrain database migrate',
    description:
      'Apply Alembic migrations to the configured Postgres database. Run once on the server DB before clients connect.',
    parameters: Type.Object({
      check_only: Type.Optional(Type.Boolean({ description: 'Report version without migrating' })),
    }),
    async execute(_toolCallId, params) {
      const args: string[] = []
      if (params.check_only === true) args.push('--check-only')
      return runPythonScript('db_migrate.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_pgvector_guide',
    label: 'FieldBrain pgvector setup guide',
    description: 'Plain-language Windows steps for optional semantic search (pgvector).',
    parameters: Type.Object({}),
    async execute() {
      return runPythonScript('pgvector_guide.py', [])
    },
  })

  pi.registerTool({
    name: 'fieldbrain_pgvector_install',
    label: 'FieldBrain install pgvector from folder',
    description:
      'Copy pgvector files from an operator-selected folder or zip into local PostgreSQL, then enable the extension. Superuser password is not stored.',
    parameters: Type.Object({
      source_path: Type.String({ description: 'Folder or .zip with pgvector files (local Postgres only)' }),
      admin_username: Type.Optional(Type.String()),
      admin_password: Type.String({ description: 'Postgres superuser password (not saved)' }),
      host: Type.Optional(Type.String()),
      port: Type.Optional(Type.Integer()),
      database: Type.Optional(Type.String()),
      skip_file_copy: Type.Optional(
        Type.Boolean({ description: 'Only CREATE EXTENSION on remote/server Postgres' }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args = [
        '--admin-password',
        params.admin_password,
      ]
      if (params.admin_username) args.push('--admin-user', params.admin_username)
      if (params.host) args.push('--host', params.host)
      if (params.port != null) args.push('--port', String(params.port))
      if (params.database) args.push('--database', params.database)
      if (params.skip_file_copy === true) args.push('--skip-file-copy')
      else if (params.source_path) args.push('--source', params.source_path)
      return runPythonScript('pgvector_install_from_folder.py', args, 180_000)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_project_list',
    label: 'FieldBrain list projects',
    description:
      'List shared projects. Always run before create. Pass with_stats for brain/doc counts per project.',
    parameters: Type.Object({
      include_hidden: Type.Optional(
        Type.Boolean({ description: 'Include system-hidden projects (e.g. global brain shell)' }),
      ),
      with_stats: Type.Optional(
        Type.Boolean({ description: 'Include brain and library doc counts' }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args: string[] = []
      if (params.include_hidden === true) args.push('--include-hidden')
      if (params.with_stats === true) args.push('--with-stats')
      return runPythonScript('fieldbrain_project_list.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_project_create',
    label: 'FieldBrain create project',
    description:
      'Manually create a project: name 12345 (job) or 12345-001 (sub-project). Duplicate names rejected. List first.',
    parameters: Type.Object({
      name: Type.String({ description: '12345 for job-level, or 12345-001 for sub-project' }),
      org_id: Type.Optional(Type.String({ description: 'Org id (default: default)' })),
      tags: Type.Optional(
        Type.Array(Type.String(), { description: 'Optional project tag strings' }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args = ['--name', params.name]
      if (params.org_id) args.push('--org-id', params.org_id)
      if (params.tags && params.tags.length > 0) {
        args.push('--tags-json', JSON.stringify(params.tags))
      }
      return runPythonScript('fieldbrain_project_create.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_log_search',
    label: 'FieldBrain search legacy maintenance logs',
    description:
      'Legacy read-only: search old maintenance log rows from before field notes moved to brain entries. For new notes use fieldbrain_brain_write; for current search use fieldbrain_search.',
    parameters: Type.Object({
      query: Type.Optional(Type.String({ description: 'Full-text search across title, body, fault, tag' })),
      project_id: Type.Optional(Type.Integer({ description: 'Filter by project id' })),
      fault_code: Type.Optional(Type.String({ description: 'Filter by fault code' })),
      equipment_tag: Type.Optional(Type.String({ description: 'Filter by equipment tag substring' })),
      limit: Type.Optional(Type.Integer({ description: 'Max results (default 25)' })),
    }),
    async execute(_toolCallId, params) {
      const args: string[] = []
      if (params.query) args.push('--query', params.query)
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.fault_code) args.push('--fault-code', params.fault_code)
      if (params.equipment_tag) args.push('--equipment-tag', params.equipment_tag)
      if (params.limit != null) args.push('--limit', String(params.limit))
      return runPythonScript('fieldbrain_log_search.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_document_list',
    label: 'FieldBrain list documents',
    description: 'List global library documents or documents attached to a project.',
    parameters: Type.Object({
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'global library or project-attached docs (default global)',
        }),
      ),
      project_id: Type.Optional(Type.Integer({ description: 'Required when scope=project' })),
      category: Type.Optional(Type.String({ description: 'Filter global docs by category' })),
      search: Type.Optional(Type.String({ description: 'Filter global docs by title/filename' })),
      limit: Type.Optional(Type.Integer({ description: 'Max global results (default 200)' })),
    }),
    async execute(_toolCallId, params) {
      const args = ['--scope', params.scope ?? 'global']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.category) args.push('--category', params.category)
      if (params.search) args.push('--search', params.search)
      if (params.limit != null) args.push('--limit', String(params.limit))
      return runPythonScript('fieldbrain_document_list.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_document_attach',
    label: 'FieldBrain attach or register document',
    description:
      'Register file bytes in the library (PDF, DOCX, XLSX, TXT, MD, CSV, images) or attach an existing document to a project. Does not index for search — follow with fieldbrain_document_catalog after reading the file.',
    parameters: Type.Object({
      document_id: Type.Optional(Type.Integer({ description: 'Existing document id to attach' })),
      file_path: Type.Optional(Type.String({ description: 'New file path to register and optionally link' })),
      project_id: Type.Optional(Type.Integer({ description: 'Target project (required for attach)' })),
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'Scope when registering a new file (default project)',
        }),
      ),
      title: Type.Optional(Type.String({ description: 'Optional title when registering a file' })),
      role: Type.Optional(Type.String({ description: 'Link role: reference or schematic' })),
    }),
    async execute(_toolCallId, params) {
      const args: string[] = []
      if (params.document_id != null) args.push('--document-id', String(params.document_id))
      if (params.file_path) args.push('--file-path', params.file_path)
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.scope) args.push('--scope', params.scope)
      if (params.title) args.push('--title', params.title)
      if (params.role) args.push('--role', params.role)
      return runPythonScript('fieldbrain_document_attach.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_document_promote',
    label: 'FieldBrain promote document to global library',
    description:
      'Promote a project-local document to the global library so it appears in global search. The project link is kept. Confirm with operator before promoting.',
    parameters: Type.Object({
      document_id: Type.Integer({ description: 'Project-local document id to promote' }),
    }),
    async execute(_toolCallId, params) {
      return runPythonScript('fieldbrain_document_promote.py', [
        '--document-id',
        String(params.document_id),
      ])
    },
  })

  pi.registerTool({
    name: 'fieldbrain_brain_read',
    label: 'FieldBrain read brain',
    description: 'Read markdown from a project or global brain library.',
    parameters: Type.Object({
      path: Type.String({ description: 'Relative brain path, e.g. gotchas/conveyor_jam.md' }),
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'global org brain or project brain (default project)',
        }),
      ),
      project_id: Type.Optional(Type.Integer({ description: 'Required when scope=project' })),
    }),
    async execute(_toolCallId, params) {
      const args = ['--path', params.path, '--scope', params.scope ?? 'project']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      return runPythonScript('fieldbrain_brain_read.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_brain_write',
    label: 'FieldBrain write brain',
    description:
      'Write or append brain markdown. scope=project requires confirmed project_id — ask operator if unclear.',
    parameters: Type.Object({
      path: Type.String({ description: 'Relative brain path, e.g. gotchas/conveyor_jam.md' }),
      content: Type.String({ description: 'Markdown content' }),
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'global org brain or project brain (default project)',
        }),
      ),
      project_id: Type.Optional(Type.Integer({ description: 'Required when scope=project' })),
      mode: Type.Optional(
        Type.Union([Type.Literal('replace'), Type.Literal('append')], {
          description: 'replace entire file or append (default replace)',
        }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args = [
        '--path',
        params.path,
        '--content',
        params.content,
        '--scope',
        params.scope ?? 'project',
        '--mode',
        params.mode ?? 'replace',
      ]
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      return runPythonScript('fieldbrain_brain_write.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_brain_delete',
    label: 'FieldBrain soft-delete brain doc',
    description: 'Soft-delete a brain markdown document (revision saved; use fieldbrain_brain_restore).',
    parameters: Type.Object({
      path: Type.String({ description: 'Relative brain path' }),
      scope: Type.Optional(Type.Union([Type.Literal('global'), Type.Literal('project')])),
      project_id: Type.Optional(Type.Integer()),
    }),
    async execute(_toolCallId, params) {
      const args = ['--path', params.path, '--scope', params.scope ?? 'project']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      return runPythonScript('fieldbrain_brain_delete.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_brain_restore',
    label: 'FieldBrain restore brain doc',
    description: 'Restore a soft-deleted brain markdown document.',
    parameters: Type.Object({
      path: Type.String({ description: 'Relative brain path' }),
      scope: Type.Optional(Type.Union([Type.Literal('global'), Type.Literal('project')])),
      project_id: Type.Optional(Type.Integer()),
    }),
    async execute(_toolCallId, params) {
      const args = ['--path', params.path, '--scope', params.scope ?? 'project']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      return runPythonScript('fieldbrain_brain_restore.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_brain_revisions',
    label: 'FieldBrain brain revisions',
    description: 'List revision history for a brain markdown document.',
    parameters: Type.Object({
      path: Type.String({ description: 'Relative brain path' }),
      scope: Type.Optional(Type.Union([Type.Literal('global'), Type.Literal('project')])),
      project_id: Type.Optional(Type.Integer()),
      limit: Type.Optional(Type.Integer({ description: 'Max revisions (default 20)' })),
    }),
    async execute(_toolCallId, params) {
      const args = ['--path', params.path, '--scope', params.scope ?? 'project']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.limit != null) args.push('--limit', String(params.limit))
      return runPythonScript('fieldbrain_brain_revisions.py', args)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_document_catalog',
    label: 'FieldBrain catalog document',
    description:
      'After you read a file with the matching Sylo reader (pdf-reader, docx, spreadsheet, read, vision), write catalog metadata and index the summary for search. Supports PDF, DOCX, XLSX, TXT, MD, CSV, images. Does not full-text ingest the file.',
    parameters: Type.Object({
      document_id: Type.Optional(
        Type.Integer({ description: 'Existing library document id (use this OR file_path)' }),
      ),
      file_path: Type.Optional(
        Type.String({
          description: 'Register file into library first, then catalog (use this OR document_id)',
        }),
      ),
      description: Type.String({
        description:
          'Your catalog summary: what this file is, key topics, when to open it (required)',
      }),
      title: Type.Optional(Type.String({ description: 'Display title override' })),
      category: Type.Optional(
        Type.String({
          description:
            'manual | datasheet | requirements | email | howto | guide | schematic | spreadsheet | image | markdown | reference | other',
        }),
      ),
      tags: Type.Optional(
        Type.String({ description: 'Comma-separated tags or JSON array string' }),
      ),
      manufacturer: Type.Optional(Type.String()),
      model: Type.Optional(Type.String()),
      version: Type.Optional(Type.String()),
      outline_json: Type.Optional(
        Type.String({
          description:
            'Optional JSON array of outline rows: [{ "level": 1, "title": "Section", "page": 0 }]',
        }),
      ),
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'When using file_path (default global)',
        }),
      ),
      project_id: Type.Optional(
        Type.Integer({ description: 'Project id when scope=project or attaching to project' }),
      ),
    }),
    async execute(_toolCallId, params) {
      if (params.document_id == null && !params.file_path?.trim()) {
        return {
          content: [{ type: 'text', text: 'Provide document_id or file_path.' }],
          details: { ok: false },
        }
      }
      if (params.document_id != null && params.file_path?.trim()) {
        return {
          content: [{ type: 'text', text: 'Provide only one of document_id or file_path.' }],
          details: { ok: false },
        }
      }
      const args = ['--description', params.description]
      if (params.document_id != null) args.push('--document-id', String(params.document_id))
      if (params.file_path?.trim()) args.push('--file-path', params.file_path.trim())
      if (params.title) args.push('--title', params.title)
      if (params.category) args.push('--category', params.category)
      if (params.tags) args.push('--tags', params.tags)
      if (params.manufacturer) args.push('--manufacturer', params.manufacturer)
      if (params.model) args.push('--model', params.model)
      if (params.version) args.push('--version', params.version)
      if (params.outline_json) args.push('--outline-json', params.outline_json)
      if (params.scope) args.push('--scope', params.scope)
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      return runPythonScript('fieldbrain_document_catalog.py', args, 120_000)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_document_ingest',
    label: 'FieldBrain ingest document (legacy)',
    description:
      'Legacy: pymupdf full-text extract + chunk index. Prefer attach → read with Sylo readers → fieldbrain_document_catalog for PDF/DOCX/XLSX/images.',
    parameters: Type.Object({
      file_path: Type.String({ description: 'Path to PDF or .txt on disk' }),
      scope: Type.Optional(
        Type.Union([Type.Literal('global'), Type.Literal('project')], {
          description: 'global library or project-local (default project)',
        }),
      ),
      project_id: Type.Optional(Type.Integer({ description: 'Required when scope=project' })),
      title: Type.Optional(Type.String({ description: 'Optional document title' })),
    }),
    async execute(_toolCallId, params) {
      const args = ['--file-path', params.file_path, '--scope', params.scope ?? 'project']
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.title) args.push('--title', params.title)
      return runPythonScript('fieldbrain_document_ingest.py', args, 300_000)
    },
  })

  pi.registerTool({
    name: 'fieldbrain_search',
    label: 'FieldBrain hybrid search',
    description:
      'Hybrid keyword + semantic search. With project_id: that project PLUS the curated global library/brain. Without project_id: global only — project-local knowledge stays invisible until promoted.',
    parameters: Type.Object({
      project_id: Type.Optional(
        Type.Integer({
          description: 'Project to search (includes global). Omit for global-only search.',
        }),
      ),
      query: Type.String({ description: 'Search query text' }),
      limit: Type.Optional(Type.Integer({ description: 'Max results (default 25)' })),
      source_type: Type.Optional(
        Type.String({ description: 'Optional filter: document, brain, tag, rung, etc.' }),
      ),
    }),
    async execute(_toolCallId, params) {
      const args = ['--query', params.query]
      if (params.project_id != null) args.push('--project-id', String(params.project_id))
      if (params.limit != null) args.push('--limit', String(params.limit))
      if (params.source_type) args.push('--source-type', params.source_type)
      return runPythonScript('fieldbrain_search.py', args)
    },
  })
}
