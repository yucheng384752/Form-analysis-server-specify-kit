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

describe('no hardcoded backend base URL', () => {
  it('does not hardcode http://localhost:8000/api in src', async () => {
    const thisFile = fileURLToPath(import.meta.url)
    const srcDir = path.resolve(path.dirname(thisFile), '..') // frontend/src

    const files = await walk(srcDir)

    const offenders: Array<{ file: string; needle: string }> = []
    const needles = ['http://localhost:8000/api', 'http://backend:8000/api']

    for (const f of files) {
      const content = await readFile(f, 'utf-8')
      for (const needle of needles) {
        if (content.includes(needle)) {
          offenders.push({ file: path.relative(srcDir, f), needle })
        }
      }
    }

    expect(offenders).toEqual([])
  })
})
