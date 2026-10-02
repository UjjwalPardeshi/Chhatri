/** KPI strip (SPEC §17.2, deck slide 6): three numbers, and "4 min" keeps a quiet unit so it fits its cell at the presenter's 44 px (fs-08 13.1). */
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { KpiTiles, triggerToMoney } from './KpiTiles'

const kpis = { zones_triggered: 3, shops_paid: 312, trigger_to_money_min: 4 as number | null, total_paid_label: '₹4,25,420', instalments_paused: 123 }
const value = (key: string) => document.querySelector(`[data-kpi="${key}"] .kpi__value`)

describe('KpiTiles', () => {
  it('reads 3, 312 and 4 min, the golden numbers (AC-K8-01)', () => {
    render(<KpiTiles kpis={kpis} />)
    expect(value('zones')?.textContent).toBe('3')
    expect(value('shops')?.textContent).toBe('312')
    expect(value('ttm')?.textContent).toBe('4 min')
    expect(triggerToMoney(kpis)).toBe('4 min')
  })

  it('sets the unit apart from the number, so only the number takes the big size', () => {
    render(<KpiTiles kpis={kpis} />)
    expect(value('ttm')?.querySelector('.kpi__unit')?.textContent).toBe(' min')
    expect(value('zones')?.querySelector('.kpi__unit')).toBeNull()
  })

  it('shows a dash with no unit before the money has moved', () => {
    render(<KpiTiles kpis={{ ...kpis, trigger_to_money_min: null }} />)
    expect(value('ttm')?.textContent).toBe('—')
    expect(value('ttm')?.querySelector('.kpi__unit')).toBeNull()
    expect(triggerToMoney({ ...kpis, trigger_to_money_min: null })).toBe('—')
  })
})
