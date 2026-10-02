/**
 * One purpose of the consent centre (fs-07 9.9, screens-and-flows 7.2): the label, a state badge (On, Off, Not given),
 * where it was agreed (SIMULATED for the simulator's own), the date, "What we use", the switch and a Receipt button.
 * The switch never flips on tap: it asks to open the withdraw sheet, and it flips when the call succeeds. A purpose that
 * is off or not given has its switch off and disabled and says how to turn it on again; a purpose that cannot be turned
 * off now says why in words. The slip card also lists the stored slips with their erase buttons.
 */
import type { Consent, HeldSlip } from '../api/rights'
import { tr, type RightsCopyKey } from '../copy/rights'
import { ModeBadge } from '../components/ModeBadge'
import { formatDate } from '../lib/format'
import type { Lang } from '../lib/lang'
import { NetworkButton } from '../shell/SharedStates'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../ui/accordion'
import { Badge } from '../ui/badge'
import { Button } from '../ui/button'
import { Card, CardContent } from '../ui/card'
import { Switch } from '../ui/switch'

export type ConsentActions = {
  disabled: boolean
  onWithdraw: (consent: Consent) => void
  onErase: (slip: HeldSlip) => void
  onReceipt: (consent: Consent) => void
}

const SOURCE_KEY: Readonly<Record<NonNullable<Consent['source']>, RightsCopyKey>> = {
  SEEDED: 'consent.source.seeded',
  PAYMENT_APP: 'consent.source.payment_app',
  PAYMENT_CHAT: 'consent.source.payment_chat',
  SLIP_UPLOAD: 'consent.source.slip_upload',
}

const STATE_KEY: Readonly<Record<Consent['status'], RightsCopyKey>> = { ACTIVE: 'consent.state.on', WITHDRAWN: 'consent.state.off', NOT_GIVEN: 'consent.state.not_given' }
const pick = (lang: Lang, en: string, hi: string): string => (lang === 'en' ? en : hi)

function HeldSlips({ held, lang, actions }: { held: readonly HeldSlip[]; lang: Lang; actions: ConsentActions }) {
  if (held.length === 0) return null
  return (
    <ul data-testid="consent-held" className="flex flex-col gap-2">
      {held.map((slip) => (
        <li key={slip.slip_id} data-testid={`held-${slip.slip_id}`} data-state={slip.state} className="flex flex-col gap-2 rounded-lg bg-secondary p-3">
          <div className="flex items-center justify-between gap-2 text-sm">
            <span>{tr('slip.held', lang, { date: formatDate(slip.received_at, lang) })}</span>
            <Badge variant="outline">{tr(slip.state === 'HELD' ? 'slip.state.held' : 'slip.state.erased', lang)}</Badge>
          </div>
          {slip.state === 'HELD' ? (
            <>
              <NetworkButton data-testid={`erase-${slip.slip_id}`} variant="outline" disabled={!slip.can_erase || actions.disabled} onClick={() => actions.onErase(slip)}>
                {tr('slip.erase', lang)}
              </NetworkButton>
              {slip.blocked_reason === 'case_open' ? <p className="text-xs text-ink-2">{tr('slip.erase.blocked', lang)}</p> : null}
            </>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

export function ConsentCard({ consent, lang, actions }: { consent: Consent; lang: Lang; actions: ConsentActions }) {
  const on = consent.status === 'ACTIVE'
  const label = pick(lang, consent.purpose_label_en, consent.purpose_label_hi)
  const lines = lang === 'en' ? consent.data_used_en : consent.data_used_hi
  return (
    <Card data-testid={`consent-${consent.purpose}`} data-status={consent.status} className="py-4">
      <CardContent className="flex flex-col gap-3 px-4">
        <h3 className="text-md font-medium">{label}</h3>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge data-testid="consent-state" variant={on ? 'default' : 'secondary'}>
            {tr(STATE_KEY[consent.status], lang)}
          </Badge>
          {consent.source === 'SEEDED' ? <ModeBadge mode="SIMULATED" testId="consent-simulated" /> : null}
          {consent.granted_at && on ? <span className="text-ink-2">{tr('consent.granted_on', lang, { date: formatDate(consent.granted_at, lang) })}</span> : null}
        </div>
        {consent.source ? <p className="text-sm text-ink-2">{tr(SOURCE_KEY[consent.source], lang)}</p> : null}
        <Accordion type="single" collapsible>
          <AccordionItem value="used">
            <AccordionTrigger data-testid={`used-${consent.purpose}`} className="min-h-11 text-sm">
              {tr('consent.used', lang)}
            </AccordionTrigger>
            <AccordionContent>
              <ul className="flex flex-col gap-1 text-sm">
                {lines.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
        {on ? null : <p data-testid="consent-regrant" className="text-sm">{pick(lang, consent.regrant_en, consent.regrant_hi)}</p>}
        {on && !consent.can_withdraw && consent.blocked_reason === 'case_open' ? <p data-testid="consent-blocked" className="text-sm text-referred-ink">{tr('consent.err.case_open', lang)}</p> : null}
        {consent.held ? <HeldSlips held={consent.held} lang={lang} actions={actions} /> : null}
        <div className="flex items-center justify-between gap-3">
          <span className="relative flex min-h-11 items-center">
            <Switch
              data-testid={`switch-${consent.purpose}`}
              aria-label={tr('consent.switch', lang, { label })}
              checked={on}
              disabled={!on || !consent.can_withdraw || actions.disabled}
              onCheckedChange={() => actions.onWithdraw(consent)}
              className="relative before:absolute before:-inset-4 before:content-['']"
            />
          </span>
          {consent.status === 'NOT_GIVEN' ? null : (
            <Button data-testid={`receipt-${consent.purpose}`} variant="outline" onClick={() => actions.onReceipt(consent)}>
              {tr('consent.receipt', lang)}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
