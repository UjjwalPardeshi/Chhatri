/**
 * Where Chhatri's messages go (flag telegram_channel), on Settings: WhatsApp or Telegram, whether a Telegram chat is
 * linked, and "Open Chhatri in Telegram" (the bot's deep link) once the bot is known. The choice is the same write the
 * console makes; it never changes cover or payouts. Nothing renders while the flag is off.
 */
import type { PreferredChannel } from '../../api/types'
import { useChannel } from '../../state/useChannel'
import { t } from '../lib/copy'
import { useMiniapp } from '../shell/MiniappContext'
import { Button } from '../ui/button'
import { Label } from '../ui/label'
import { RadioGroup, RadioGroupItem } from '../ui/radio-group'

const OPTIONS: readonly { id: PreferredChannel; label: string }[] = [
  { id: 'whatsapp', label: 'WhatsApp' },
  { id: 'telegram', label: 'Telegram' },
]

function isChannel(value: string): value is PreferredChannel {
  return value === 'whatsapp' || value === 'telegram'
}

export function ChannelChoice() {
  const { merchantId, lang, online } = useMiniapp()
  const channel = useChannel(merchantId)
  if (!channel.on || channel.view === null) return null
  const telegram = channel.telegram
  const onTelegram = channel.preferred === 'telegram'
  return (
    <fieldset data-testid="channel-choice" className="flex flex-col gap-2">
      <legend className="mb-2 px-1 text-caption font-bold text-ink-2">{t('channel.label', lang)}</legend>
      <RadioGroup
        className="gap-0 overflow-hidden rounded-lg border bg-card [&>*+*]:border-t [&>*+*]:border-line-soft"
        value={channel.preferred}
        onValueChange={(next) => isChannel(next) && next !== channel.preferred && void channel.choose(next)}
        aria-label={t('channel.label', lang)}
        disabled={channel.busy || !online}
      >
        {OPTIONS.map((option) => (
          <Label key={option.id} htmlFor={`channel-option-${option.id}`} className="flex min-h-14 items-center gap-3 px-4 py-3 text-md font-medium">
            <RadioGroupItem id={`channel-option-${option.id}`} value={option.id} data-testid={`channel-option-${option.id}`} />
            {option.label}
          </Label>
        ))}
      </RadioGroup>
      <p className="text-caption text-muted-foreground">{t('channel.hint', lang)}</p>
      {onTelegram && telegram ? (
        <div className="flex flex-col gap-2">
          <p data-testid="channel-link-state" className="text-sm">
            {t(telegram.linked ? 'channel.linked' : 'channel.not_linked', lang)}
          </p>
          {telegram.deep_link ? (
            <Button asChild variant="outline" size="lg">
              <a data-testid="channel-open-telegram" href={telegram.deep_link} target="_blank" rel="noreferrer">
                {t('channel.open', lang)}
              </a>
            </Button>
          ) : null}
          {telegram.mode === 'LIVE' ? null : <p className="rounded-lg bg-demo-soft px-3 py-2 text-xs text-demo">{t('channel.simulated', lang)}</p>}
        </div>
      ) : null}
      {channel.error ? (
        <p role="alert" className="rounded-lg border border-blocked bg-blocked-soft p-3 text-sm">
          {t('channel.error', lang)}
        </p>
      ) : null}
    </fieldset>
  )
}
