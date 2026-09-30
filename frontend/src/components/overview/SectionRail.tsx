/**
 * A slim table of contents for the long Overview (deck order, slides 2-13), sticky under the
 * header once the hero is scrolled past. The section in the middle of the screen is marked
 * (IntersectionObserver only, no scroll listeners); links are plain anchors to section ids.
 * Hidden on narrow screens (CSS), where the page is read top to bottom.
 */
import { useEffect, useState } from 'react'

export const RAIL: readonly { id: string; label: string }[] = [
  { id: 'ov-problem', label: 'Problem' },
  { id: 'ov-how', label: 'How it works' },
  { id: 'ov-storm', label: 'Storm' },
  { id: 'ov-whatsapp', label: 'WhatsApp' },
  { id: 'ov-humans', label: 'Humans' },
  { id: 'ov-proof', label: 'Proof' },
  { id: 'ov-tech', label: 'Tech' },
  { id: 'ov-business', label: 'Business' },
  { id: 'ov-roadmap', label: 'Roadmap' },
]

/** A section counts as current while it crosses this band around the middle of the screen. */
const MIDDLE_BAND = '-40% 0px -55% 0px'

export function SectionRail() {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined
    const observer = new IntersectionObserver(
      (entries) => {
        const hit = entries.find((e) => e.isIntersecting)
        if (hit) setActive(hit.target.id)
      },
      { rootMargin: MIDDLE_BAND },
    )
    for (const item of RAIL) {
      const el = document.getElementById(item.id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [])
  return (
    <nav className="ov-rail" aria-label="Sections">
      <ol className="ov-rail__list">
        {RAIL.map((item) => (
          <li key={item.id}>
            <a className="ov-rail__link" href={`#${item.id}`} aria-current={active === item.id ? 'location' : undefined}>
              {item.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  )
}
