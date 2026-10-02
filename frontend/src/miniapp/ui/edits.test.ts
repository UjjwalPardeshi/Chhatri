// @vitest-environment node
/** The one-time edits to the generated shadcn files (implementation guide, Wave 0). Source-level, so a re-run of `shadcn add --overwrite` shows up. */
import { readdirSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const dir = new URL('./', import.meta.url)
const files = readdirSync(dir).filter((name) => name.endsWith('.tsx'))
const read = (name: string) => readFileSync(new URL(name, dir), 'utf8')
const all = files.map((name) => [name, read(name)] as const)

describe('generated files after the one-time edits', () => {
  it('has files to check', () => {
    expect(files).toContain('button.tsx')
  })

  it.each(all)('%s uses our cn, no dark: class, no viewport variant, no dead class', (_name, source) => {
    expect(source).not.toMatch(/from "cn"/)
    expect(source).not.toMatch(/"[^"\n]*\bdark:/)
    expect(source).not.toMatch(/"[^"\n]*(^|[\s:])(sm|md|lg|xl|2xl):/)
    expect(source).not.toContain('rounded-xs') // not in the theme mapping, so no rule
    expect(source).not.toContain('ease-in-out') // the theme has ease-ui and ease-move
    expect(source).not.toContain('next-themes')
  })

  it('makes the button 44 px, and 48 px for the main action', () => {
    const source = read('button.tsx')
    expect(source).toContain('default: "h-11')
    expect(source).toContain('lg: "h-12')
    expect(source).toContain('icon: "size-11"')
    expect(source).not.toMatch(/"icon-(xs|sm|lg)"|\bxs:|\bsm:/)
  })

  it.each(['dialog.tsx', 'sheet.tsx', 'alert-dialog.tsx', 'popover.tsx', 'tooltip.tsx'])(
    '%s renders its portal inside the mini-app root',
    (name) => {
      const source = read(name)
      expect(source).toContain('container={useMiniappPortalContainer()}')
      expect(source).toContain('from "@/miniapp/MiniappRoot"')
    },
  )
})
