/**
 * The demo clock sheet (screens-and-flows section 8, N7): on the standalone route there is no console control bar, so a
 * visitor on a phone could not move the replay, and at its start Anil has no claim. The clock text in the app bar
 * opens this bottom sheet: the chapters the console already has (for the monsoon: Alert 14:00, Trigger 17:00, Paid
 * 17:04, Instalment 17:05), Play or Pause, and "Back to the start". It drives the same replay routes as the control bar
 * and adds no endpoint. A chapter seeks to its own minute, so what happened there is on screen at once.
 */
import { useState } from 'react'

import { CHAPTERS, type Chapter } from '../../content/chapters'
import { useLive } from '../../state/live'
import { t, type CopyKey } from '../lib/copy'
import { formatDateTime } from '../lib/format'
import { Button } from '../ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet'
import { useMiniapp } from './MiniappContext'

/** The replay speed of Play here: the console's default speed when the clock has none. */
const PLAY_SPEED = 10

const CHAPTER_KEYS: Readonly<Record<string, CopyKey>> = {
  Alert: 'clock.chapter.alert',
  Trigger: 'clock.chapter.trigger',
  Paid: 'clock.chapter.paid',
  Instalment: 'clock.chapter.instalment',
  'Check-in': 'clock.chapter.checkin',
  'Cover asked': 'clock.chapter.cover',
}

function ChapterButton({ chapter }: { chapter: Chapter }) {
  const { lang } = useMiniapp()
  const { replay, replayBusy } = useLive()
  const key = CHAPTER_KEYS[chapter.label]
  return (
    <Button variant="outline" size="lg" data-testid={`app-clock-chapter-${chapter.at}`} disabled={replayBusy !== null} onClick={() => void replay('seek', chapter.at)}>
      {key ? t(key, lang) : chapter.label} <span className="num">{chapter.at}</span>
    </Button>
  )
}

export function DemoClockSheet() {
  const { lang, now } = useMiniapp()
  const { snapshot, replay, replayBusy } = useLive()
  const [open, setOpen] = useState(false)
  const clock = snapshot?.clock ?? null
  const chapters: readonly Chapter[] = clock?.scenario ? CHAPTERS[clock.scenario] : []
  const running = clock?.running ?? false
  const busy = replayBusy !== null
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button type="button" data-testid="app-clock-open" className="block min-h-6 text-left text-2xs leading-tight text-ink-3 underline decoration-dotted underline-offset-2">
          <time data-testid="app-clock" dateTime={now ?? undefined}>
            {t('app.clock', lang, { time: formatDateTime(now, lang) })}
          </time>
        </button>
      </SheetTrigger>
      <SheetContent side="bottom" data-testid="app-clock-sheet" className="gap-0 rounded-t-2xl pb-4">
        <SheetHeader className="px-4 pt-5 pb-3">
          <SheetTitle className="text-lg font-medium">{t('clock.sheet.title', lang)}</SheetTitle>
          <SheetDescription className="text-sm text-muted-foreground">{t('clock.sheet.note', lang)}</SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4">
          {chapters.length > 0 ? (
            <div className="grid grid-cols-2 gap-2">
              {chapters.map((chapter) => (
                <ChapterButton key={chapter.at} chapter={chapter} />
              ))}
            </div>
          ) : null}
          <div className="grid grid-cols-2 gap-2">
            <Button size="lg" data-testid="app-clock-play" disabled={busy || clock === null} onClick={() => void replay(running ? 'pause' : 'play', running ? undefined : clock?.speed || PLAY_SPEED)}>
              {t(running ? 'clock.sheet.pause' : 'clock.sheet.play', lang)}
            </Button>
            <Button size="lg" variant="outline" data-testid="app-clock-reset" disabled={busy || clock === null} onClick={() => void replay('reset')}>
              {t('clock.sheet.start', lang)}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
