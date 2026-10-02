/**
 * Feature flags (Wave 0). Every new feature ships behind a flag that is OFF until the build environment
 * turns it on: `VITE_FEATURES` is a comma or space separated list of flag names, for example
 * `VITE_FEATURES=n1_miniapp,n2_ask_chhatri`. Off means hidden, so the console never renders half a feature.
 *
 * The backend reads the same names from `CHHATRI_FEATURES` (backend/chhatri/features.py) and answers 404
 * `not_found` for a flagged route that is off; scripts/tests/test_feature_flags.py keeps the two name lists
 * identical. Mock mode reads the variable the same way: set it in the shell or in frontend/.env.mock.local.
 */

/** Keep this list identical to FEATURE_NAMES in backend/chhatri/features.py (a test compares them). */
export const FEATURE_NAMES = [
  'n1_miniapp',
  'n2_ask_chhatri',
  'n3_slip_precheck',
  'n4_voice',
  'n5_grievances',
  'n6_consents',
  'n8_marathi',
  'x4_lender_request',
  'x6_provider_panel',
  'x8_distress_guard',
  'h8_ops_strip',
  'h24_whatif',
  'h25_evals',
  'console_polish',
] as const

export type FeatureName = (typeof FEATURE_NAMES)[number]

const KNOWN: ReadonlySet<string> = new Set(FEATURE_NAMES)

function tokens(raw: string | undefined): string[] {
  return (raw ?? '')
    .toLowerCase()
    .split(/[\s,]+/)
    .filter((token) => token !== '')
}

/** The known flags named in `raw`; unknown names are ignored (see `unknownFeatures`). */
export function parseFeatures(raw: string | undefined): ReadonlySet<FeatureName> {
  return new Set(tokens(raw).filter((token): token is FeatureName => KNOWN.has(token)))
}

/** Names in `raw` that are not flags (typos), each once, in order. */
export function unknownFeatures(raw: string | undefined): string[] {
  return [...new Set(tokens(raw).filter((token) => !KNOWN.has(token)))]
}

/** The flags that are on, sorted by name: the shape of `features` in GET /api/health. */
export function enabledFeatures(raw: string | undefined = import.meta.env.VITE_FEATURES): FeatureName[] {
  return [...parseFeatures(raw)].toSorted()
}

/** True when the flag is on. `raw` defaults to the build's VITE_FEATURES, read at call time. */
export function isFeatureEnabled(name: FeatureName, raw: string | undefined = import.meta.env.VITE_FEATURES): boolean {
  return parseFeatures(raw).has(name)
}
