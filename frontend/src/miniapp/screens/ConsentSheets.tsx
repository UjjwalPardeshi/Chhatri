/**
 * The two confirmation sheets of the consent centre. Withdraw (fs-07 9.9): the effect text of the purpose with its numbers
 * filled in by the API, then "Turn off" and "Keep it on"; a refusal shows its reason in the sheet and leaves the switch
 * on. Erase: says before the merchant confirms what is erased, what stays and that the activity log cannot be edited.
 * Focus starts on the safe button ("Keep it on", "Keep it"), Esc cancels, the destructive button is last.
 */
import { useRef } from 'react'

import { tr, type RightsCopyKey } from '../copy/rights'
import type { Lang } from '../lib/lang'
import { NetworkButton } from '../shell/SharedStates'
import { Button } from '../ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet'

type SheetProps = { lang: Lang; busy: boolean; error: RightsCopyKey | null; onClose: () => void; onConfirm: () => void }

function Confirm({ testId, title, lang, busy, error, onClose, onConfirm, keep, confirm, children }: SheetProps & { testId: string; title: string; keep: string; confirm: string; children: React.ReactNode }) {
  const keepRef = useRef<HTMLButtonElement>(null)
  return (
    <Sheet open onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent side="bottom" showCloseButton={false} data-testid={testId} aria-describedby={undefined} className="max-h-[90%] gap-0 overflow-y-auto rounded-t-2xl pb-2" onOpenAutoFocus={(event) => { event.preventDefault(); keepRef.current?.focus() }}>
        <SheetHeader>
          <SheetTitle className="text-md">{title}</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-3 px-4 pb-2">
          {children}
          {error ? (
            <p role="alert" data-testid={`${testId}-error`} className="rounded-lg bg-blocked-soft p-3 text-sm">
              {tr(error, lang)}
            </p>
          ) : null}
          <Button ref={keepRef} data-testid={`${testId}-keep`} variant="outline" size="lg" onClick={onClose}>
            {keep}
          </Button>
          <NetworkButton data-testid={`${testId}-confirm`} variant="destructive" size="lg" disabled={busy} onClick={onConfirm}>
            {confirm}
          </NetworkButton>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export function WithdrawSheet({ effect, ...rest }: SheetProps & { effect: string }) {
  return (
    <Confirm {...rest} testId="withdraw-sheet" title={tr('consent.withdraw.title', rest.lang)} keep={tr('consent.withdraw.cancel', rest.lang)} confirm={tr('consent.withdraw.confirm', rest.lang)}>
      <p data-testid="withdraw-effect" className="text-md">
        {effect}
      </p>
    </Confirm>
  )
}

export function EraseSheet(props: SheetProps) {
  const { lang } = props
  return (
    <Confirm {...props} testId="erase-sheet" title={tr('slip.erase.title', lang)} keep={tr('slip.erase.cancel', lang)} confirm={tr('slip.erase.confirm', lang)}>
      <p className="text-md">{tr('slip.erase.removes', lang)}</p>
      <p className="text-md">{tr('slip.erase.keeps', lang)}</p>
      <p className="text-sm text-ink-2">{tr('slip.erase.audit_note', lang)}</p>
    </Confirm>
  )
}
