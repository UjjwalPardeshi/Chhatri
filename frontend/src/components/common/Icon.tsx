/** Inline SVG icons (no icon fonts, no external requests; SPEC §20 offline-safe). */

export type IconName =
  | 'play'
  | 'pause'
  | 'step'
  | 'reset'
  | 'sound-on'
  | 'sound-off'
  | 'mic'
  | 'send'
  | 'attach'
  | 'camera'
  | 'speaker'
  | 'check'
  | 'cross'
  | 'question'
  | 'dash'
  | 'shield'
  | 'north'
  | 'umbrella'
  | 'chevron'
  | 'stop'
  | 'map'
  | 'phone'
  | 'arrow'
  | 'more'
  | 'drop'
  | 'close'
  | 'zoom'
  | 'notes'
  | 'bolt'

const PATHS: Record<IconName, string> = {
  play: 'M8 5.5v13l11-6.5z',
  pause: 'M7 5h4v14H7zM13 5h4v14h-4z',
  step: 'M6 5.5v13l9-6.5zM16 5h3v14h-3z',
  reset: 'M12 5a7 7 0 1 1-6.6 4.7l1.9.7A5 5 0 1 0 12 7v3L7.5 6 12 2z',
  'sound-on': 'M4 9h4l5-4v14l-5-4H4zM16 8.5a5 5 0 0 1 0 7l-1.4-1.4a3 3 0 0 0 0-4.2zM18.5 6a8.5 8.5 0 0 1 0 12l-1.4-1.4a6.5 6.5 0 0 0 0-9.2z',
  'sound-off': 'M4 9h4l5-4v14l-5-4H4zM16.3 9.7l1.4-1.4 2 2 2-2 1.4 1.4-2 2 2 2-1.4 1.4-2-2-2 2-1.4-1.4 2-2z',
  mic: 'M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM6 11h2a4 4 0 0 0 8 0h2a6 6 0 0 1-5 5.9V20h-2v-3.1A6 6 0 0 1 6 11z',
  send: 'M3 20.5 21 12 3 3.5 3 10l12 2-12 2z',
  attach: 'M16.5 6.5 9 14a1.5 1.5 0 0 0 2.1 2.1l8-8a3.5 3.5 0 0 0-5-5l-8.5 8.5a5.5 5.5 0 0 0 7.8 7.8l7-7-1.4-1.4-7 7a3.5 3.5 0 1 1-5-5L15.5 4.5a1.5 1.5 0 0 1 2.1 2.1l-8 8-.1.1z',
  camera: 'M9 4h6l1.5 2H20a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h3.5zM12 8a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z',
  speaker: 'M4 9h4l5-4v14l-5-4H4zM16 8.5a5 5 0 0 1 0 7l-1.4-1.4a3 3 0 0 0 0-4.2z',
  check: 'M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4 18.7 7z',
  cross: 'M6.4 5 5 6.4 10.6 12 5 17.6 6.4 19l5.6-5.6 5.6 5.6 1.4-1.4-5.6-5.6L19 6.4 17.6 5 12 10.6z',
  question: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm1 14h-2v-2h2zm2.1-7.1-.9.9A3 3 0 0 0 13 13h-2v-.5a4 4 0 0 1 1.2-2.8l1.2-1.3a1.7 1.7 0 1 0-2.9-1.2H8.5a3.5 3.5 0 1 1 6.6 1.7z',
  dash: 'M5 11h14v2H5z',
  shield: 'M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z',
  north: 'M12 2 6 20l6-4 6 4z',
  umbrella: 'M12 2a10 10 0 0 1 10 10c-1.1-1.2-2.3-1.8-3.4-1.8s-2.3.6-3.3 1.8c-1-1.2-2.2-1.8-3.3-1.8s-2.3.6-3.3 1.8C6.6 10.8 5.4 10.2 4.3 10.2S2.1 10.8 2 12A10 10 0 0 1 12 2zm-1 10.5h2V19a3 3 0 0 1-6 0h2a1 1 0 0 0 2 0z',
  chevron: 'M8.6 7.4 10 6l6 6-6 6-1.4-1.4 4.6-4.6z',
  stop: 'M7 7h10v10H7z',
  map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zm0 2.2 6 2v10.6l-6-2z',
  arrow: 'M4 11h12.2l-4.6-4.6L13 5l7 7-7 7-1.4-1.4 4.6-4.6H4z',
  more: 'M5 10.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm7 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3zm7 0a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z',
  drop: 'M12 2.5c3.3 4.4 6 7.9 6 11.3a6 6 0 0 1-12 0c0-3.4 2.7-6.9 6-11.3z',
  close: 'M6.4 5 5 6.4 10.6 12 5 17.6 6.4 19l5.6-5.6 5.6 5.6 1.4-1.4-5.6-5.6L19 6.4 17.6 5 12 10.6z',
  zoom: 'M10.5 3a7.5 7.5 0 0 1 6 12l4.3 4.3-1.4 1.4-4.3-4.3A7.5 7.5 0 1 1 10.5 3zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zm-1 2.5h2v2h2v2h-2v2h-2v-2h-2v-2h2z',
  notes: 'M6 3h9l4 4v14H6zm2 2v14h9V8h-3V5zm1.5 6h6v1.5h-6zm0 3h6v1.5h-6z',
  bolt: 'M13 2 5 13.5h5.5L10 22l9-12h-5.8z',
  phone: 'M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm0 3v13h10V5zm5 14.2a1 1 0 1 0 0 .1z',
}

type Props = { name: IconName; size?: number; className?: string; title?: string }

export function Icon({ name, size = 18, className, title }: Props) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  )
}
