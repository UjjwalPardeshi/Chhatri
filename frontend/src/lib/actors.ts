/**
 * SPEC §11 audit actors in plain words for the console: "officer:officer" → "claims officer",
 * "officer:rk" → "claims officer rk", "policy-engine" → "policy engine"; any other actor
 * (system, model, ai-agent, merchant:…, workflow:…) is shown as it is.
 */
const OFFICER_PREFIX = 'officer:'
/** The officer id the demo session uses (backend OFFICER_ACTOR with the default id). */
const DEFAULT_OFFICER_ID = 'officer'

export function isOfficer(actor: string): boolean {
  return actor.startsWith(OFFICER_PREFIX)
}

export function actorLabel(actor: string): string {
  if (actor === 'policy-engine') return 'policy engine'
  if (!isOfficer(actor)) return actor
  const id = actor.slice(OFFICER_PREFIX.length)
  return id === DEFAULT_OFFICER_ID || id === '' ? 'claims officer' : `claims officer ${id}`
}
