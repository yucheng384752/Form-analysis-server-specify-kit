import { describe, it, expect } from 'vitest'
import { readdir, readFile } from 'fs/promises'
import path from 'path'
import { fileURLToPath } from 'url'

async function walk(dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  const files: string[] = []

  for (const entry of entries) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      // Exclude test-only sources; we only care about production code paths.
      if (entry.name === 'test' || entry.name === '__tests__') continue
      files.push(...(await walk(full)))
      continue
    }
    if (!entry.isFile()) continue

    if (full.endsWith('.ts') || full.endsWith('.tsx')) {
      // Exclude test files themselves.
      if (full.endsWith('.test.ts') || full.endsWith('.test.tsx') || full.endsWith('.spec.ts') || full.endsWith('.spec.tsx')) {
        continue
      }
      files.push(full)
    }
  }

  return files
}

describe('no legacy import endpoints in production frontend code', () => {
  it('does not reference legacy endpoints (/api/import, /api/upload/* except /pdf) in src', async () => {
    const thisFile = fileURLToPath(import.meta.url)
    const srcDir = path.resolve(path.dirname(thisFile), '..') // frontend/src

    const files = await walk(srcDir)

    const offenders: Array<{ file: string; match: string }> = []

    const legacyImportNeedle = '/api/import'
    const apiUploadNeedle = /\/api\/upload/g

    for (const f of files) {
      const content = await readFile(f, 'utf-8')

      if (content.includes(legacyImportNeedle)) {
        offenders.push({ file: path.relative(srcDir, f), match: legacyImportNeedle })
      }

      for (const match of content.matchAll(apiUploadNeedle)) {
        const index = match.index ?? -1
        if (index < 0) continue

        const allowedPrefix = '/api/upload/pdf'
        if (content.startsWith(allowedPrefix, index)) continue

        offenders.push({ file: path.relative(srcDir, f), match: match[0] })
      }
    }

    expect(offenders).toEqual([])
  })
})
