import { describe, expect, it } from 'vitest'

import { cn } from './cn'

describe('cn', () => {
  it('keeps the mini-app text sizes next to a text colour', () => {
    expect(cn('text-caption', 'text-paid-ink')).toBe('text-caption text-paid-ink')
    expect(cn('text-field', 'text-foreground')).toBe('text-field text-foreground')
  })

  it('still resolves a real conflict: the later size wins', () => {
    expect(cn('text-caption', 'text-sm')).toBe('text-sm')
    expect(cn('p-4', 'p-2')).toBe('p-2')
  })
})
