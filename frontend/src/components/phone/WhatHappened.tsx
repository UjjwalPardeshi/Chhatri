/**
 * The "What happened" stepper beside the phone (SPEC §17.2, deck slide 7): decision, credit and
 * instalment pause with their simulated times, left to right, so the presenter can point at the
 * whole chain in one glance (steps from whatHappened.ts).
 */
import { hhmm } from '../../lib/time'
import type { HappenedStep } from './whatHappened'

export function WhatHappened({ steps }: { steps: readonly HappenedStep[] }) {
  if (steps.length === 0) return null
  return (
    <section className="card merchant-card happened" aria-label="What happened">
      <p className="eyebrow">What happened</p>
      <ol className="happened__steps">
        {steps.map((step) => (
          <li key={step.key} className="happened__step" data-tone={step.tone}>
            <span className="happened__at num">{hhmm(step.at)}</span>
            <span className="happened__dot" aria-hidden="true" />
            <strong className="happened__title num">{step.title}</strong>
            {step.detail ? <span className="happened__detail muted">{step.detail}</span> : null}
          </li>
        ))}
      </ol>
    </section>
  )
}
