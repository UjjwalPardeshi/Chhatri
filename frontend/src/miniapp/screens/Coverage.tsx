/**
 * S2 Coverage explainer (fs-04 section 8): what Chhatri covers in plain words. A card of the cover in numbers, then
 * seven sections (rain, hospital cash, how much, when cover starts, premium, when a claim is not paid, the loan
 * instalment), each with its clause chip, two to four sentences, a worked example where there is one, and the insurance
 * words of the section as buttons for the jargon lens (H20). Every number is read from `GET /api/policy` and filled in
 * as a `{placeholder}`, so a change of the rules reaches the page; the examples use the golden demo numbers and say so.
 * Viewing this screen never asks for a quote or makes a payment link.
 */
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'

import type { RuleNumbers } from '../api/rules'
import { JargonTerms } from '../components/JargonTerms'
import type { TermId } from '../glossary'
import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useCover } from '../hooks/useMiniappData'
import { useRules } from '../hooks/useRules'
import { t, type CopyKey } from '../lib/copy'
import { rulesParams } from '../lib/copyRules'
import type { Lang } from '../lib/lang'
import { useMiniapp } from '../shell/MiniappContext'
import { ResourceScreen } from '../shell/SharedStates'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../ui/accordion'
import { Badge } from '../ui/badge'
import { Card, CardContent } from '../ui/card'
import { Skeleton } from '../ui/skeleton'
import type { Cover } from '../../api/types'

const SECTION_IDS = ['c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c10'] as const
type SectionId = (typeof SECTION_IDS)[number]

type SectionDef = {
  id: SectionId
  /** The clause chips of the policy wording. */
  clauses: readonly string[]
  /** The words of this section that no earlier part of the page has already given a button (a term is asked about once). */
  terms: readonly TermId[]
  example?: Extract<CopyKey, `explain.${SectionId}.example`>
  reasons?: boolean
}

const SECTIONS: readonly SectionDef[] = [
  { id: 'c2', clauses: ['C2'], terms: ['expected_day', 'area_drop'], example: 'explain.c2.example' },
  { id: 'c3', clauses: ['C3'], terms: ['referred'], example: 'explain.c3.example' },
  { id: 'c4', clauses: ['C4'], terms: [] },
  { id: 'c5', clauses: ['C5'], terms: [], example: 'explain.c5.example' },
  { id: 'c6', clauses: ['C6'], terms: ['premium', 'prepaid_through', 'settlement'], example: 'explain.c6.example' },
  { id: 'c7', clauses: ['C7', 'C8'], terms: [], reasons: true },
  { id: 'c10', clauses: ['C10'], terms: ['edi_holiday'] },
]

/** The words of the numbers card: its rows name a share, caps, a limit, a wait and an alert. */
const NUMBER_TERMS: readonly TermId[] = ['waiting_period', 'payout_share', 'daily_cap', 'annual_limit', 'alert']

/** The decline reasons of the message catalogue (BUILT REASON_* lines), the reasons Chhatri gives. */
const REASON_KEYS = [
  'reason.cover_in_force',
  'reason.premium_prepaid',
  'reason.silence_verified',
  'reason.not_already_paid',
  'reason.within_annual_limit',
  'reason.cover_before_alert',
  'reason.alert_active',
  'reason.index_quorum',
  'reason.below_floor',
  'reason.below_model_range',
] as const satisfies readonly CopyKey[]

const isSection = (value: string): value is SectionId => (SECTION_IDS as readonly string[]).includes(value)

/** The section a link names through its hash (`#c6`), if it is one. */
function sectionOfHash(hash: string): SectionId | null {
  const name = hash.replace(/^#/, '')
  return isSection(name) ? name : null
}

function CoverageSkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-3">
      <Skeleton className="h-52 w-full rounded-lg" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </output>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-sm text-secondary-foreground">{label}</dt>
      <dd className="num shrink-0 text-right text-md font-medium">{value}</dd>
    </div>
  )
}

function NumbersCard({ rules, lang }: { rules: RuleNumbers; lang: Lang }) {
  const { embedded } = useMiniapp()
  const Title = embedded ? 'h3' : 'h2'
  const days = (n: number) => t('explain.val.days', lang, { n })
  return (
    <Card data-testid="coverage-numbers" className="gap-3 py-4">
      <CardContent className="flex flex-col gap-3 px-4">
        <Title className="text-lg font-medium">{t('explain.numbers.title', lang)}</Title>
        <dl className="flex flex-col gap-2.5">
          <Figure label={t('explain.num.share', lang)} value={`${rules.payout_share_pct}%`} />
          <Figure label={t('explain.num.area_cap', lang)} value={rules.area_cap_label} />
          <Figure label={t('explain.num.personal_cap', lang)} value={rules.personal_cap_label} />
          <Figure label={t('explain.num.annual', lang)} value={rules.annual_limit_label} />
          <Figure label={t('explain.num.waiting', lang)} value={days(rules.waiting_period_days)} />
          <Figure label={t('explain.num.lookahead', lang)} value={t('explain.val.hours', lang, { n: rules.alert_lookahead_hours })} />
          <Figure label={t('explain.num.first_days', lang)} value={days(rules.first_payment_days)} />
        </dl>
        <div className="flex flex-col gap-0.5 border-t pt-2">
          <p className="text-caption text-muted-foreground">{t('explain.terms_hint', lang)}</p>
          <JargonTerms ids={NUMBER_TERMS} testId="coverage-numbers-terms" />
        </div>
      </CardContent>
    </Card>
  )
}

function Example({ id, exampleKey, lang }: { id: SectionId; exampleKey: CopyKey; lang: Lang }) {
  return (
    <div data-testid={`coverage-example-${id}`} className="flex flex-col gap-1 rounded-lg bg-secondary p-3">
      <p className="text-xs font-medium text-muted-foreground">{t('explain.example.title', lang)}</p>
      <p className="text-sm text-secondary-foreground">{t(exampleKey, lang)}</p>
      <p className="text-caption text-muted-foreground">{t('explain.example.sim', lang)}</p>
    </div>
  )
}

function Reasons({ lang }: { lang: Lang }) {
  return (
    <ul className="flex flex-col gap-2">
      {REASON_KEYS.map((key) => (
        <li key={key} className="flex items-start gap-2 text-sm">
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground" aria-hidden="true" />
          <span>{t(key, lang)}</span>
        </li>
      ))}
    </ul>
  )
}

function Section({ def, open, rules, lang }: { def: SectionDef; open: boolean; rules: RuleNumbers; lang: Lang }) {
  const params = rulesParams(rules)
  return (
    <AccordionItem value={def.id} data-testid={`coverage-section-${def.id}`}>
      <AccordionTrigger className="min-h-12 items-center py-3 text-md">
        <span className="flex flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <span>{t(`explain.${def.id}.title`, lang)}</span>
          {def.clauses.map((clause) => (
            <Badge key={clause} variant="outline" data-clause="" className="text-muted-foreground">
              {clause}
            </Badge>
          ))}
        </span>
      </AccordionTrigger>
      {/* Mounted while closed, so the words stay in the page (find, tests) and hidden from view and from screen readers. */}
      <AccordionContent forceMount hidden={!open}>
        <div className="flex flex-col gap-3">
          <p className="text-sm leading-relaxed">{t(`explain.${def.id}.body`, lang, params)}</p>
          {def.reasons ? <Reasons lang={lang} /> : null}
          {def.example ? <Example id={def.id} exampleKey={def.example} lang={lang} /> : null}
          <JargonTerms ids={def.terms} testId={`coverage-terms-${def.id}`} />
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}

function PriceLine({ cover, lang }: { cover: Cover | null; lang: Lang }) {
  if (cover === null) return <Skeleton data-testid="coverage-price-loading" className="h-12 w-full" />
  const covered = cover.status !== 'NONE'
  return (
    <div data-testid="coverage-price" className="flex flex-col gap-1 rounded-lg border bg-card px-4 py-3">
      <p className="text-md font-medium">{covered ? t('explain.price.covered', lang, { per_day: cover.premium_per_day_label }) : t('explain.price.uncovered', lang)}</p>
      {covered ? <p className="text-caption text-muted-foreground">{t('explain.price.prototype', lang)}</p> : null}
    </div>
  )
}

function CoverageBody({ rules, cover }: { rules: RuleNumbers; cover: Cover | null }) {
  const { lang } = useMiniapp()
  const { hash } = useLocation()
  const named = sectionOfHash(hash)
  const [open, setOpen] = useState<string[]>([named ?? 'c2'])
  const [seenHash, setSeenHash] = useState(named)
  // A link to a section (`#c6`) opens it: adjusted while rendering, not in an effect, so there is no second pass.
  if (named !== seenHash) {
    setSeenHash(named)
    if (named !== null && !open.includes(named)) setOpen([...open, named])
  }
  useEffect(() => {
    if (named !== null) document.querySelector(`[data-testid="coverage-section-${named}"]`)?.scrollIntoView?.({ block: 'start' })
  }, [named])
  return (
    <>
      <NumbersCard rules={rules} lang={lang} />
      <p className="text-md">{t('explain.no_forms', lang)}</p>
      <Card className="gap-0 py-0">
        <CardContent className="px-4">
          <Accordion type="multiple" value={open} onValueChange={setOpen}>
            {SECTIONS.map((def) => (
              <Section key={def.id} def={def} open={open.includes(def.id)} rules={rules} lang={lang} />
            ))}
          </Accordion>
        </CardContent>
      </Card>
      <PriceLine cover={cover} lang={lang} />
      <div className="flex flex-col gap-0.5">
        <p data-testid="coverage-rules-note" className="text-caption text-muted-foreground">
          {t('explain.rules_note', lang, { rules_version: rules.version })}
        </p>
        <JargonTerms ids={['rules_version']} />
      </div>
    </>
  )
}

export function Coverage() {
  const { merchantId } = useMiniapp()
  const rules = useRules()
  const cover = useCover(merchantId)
  const claims = useClaims(merchantId)
  const shown = (rules.state === 'ready' || rules.state === 'offline') && rules.data !== null
  const settled = cover.state !== 'loading' && claims.state !== 'loading'
  useNextBest(shown && settled ? { screen: 'coverage', cover: cover.data, claims: claims.data ?? [] } : null)
  return (
    <ResourceScreen name="coverage" resource={rules} skeleton={<CoverageSkeleton />}>
      {(data) => <CoverageBody rules={data} cover={cover.data} />}
    </ResourceScreen>
  )
}
