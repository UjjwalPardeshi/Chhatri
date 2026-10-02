/**
 * `<Copy k="home.title" />`: a string in the language shown, in its own element. A string that fell back to another
 * language (Marathi to Hindi to English, fs-04 section 13) carries that language in its own `lang`, so the browser
 * shapes it and a screen reader reads it right (AC-33). A string in the language shown carries none: the root has it.
 */
import type { ComponentProps, ElementType } from 'react'

import { useMiniapp } from '../shell/MiniappContext'
import { translate, type CopyKey, type CopyParams } from './copy'

type CopyProps<Tag extends ElementType> = { k: CopyKey; params?: CopyParams; as?: Tag } & Omit<ComponentProps<Tag>, 'children' | 'lang'>

export function Copy<Tag extends ElementType = 'span'>({ k, params, as, ...rest }: CopyProps<Tag>) {
  const { lang } = useMiniapp()
  const { text, lang: from, fallback } = translate(k, lang, params)
  const Component: ElementType = as ?? 'span'
  return (
    <Component lang={fallback ? from : undefined} {...rest}>
      {text}
    </Component>
  )
}
