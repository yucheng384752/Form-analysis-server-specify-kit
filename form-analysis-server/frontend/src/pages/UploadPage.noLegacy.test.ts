import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

describe('UploadPage legacy endpoint guard', () => {
  it('does not call legacy CSV import endpoints (/api/import, /api/upload/* except /pdf)', () => {
    const source = fs.readFileSync(path.join(process.cwd(), 'src/pages/UploadPage.tsx'), 'utf-8');

    // Legacy CSV import pipeline endpoints (deprecated / blocked in multi-tenant)
    expect(source).not.toMatch(/\/api\/import\b/);

    // Allow PDF pipeline endpoints under /api/upload/pdf*, but disallow everything else under /api/upload
    expect(source).not.toMatch(/\/api\/upload(?!\/pdf)/);
  });
});
