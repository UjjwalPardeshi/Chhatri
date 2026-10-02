/**
 * S7 Trust receipt (fs-04 8, 10, screens and flows 4.7, H3): a document the merchant can keep, print or show to a bank
 * or an officer. It is a receipt once the payout is credited, and the same screen is a record of the decision before
 * that. "Print or save as PDF" calls `window.print()` once; the print rules (receipt.print.css) hide the bars and the
 * buttons and let the page flow. An unknown decision is "not found" with a way back, and the bar leads to the claim's
 * dispute button when the claim was paid.
 */
import { Printer } from 'lucide-react'
import { useMemo } from 'react'

import { useNextBest } from '../hooks/nextBestActionBar'
import { useClaims, useReceipt } from '../hooks/useMiniappData'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { ResourceScreen, ScreenRoot } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Skeleton } from '../ui/skeleton'
import { isNotFound, NotFoundCard } from './ClaimsNotFound'
import { ReceiptContent } from './ReceiptContent'
import { claimOfReceipt } from './ReceiptRows'
import './receipt.print.css'

/** Header rows, a formula bar and four lines. */
function ReceiptSkeleton() {
  const { lang } = useMiniapp()
  return (
    <output data-testid="app-skeleton" aria-label={t('state.loading', lang)} className="flex flex-col gap-4 rounded-xl border bg-card p-4">
      {[0, 1, 2].map((row) => (
        <Skeleton key={row} className="h-5 w-2/3" />
      ))}
      <Skeleton className="h-12 w-full rounded-lg" />
      {[0, 1, 2, 3].map((row) => (
        <Skeleton key={row} className="h-4 w-full" />
      ))}
    </output>
  )
}

function PrintButton() {
  const { lang } = useMiniapp()
  return (
    <Button type="button" data-testid="receipt-print" size="lg" className="h-auto min-h-12 w-full py-2 whitespace-normal print:hidden" onClick={() => window.print()}>
      <Printer aria-hidden="true" />
      {t('receipt.btn.print', lang)}
    </Button>
  )
}

export function Receipt() {
  const { merchantId, url, lang } = useMiniapp()
  const receipt = useReceipt(merchantId, url.decision)
  const claims = useClaims(merchantId)
  const claim = useMemo(() => claimOfReceipt(claims.data, receipt.data), [claims.data, receipt.data])
  const loaded = receipt.data !== null && (receipt.state === 'ready' || receipt.state === 'offline')
  useNextBest(loaded && claim !== null && claims.data !== null ? { screen: 'receipt', cover: null, claims: claims.data, claim } : null)
  if (receipt.state === 'error' && isNotFound(receipt.error)) {
    return (
      <ScreenRoot name="receipt" state="error">
        <NotFoundCard />
      </ScreenRoot>
    )
  }
  return (
    <ResourceScreen name="receipt" resource={receipt} skeleton={<ReceiptSkeleton />}>
      {(data) => (
        <>
          <ReceiptContent receipt={data} />
          <PrintButton />
          <p data-testid="receipt-footer" className="text-caption text-ink-3">
            {t('receipt.footer', lang)}
          </p>
        </>
      )}
    </ResourceScreen>
  )
}
