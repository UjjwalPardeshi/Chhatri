import { describe, expect, it } from 'vitest'

import { cn } from './utils'

describe('cn', () => {
  it('lets the later Tailwind class win and drops falsy values', () => {
    expect(cn('px-2', false, 'px-4', undefined)).toBe('px-4')
  })
})
