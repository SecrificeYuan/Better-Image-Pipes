import { defineConfig } from '@playwright/test'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export default defineConfig({
  testDir: './e2e',
  outputDir: join(tmpdir(), 'better-image-pipes-browser-results'),
  workers: 1,
  timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:5190', viewport: { width: 1600, height: 1000 },
    trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: [
    { command: 'uv run --project ../backend python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8120',
      url: 'http://127.0.0.1:8120/api/nodes', timeout: 120000,
      env: { IMAGE_PIPES_DATA_DIR: join(tmpdir(), 'better-image-pipes-browser-data') } },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5190',
      url: 'http://127.0.0.1:5190', timeout: 120000,
      env: { IMAGE_PIPES_API_PROXY: 'http://127.0.0.1:8120' } },
  ],
})
