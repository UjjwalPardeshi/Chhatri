/**
 * The scam warning of an answer (H19, screens 5.3): a banner above the answer with the blocked tone, the triangle-alert
 * icon and `role="alert"`. It never blocks the question. The helpline line (`scam.report`) stays hidden until the number
 * and the portal address are in configuration and checked against the official source (copy deck open item 3).
 */
import { TriangleAlert } from 'lucide-react'

import { AlertBanner } from '../components/AlertBanner'
import { ta } from '../copy/ask'
import type { Lang } from '../lib/lang'

export function AskScamBanner({ lang }: { lang: Lang }) {
  return (
    <div data-testid="ask-scam">
      <AlertBanner tone="error" icon={TriangleAlert} title={ta('scam.title', lang)}>
        <p>{ta('ASK_SCAM_WARNING', lang)}</p>
        <p>{ta('scam.do', lang)}</p>
        <p className="text-caption text-ink-2">{ta('scam.note', lang)}</p>
      </AlertBanner>
    </div>
  )
}
