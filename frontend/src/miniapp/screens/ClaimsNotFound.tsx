/**
 * An id that matches nothing (a claim, or a decision): `error.not_found` and a link back to the list of claims
 * (fs-04 S5 to S7). Retrying would ask the same question again, so the card offers the way out instead of Retry.
 */
import { Link } from 'react-router'

import type { ApiError } from '../../api/client'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Button } from '../ui/button'

/** A 404, or the `not_found` code the hooks raise for a link with no valid id. */
export const isNotFound = (error: ApiError | null): boolean => error !== null && (error.status === 404 || error.code === 'not_found')

export function NotFoundCard() {
  const { lang, url } = useMiniapp()
  return (
    <div data-testid="app-error" role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-blocked bg-blocked-soft p-4">
      <p className="text-sm font-medium text-foreground">{t('error.not_found', lang)}</p>
      <Button asChild variant="outline" className="h-auto min-h-11 py-2">
        <Link to={url.href({ screen: 'claims' })}>{t('tracker.title', lang)}</Link>
      </Button>
    </div>
  )
}
