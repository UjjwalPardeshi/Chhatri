// @vitest-environment node
/**
 * Build-output checks (design system 13.6, AC-05 and AC-06 of fs-04). Builds the one Tailwind entry with Vite and
 * reads the CSS that ships. miniapp.css excludes test files from class detection; the words that are Tailwind utility
 * names are still assembled from parts here, so the guard holds even if that exclusion is ever dropped.
 */
import tailwindcss from '@tailwindcss/vite'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { build, type Rollup } from 'vite'
import { beforeAll, describe, expect, it } from 'vitest'

const SRC = fileURLToPath(new URL('..', import.meta.url))
const ENTRY = '\0miniapp-css-probe'
const word = (...parts: string[]) => parts.join('')
const COLLIDING = [word('tab', 'le'), word('car', 'd'), word('bt', 'n'), word('bad', 'ge')] // console class names that a utility could shadow
let css = ''

function filesUnder(dir: string, extension: RegExp): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? filesUnder(path, extension) : extension.test(name) ? [path] : []
  })
}

function consoleFiles(extension: RegExp): string[] {
  return filesUnder(SRC, extension).filter((path) => !path.startsWith(join(SRC, 'miniapp')) && !/\.test\./.test(path))
}

function cssOf(result: Rollup.RollupOutput | Rollup.RollupOutput[]): string {
  return (Array.isArray(result) ? result : [result])
    .flatMap((output) => output.output)
    .filter((chunk): chunk is Rollup.OutputAsset => chunk.type === 'asset' && chunk.fileName.endsWith('.css'))
    .map((asset) => String(asset.source))
    .join('\n')
}

beforeAll(async () => {
  const result = await build({
    root: join(SRC, '..'),
    configFile: false,
    logLevel: 'silent',
    plugins: [
      tailwindcss(),
      {
        name: 'miniapp-css-entry',
        resolveId: (id) => (id === ENTRY ? ENTRY : null),
        load: (id) => (id === ENTRY ? "import '/src/miniapp/miniapp.css'" : null),
      },
    ],
    build: { write: false, rollupOptions: { input: ENTRY } },
  })
  css = cssOf(result as Rollup.RollupOutput | Rollup.RollupOutput[])
}, 60_000)

const escapeClass = (name: string) => name.replace(/[^A-Za-z0-9_-]/g, (char) => `\\${char}`)
function classTokens(paths: string[]): Set<string> {
  const literals = paths.flatMap((path) => [...readFileSync(path, 'utf8').matchAll(/className=["'`{][^"'`}]*["'`}]/g)])
  return new Set(literals.flatMap((match) => match[0].split(/["'`{}=\s]+/)))
}
const declaredNames = (source: string, pattern: RegExp) => new Set([...source.matchAll(pattern)].map((m) => m[1] ?? ''))

describe('built mini-app CSS', () => {
  it('is produced, with the scoped base and a utility from the theme mapping', () => {
    expect(css).toContain(':where(.miniapp)')
    expect(css).toContain('.bg-primary')
  })

  it('has no Preflight rule and nothing on html or body', () => {
    expect(css).not.toContain('-webkit-text-size-adjust')
    expect(css).not.toContain('::-webkit-calendar-picker-indicator')
    expect(css).not.toMatch(/(^|[}\s,])(html|body)[\s,{]/)
  })

  it('has no utility with !important (a layered one would beat the console reduced-motion rule)', () => {
    expect(css.match(/[^{}]*\{[^{}]*!important[^{}]*\}/g)).toEqual([':where(.miniapp) [hidden]{display:none!important}'])
  })

  it('emits no class that the console also defines', () => {
    const consoleClasses = new Set<string>()
    for (const path of consoleFiles(/\.css$/)) {
      for (const name of declaredNames(readFileSync(path, 'utf8'), /\.([A-Za-z_][\w-]*)/g)) consoleClasses.add(name)
    }
    for (const name of COLLIDING) expect(consoleClasses.has(name)).toBe(true) // the list is still true
    const emitted = [...consoleClasses].filter((name) => new RegExp(`\\.${escapeClass(name)}(?![\\w-])`).test(css))
    expect(emitted).toEqual([])
  })

  it('emits no keyframes with a name the console defines', () => {
    const consoleFrames = new Set<string>()
    for (const path of consoleFiles(/\.css$/)) {
      for (const name of declaredNames(readFileSync(path, 'utf8'), /@keyframes\s+([\w-]+)/g)) consoleFrames.add(name)
    }
    const emitted = [...declaredNames(css, /@keyframes\s+([\w-]+)/g)]
    expect(emitted.length).toBeGreaterThan(0)
    expect(emitted.filter((name) => consoleFrames.has(name))).toEqual([])
  })

  it('declares no custom property that the console :root also declares', () => {
    const consoleVars = declaredNames(readFileSync(join(SRC, 'styles/tokens.css'), 'utf8'), /(--[\w-]+)\s*:/g)
    const builtVars = declaredNames(css, /(--[\w-]+)\s*:/g)
    const shared = [...builtVars].filter((name) => consoleVars.has(name) && !name.startsWith('--tw-'))
    expect(shared).toEqual([])
  })

  it('detects classes in src/miniapp only: a class that console code alone uses is absent', () => {
    const inMiniapp = classTokens(filesUnder(join(SRC, 'miniapp'), /\.tsx$/))
    const consoleOnly = [...classTokens(consoleFiles(/\.tsx$/))].filter(
      (name) => /^[a-z][a-z0-9-]*$/.test(name) && !inMiniapp.has(name),
    )
    expect(consoleOnly.length).toBeGreaterThan(0)
    expect(consoleOnly.filter((name) => new RegExp(`\\.${escapeClass(name)}\\{`).test(css))).toEqual([])
  })
})
