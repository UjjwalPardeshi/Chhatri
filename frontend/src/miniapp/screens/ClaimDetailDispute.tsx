/**
 * "This is wrong" (fs-04 S5 step 5, AC-22). In Wave 1 the button sends the dispute phrase through the chat route
 * (`POST /api/merchants/{id}/messages`), the same words the demo's dispute voice chip uses; the backend opens a
 * DISPUTE case and the thanks (DISPUTE_ACK) is shown in a toast in the language of the app. The screen shows the
 * result as well: the question card appears when the claims reload, and focus moves to its case chip, so the button
 * that went away does not take the focus with it. A failure keeps the button, says so under it and in a toast.
 */
import { useCallback, useState } from 'react'
import { toast } from 'sonner'

import { isFeatureEnabled } from '../../features'
import { useLive } from '../../state/live'
import { focusWhenPresent } from '../hooks/nextBestActionBar'
import { t } from '../lib/copy'
import type { Lang } from '../lib/lang'

/** The words of the demo's dispute voice chip (`VOICE_DEMOS.dispute.hi`); the backend reads them as DISPUTE_AMOUNT. */
export const DISPUTE_PHRASE = 'मेरा नुकसान ज़्यादा हुआ।'

export type Dispute = { busy: boolean; failed: boolean; send: () => void }

type DisputeInput = { merchantId: string; lang: Lang; reload: () => void }

export function useDispute({ merchantId, lang, reload }: DisputeInput): Dispute {
  const { api } = useLive()
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const send = useCallback(() => {
    setBusy(true)
    setFailed(false)
    /** With `n5_grievances` on the button opens a PAYOUT_AMOUNT grievance (card 5.1), the same case as the chat path. */
    const request = isFeatureEnabled('n5_grievances') ? api.openGrievance(merchantId, { topic: 'PAYOUT_AMOUNT', text: DISPUTE_PHRASE, lang: lang === 'en' ? 'en' : 'hi' }) : api.sendText(merchantId, DISPUTE_PHRASE)
    request
      .then(() => {
        toast(t('DISPUTE_ACK', lang))
        reload()
        focusWhenPresent('claim-case-chip')
      })
      .catch(() => {
        setFailed(true)
        toast.error(t('error.generic', lang))
      })
      .finally(() => setBusy(false))
  }, [api, merchantId, lang, reload])
  return { busy, failed, send }
}
