/**
 * A full-width Overview section on one of three surfaces (paper, white, navy) with its content in
 * a centred column, revealed as the presenter scrolls to it (motion motivated by storytelling:
 * each deck slide arrives in turn). IntersectionObserver only, no scroll listeners. A section the
 * page has already scrolled past is revealed too, so fast scrolling never leaves blank sections.
 * Without IntersectionObserver (old browsers, tests) content is shown at once; reduced motion is
 * honoured in CSS.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'

const VISIBLE_THRESHOLD = 0.08
const ROOT_MARGIN = '0px 0px -6% 0px'

export type SectionTone = 'paper' | 'white' | 'navy'

type Props = { children: ReactNode; className?: string; id?: string; label: string; tone?: SectionTone }

export function RevealSection({ children, className = '', id, label, tone = 'paper' }: Props) {
  const ref = useRef<HTMLElement>(null)
  const [shown, setShown] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const node = ref.current
    if (shown || !node) return undefined
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting || (e.boundingClientRect?.bottom ?? 1) < 0)) {
          setShown(true)
          observer.disconnect()
        }
      },
      { threshold: VISIBLE_THRESHOLD, rootMargin: ROOT_MARGIN },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [shown])
  return (
    <section ref={ref} id={id} aria-label={label} className={`ov-section ov-section--${tone} reveal ${shown ? 'is-in' : ''} ${className}`}>
      <div className="ov-section__inner">{children}</div>
    </section>
  )
}
