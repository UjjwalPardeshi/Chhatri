/**
 * The heading of a block on the claim screens. In the app on its own the app bar title is the page's `h1` and a block
 * is an `h2`; inside the console's phone frame the console page owns the `h1` and the app bar title is not one, so a
 * block is an `h3` there (the same rule as the Home card).
 */
import type { ComponentProps } from 'react'

import { useMiniapp } from '../shell/MiniappContext'

export function ClaimsHeading(props: Omit<ComponentProps<'h2'>, 'ref'>) {
  const { embedded } = useMiniapp()
  const Tag = embedded ? 'h3' : 'h2'
  return <Tag {...props} />
}
