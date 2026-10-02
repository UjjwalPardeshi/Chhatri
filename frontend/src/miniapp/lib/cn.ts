import { createCn } from 'cn/config'

/**
 * `cn` (class joining plus Tailwind conflict resolution) that knows the mini-app's own text sizes. The stock `cn`
 * reads `text-caption` and `text-field` as colours, so `cn('text-caption', 'text-paid-ink')` would drop the size.
 */
export const cn = createCn({
  extend: { classGroups: { 'font-size': [{ text: ['2xs', 'caption', 'field', 'md'] }] } },
})
