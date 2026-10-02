/** The feature gate: children render only while the named flag is on (src/features.ts), `fallback` otherwise. */
import type { ReactNode } from 'react'

import { isFeatureEnabled, type FeatureName } from '../../features'

type FeatureProps = { name: FeatureName; children: ReactNode; fallback?: ReactNode }

export function Feature({ name, children, fallback = null }: FeatureProps) {
  return <>{isFeatureEnabled(name) ? children : fallback}</>
}
