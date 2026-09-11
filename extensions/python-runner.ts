import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const execFileAsync = promisify(execFile)

export const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const SCRIPTS_DIR = path.join(PACKAGE_ROOT, 'scripts')

export type ToolContentBlock = { type: 'text'; text: string }

function resolvePython(): { command: string; prefixArgs: string[] } {
  const envPython = process.env.SYLO_PYTHON?.trim()
  if (envPython) {
    return { command: envPython, prefixArgs: [] }
  }
  return { command: process.platform === 'win32' ? 'python' : 'python3', prefixArgs: [] }
}

export function toolError(text: string): { content: ToolContentBlock[] } {
  return { content: [{ type: 'text', text }] }
}

export async function runPythonScript(
  scriptName: string,
  args: string[] = [],
  timeoutMs = 120_000,
): Promise<{ content: ToolContentBlock[] }> {
  const scriptPath = path.join(SCRIPTS_DIR, scriptName)
  const { command, prefixArgs } = resolvePython()
  try {
    const { stdout, stderr } = await execFileAsync(command, [...prefixArgs, scriptPath, ...args], {
      cwd: PACKAGE_ROOT,
      maxBuffer: 8 * 1024 * 1024,
      windowsHide: true,
      timeout: timeoutMs,
      env: { ...process.env },
    })
    const trimmed = stdout.trim()
    if (!trimmed) {
      return toolError(stderr.trim() || `${scriptName} produced no output`)
    }
    const parsed = JSON.parse(trimmed) as { ok?: boolean; error?: string; operator_chat?: string }
    if (parsed.ok === false) {
      return toolError(parsed.error ?? `${scriptName} failed`)
    }
    if (typeof parsed.operator_chat === 'string' && parsed.operator_chat.trim()) {
      return { content: [{ type: 'text', text: parsed.operator_chat.trim() }] }
    }
    return { content: [{ type: 'text', text: trimmed }] }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return toolError(message)
  }
}
