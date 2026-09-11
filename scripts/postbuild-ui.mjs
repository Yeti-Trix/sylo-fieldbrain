import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dest = path.join(root, 'skills/fieldbrain/routes/fieldbrain/fallback.md')
const src = path.join(root, 'ui/fallback.md')

if (fs.existsSync(src)) {
  fs.mkdirSync(path.dirname(dest), { recursive: true })
  fs.copyFileSync(src, dest)
  console.log('[sylo-fieldbrain] copied ui/fallback.md →', dest)
}
