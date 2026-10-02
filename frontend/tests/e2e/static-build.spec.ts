/**
 * The static build (card 7.1, N7): serves the built `dist/` the way GitHub Pages does (a real file, else 404.html with
 * status 404) and opens a deep link with no backend. It runs only when asked, because `npm run build` (no mock) also
 * writes dist/ and that build needs a backend: build with `VITE_FEATURES=n1_miniapp npm run build -- --mode mock`, then
 * run `STATIC_DIR=dist npx playwright test --project=mock static-build`. `STATIC_DIR` names the static build output.
 */
import { expect, test } from '@playwright/test'
import { existsSync, readFileSync, statSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import { extname, join, normalize } from 'node:path'

const DIST = process.env.STATIC_DIR ?? ''
const TYPES: Record<string, string> = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.woff2': 'font/woff2', '.png': 'image/png' }

test.skip(DIST === '' || !existsSync(join(DIST, '404.html')), 'no static build named: set STATIC_DIR to the output of npm run build -- --mode mock')

let server: Server
let base = ''

test.beforeAll(async () => {
  server = createServer((req, res) => {
    const path = normalize(decodeURIComponent((req.url ?? '/').split('?')[0])).replace(/^(\.\.[/\\])+/, '')
    const file = join(DIST, path)
    if (existsSync(file) && statSync(file).isFile()) {
      res.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream' }).end(readFileSync(file))
      return
    }
    res.writeHead(404, { 'content-type': 'text/html' }).end(readFileSync(join(DIST, '404.html')))
  })
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const address = server.address()
  base = typeof address === 'object' && address ? `http://127.0.0.1:${address.port}` : ''
})

test.afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()))
})

test('a deep link opens through the 404 fallback and the console runs on the in-browser mock', async ({ page }) => {
  const apiCalls: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiCalls.push(request.url())
  })
  const response = await page.goto(`${base}/claims?lang=en`)
  expect(response?.status()).toBe(404)
  await expect(page.locator('.app')).toBeVisible()
  await expect(page.getByRole('heading', { name: /claims/i }).first()).toBeVisible()
  expect(apiCalls).toEqual([])
})
