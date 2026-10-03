/** The heading block every landing section opens with: a small eyebrow, the section's claim, and an optional lead. */
import type { ReactNode } from 'react'

type Props = { eyebrow: string; title: string; lead?: ReactNode; center?: boolean }

export function SectionHead({ eyebrow, title, lead, center = false }: Props) {
  return (
    <header className={`lp-head ${center ? 'lp-head--center' : ''}`}>
      <p className="lp-eyebrow">{eyebrow}</p>
      <h2 className="lp-h2">{title}</h2>
      {lead ? <p className="lp-lead">{lead}</p> : null}
    </header>
  )
}
