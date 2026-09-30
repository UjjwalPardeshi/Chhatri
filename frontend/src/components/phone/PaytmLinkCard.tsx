/**
 * The premium link as a Paytm payment card (SPEC §13.4 COVER_LINK, deck slide 8 "BLOCKED"): a
 * navy Paytm header, the first payment and the daily premium, a Pay pill, and the link itself
 * underneath so the real URL stays visible (staging when Paytm is live, simulated otherwise).
 */
import type { ReactNode } from 'react'

import type { Message } from '../../api/types'
import type { CoverLink } from './coverOffer'

type Props = { message: Message; link: CoverLink; stamp: ReactNode }

export function PaytmLinkCard({ message, link, stamp }: Props) {
  return (
    <div className="pay-card">
      <div className="pay-card__head">
        <span>Paytm</span>
        <span className="pay-card__brand">Chhatri cover</span>
      </div>
      <div className="pay-card__body">
        <span className="pay-card__label">First payment</span>
        <strong className="pay-card__amount num">{link.firstPayment}</strong>
        <span className="pay-card__rate num">Cover at {link.perDay} a day</span>
        {message.text_hi ? (
          <p className="pay-card__hi hi" lang="hi">
            {message.text_hi.split(':')[0]}
          </p>
        ) : null}
        <a className="pay-card__pay" href={link.url} target="_blank" rel="noreferrer noopener" aria-hidden="true" tabIndex={-1}>
          Pay {link.firstPayment}
        </a>
        <a className="pay-card__url" href={link.url} target="_blank" rel="noreferrer noopener">
          {link.url}
        </a>
        {stamp}
      </div>
    </div>
  )
}
