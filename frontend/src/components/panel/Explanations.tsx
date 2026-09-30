/**
 * "Why Zone 9 got nothing" (SPEC §17.2): server-written explanations for zones that were not paid.
 * They only mean something once other zones were paid, so before the first trigger evaluation the
 * panel shows a neutral line per slow-day zone instead of giving the punchline away. The live panel
 * (`compact`) sets it tighter but always in full: "…so Chhatri doesn't pay" is the deck's punchline
 * (slide 6), so the event feed below gives way (the panel scrolls) rather than the sentence.
 */
import type { StateSnapshot, ZoneSnapshot } from '../../api/types'

export function splitLead(text: string): { lead: string; rest: string } {
  const colon = text.indexOf(':')
  return colon === -1 ? { lead: '', rest: text } : { lead: text.slice(0, colon + 1), rest: text.slice(colon + 1) }
}

function Explanation({ zoneId, text, compact }: { zoneId: string; text: string; compact: boolean }) {
  const { lead, rest } = splitLead(text)
  return (
    <p className={`card explanation ${compact ? 'explanation--compact' : ''}`} data-zone={zoneId}>
      {lead ? <strong>{lead}</strong> : null}
      {rest}
    </p>
  )
}

export function Explanations({ explanations, compact = false }: { explanations: Record<string, string>; compact?: boolean }) {
  const entries = Object.entries(explanations).toSorted(([a], [b]) => a.localeCompare(b, 'en', { numeric: true }))
  if (entries.length === 0) return null
  return (
    <section className="explanations" aria-label="Zones not paid">
      {entries.map(([zoneId, text]) => (
        <Explanation key={zoneId} zoneId={zoneId} text={text} compact={compact} />
      ))}
    </section>
  )
}

/** "Z9 · slow day, no alert" for each slow-day zone (before any trigger has fired). */
export function slowDayNotes(zones: readonly ZoneSnapshot[]): string[] {
  return zones.filter((z) => z.status === 'slow_day').map((z) => `${z.zone_id} · slow day, no alert`)
}

/** The panel's explanation slot: full explanations after the first trigger, neutral notes before. */
export function ZoneExplanations({ snapshot }: { snapshot: Pick<StateSnapshot, 'explanations' | 'triggers' | 'zones'> }) {
  if (snapshot.triggers.length > 0) return <Explanations explanations={snapshot.explanations} compact />
  const notes = slowDayNotes(snapshot.zones)
  if (notes.length === 0) return null
  return (
    <section className="explanations" aria-label="Zones to watch">
      {notes.map((note) => (
        <p key={note} className="card explanation explanation--quiet">
          {note}
        </p>
      ))}
    </section>
  )
}
