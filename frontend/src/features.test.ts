/** Feature flags (Wave 0): everything is off unless VITE_FEATURES names it. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { enabledFeatures, FEATURE_NAMES, isFeatureEnabled, parseFeatures, unknownFeatures } from './features'

afterEach(() => vi.unstubAllEnvs())

describe('FEATURE_NAMES', () => {
  it('lists the Wave 0 flags in the order the backend lists them', () => {
    expect(FEATURE_NAMES).toEqual([
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
      'telegram_channel',
    ])
  })
})

describe('the test run', () => {
  it('starts with every flag off, whatever the shell or frontend/.env.local say (vitest.config.ts pins it)', () => {
    expect(import.meta.env.VITE_FEATURES).toBe('')
    expect(enabledFeatures()).toEqual([])
  })
})

describe('parseFeatures', () => {
  it('is empty without a value', () => {
    expect(parseFeatures(undefined).size).toBe(0)
    expect(parseFeatures('').size).toBe(0)
    expect(parseFeatures('  ,, \n ').size).toBe(0)
  })

  it('reads comma and whitespace separated names, ignoring case and spacing', () => {
    expect([...parseFeatures(' n1_miniapp,N2_ASK_CHHATRI\n h24_whatif  ')]).toEqual(['n1_miniapp', 'n2_ask_chhatri', 'h24_whatif'])
  })

  it('ignores unknown names and repeats', () => {
    expect([...parseFeatures('n4_voice,n4_voice,n4_voices,whatif')]).toEqual(['n4_voice'])
  })
})

describe('unknownFeatures', () => {
  it('lists each name that is not a flag once, in order', () => {
    expect(unknownFeatures('n1_miniapp, n1_minapp,wat,n1_minapp')).toEqual(['n1_minapp', 'wat'])
    expect(unknownFeatures(undefined)).toEqual([])
    expect(unknownFeatures('n1_miniapp')).toEqual([])
  })
})

describe('isFeatureEnabled', () => {
  it('is off for every flag when VITE_FEATURES is empty', () => {
    vi.stubEnv('VITE_FEATURES', '')
    expect(FEATURE_NAMES.filter((name) => isFeatureEnabled(name))).toEqual([])
  })

  it('turns on exactly the flags named in VITE_FEATURES, read at call time', () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp,console_polish')
    expect(FEATURE_NAMES.filter((name) => isFeatureEnabled(name))).toEqual(['n1_miniapp', 'console_polish'])
    vi.stubEnv('VITE_FEATURES', 'n2_ask_chhatri')
    expect(isFeatureEnabled('n1_miniapp')).toBe(false)
    expect(isFeatureEnabled('n2_ask_chhatri')).toBe(true)
  })

  it('takes the value from its argument when one is given', () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    expect(isFeatureEnabled('n4_voice', 'n4_voice')).toBe(true)
    expect(isFeatureEnabled('n1_miniapp', '')).toBe(false)
  })
})

describe('enabledFeatures', () => {
  it('lists the flags that are on, sorted by name, like `features` in GET /api/health', () => {
    expect(enabledFeatures('n2_ask_chhatri, n1_miniapp, typo, console_polish')).toEqual(['console_polish', 'n1_miniapp', 'n2_ask_chhatri'])
  })

  it('is empty by default and reads VITE_FEATURES at call time', () => {
    vi.stubEnv('VITE_FEATURES', '')
    expect(enabledFeatures()).toEqual([])
    vi.stubEnv('VITE_FEATURES', 'h24_whatif')
    expect(enabledFeatures()).toEqual(['h24_whatif'])
  })
})
