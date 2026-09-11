/**
 * sylo-fieldbrain — shared shop knowledge (projects, docs, brains, maintenance notes).
 *
 * @see features_tracker/active/2026-07-04_14-56-00_sylo_fieldbrain_package_migration.md
 */
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent'

import { registerFieldBrainTools } from './fieldbrain-tools.js'

export default function piSyloFieldBrainExtension(pi: ExtensionAPI): void {
  registerFieldBrainTools(pi)
}
