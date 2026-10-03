/**
 * The pricing simulator's levers (GET /api/pricing): the index floor as a choice of the table's own floors, three
 * sliders on the route's bounds, and "Reset to the published rules". A lever that differs from the published rules
 * is marked and says what the rules have. The section debounces and aborts the requests; this file only reports which
 * lever moved and to what.
 */
import { useId } from 'react'

import type { LeverKey, Pricing, PricingLevers } from '../../api/pricing'
import { changedLevers, FLOOR_HINT, LEVER_FORMAT, percent, publishedLevers, SLIDERS, type Slider } from './pricingModel'

type OnLever = (key: LeverKey, value: number) => void
type Props = { answer: Pricing; levers: PricingLevers; onLever: OnLever; onReset: () => void }
type LeverProps = { answer: Pricing; levers: PricingLevers; changed: boolean; onLever: OnLever }

function Foot({ hint, lever, answer, changed }: { hint: string; lever: LeverKey; answer: Pricing; changed: boolean }) {
  return (
    <p className="pricing-lever__foot">
      <span>{hint}</span>
      {changed ? <span className="pricing-lever__rule">published {LEVER_FORMAT[lever](answer.rules[lever])}</span> : null}
    </p>
  )
}

function FloorChoice({ answer, levers, changed, onLever }: LeverProps) {
  return (
    <fieldset className="pricing-lever" data-changed={changed}>
      <legend className="pricing-lever__name">Index floor</legend>
      <div className="pricing-floor">
        {answer.floors.map((floor) => (
          <button key={floor} type="button" className="btn" aria-pressed={levers.floor_pct === floor} onClick={() => onLever('floor_pct', floor)}>
            {percent(floor)}
          </button>
        ))}
      </div>
      <Foot hint={FLOOR_HINT} lever="floor_pct" answer={answer} changed={changed} />
    </fieldset>
  )
}

function SliderLever({ slider, answer, levers, changed, onLever }: LeverProps & { slider: Slider }) {
  const id = useId()
  const value = LEVER_FORMAT[slider.key](levers[slider.key])
  return (
    <div className="pricing-lever" data-changed={changed}>
      <div className="pricing-lever__head">
        <label htmlFor={id} className="pricing-lever__name">
          {slider.label}
        </label>
        <span className="pricing-lever__value num">{value}</span>
      </div>
      <input id={id} type="range" min={slider.min} max={slider.max} step={slider.step} value={levers[slider.key]} aria-valuetext={value} onChange={(e) => onLever(slider.key, Number(e.target.value))} />
      <Foot hint={slider.hint} lever={slider.key} answer={answer} changed={changed} />
    </div>
  )
}

export function PricingControls({ answer, levers, onLever, onReset }: Props) {
  const changed = changedLevers(levers, publishedLevers(answer.rules))
  return (
    <div className="pricing-levers">
      <FloorChoice answer={answer} levers={levers} changed={changed.includes('floor_pct')} onLever={onLever} />
      {SLIDERS.map((slider) => (
        <SliderLever key={slider.key} slider={slider} answer={answer} levers={levers} changed={changed.includes(slider.key)} onLever={onLever} />
      ))}
      <div className="pricing-levers__reset">
        <button type="button" className="btn" disabled={changed.length === 0} onClick={onReset}>
          Reset to the published rules
        </button>
        <span>rules {answer.rules.version}</span>
      </div>
    </div>
  )
}
