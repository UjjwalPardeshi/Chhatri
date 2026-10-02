/**
 * The amount and date finder of the voice route (data-model 5.11, fs-05 section 11.4), a fixed lookup and never a
 * guess: digits, Hindi and English number words, सौ, हज़ार, लाख, डेढ़, ढाई, सवा, and dates such as "19 August". A
 * phrase it cannot turn into a value comes back with `value` null, so the screen asks the merchant to type it. The
 * word कल means yesterday or tomorrow, so it is a date with no value and the merchant chooses.
 */
import type { Mention } from '../miniapp/api/ask'
import { formatInr } from '../lib/money'

const UNITS: Readonly<Record<string, number>> = {
  एक: 1, दो: 2, तीन: 3, चार: 4, पाँच: 5, पांच: 5, छह: 6, छः: 6, सात: 7, आठ: 8, नौ: 9, दस: 10, बीस: 20, तीस: 30, चालीस: 40, पचास: 50, साठ: 60, सत्तर: 70, अस्सी: 80, नब्बे: 90,
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
}
const SCALES: Readonly<Record<string, number>> = { सौ: 100, hundred: 100, हज़ार: 1_000, हजार: 1_000, thousand: 1_000, लाख: 100_000, lakh: 100_000 }
const FRACTIONS: Readonly<Record<string, number>> = { डेढ़: 1.5, ढाई: 2.5, सवा: 1.25 }
const CURRENCY = new Set(['रुपये', 'रुपए', 'रुपया', 'rupees', 'rupee', 'rs', 'rs.', '₹'])
const MONTHS: Readonly<Record<string, number>> = {
  january: 1, february: 2, march: 3, april: 4, may: 5, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12,
  जनवरी: 1, फ़रवरी: 2, फरवरी: 2, मार्च: 3, अप्रैल: 4, मई: 5, जून: 6, जुलाई: 7, अगस्त: 8, सितंबर: 9, सितम्बर: 9, अक्टूबर: 10, नवंबर: 11, नवम्बर: 11, दिसंबर: 12, दिसम्बर: 12,
}
const MONTH_NAMES_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const KAL = new Set(['कल', 'kal'])
/** The deck's voice.chip.kal.ask: the server never guesses which day कल means. */
const KAL_CHIP_HI = 'आपका मतलब बीता हुआ कल था या आने वाला कल?'
const KAL_CHIP_EN = 'Did you mean yesterday or tomorrow?'
const DATE_PATTERN = /(\d{1,2})\s*(?:th|st|nd|rd)?\s+([\p{L}\p{M}]+)/gu

const pad = (n: number): string => String(n).padStart(2, '0')
const isWord = (token: string): boolean => token in UNITS || token in SCALES || token in FRACTIONS

type Draft = Omit<Mention, 'id'>

function dateMention(day: number, month: number, year: number, heard: string): Draft {
  const label = `${day} ${MONTH_NAMES_EN[month - 1]}`
  return { kind: 'date', heard, value: label, value_paise: null, value_date: `${year}-${pad(month)}-${pad(day)}`, chip_hi: '', chip_en: '' }
}

/** The dates written as day and month name, and the text with them cut out so their digits are not read as money. */
function findDates(text: string, year: number): { drafts: { at: number; draft: Draft }[]; rest: string } {
  const drafts: { at: number; draft: Draft }[] = []
  const rest = text.replace(DATE_PATTERN, (whole: string, day: string, name: string, at: number) => {
    const month = MONTHS[name.toLowerCase()]
    const d = Number(day)
    if (month === undefined || d < 1 || d > 31) return whole
    drafts.push({ at, draft: dateMention(d, month, year, whole.trim()) })
    return ' '.repeat(whole.length)
  })
  return { drafts, rest }
}

/** One run of number words, for example "डेढ़ हज़ार": the rupees it names, or null when it names none. */
function wordsValue(tokens: readonly string[]): number | null {
  let total = 0
  let current = 0
  let fraction = 1
  for (const token of tokens) {
    if (token in FRACTIONS) fraction = FRACTIONS[token]
    else if (token in UNITS) current += UNITS[token]
    else if (token === 'सौ' || token === 'hundred') current = (current || fraction) * 100
    else {
      total += (current || fraction) * SCALES[token]
      current = 0
    }
    if (token in SCALES) fraction = 1
  }
  const value = total + current
  const lone = tokens.length === 1 && (tokens[0] in FRACTIONS)
  return lone || value <= 0 ? null : Math.round(value)
}

function amountDraft(heard: string, rupees: number | null): Draft {
  return { kind: 'amount', heard, value: rupees === null ? null : formatInr(rupees * 100), value_paise: rupees === null ? null : rupees * 100, value_date: null, chip_hi: '', chip_en: '' }
}

function findAmounts(text: string): { at: number; draft: Draft }[] {
  const found: { at: number; draft: Draft }[] = []
  const tokens = [...text.matchAll(/[^\s,।?!]+/gu)].map((m) => ({ word: m[0].toLowerCase(), raw: m[0], at: m.index }))
  for (let i = 0; i < tokens.length; i += 1) {
    const digits = /^₹?(\d+(?:\.\d+)?)$/.exec(tokens[i].word.replaceAll(',', ''))
    if (digits) {
      const rupees = Number(digits[1])
      found.push({ at: tokens[i].at, draft: amountDraft(tokens[i].raw, Number.isInteger(rupees) ? rupees : null) })
    } else if (isWord(tokens[i].word)) {
      let end = i
      while (end + 1 < tokens.length && isWord(tokens[end + 1].word)) end += 1
      const run = tokens.slice(i, end + 1)
      const withMoney = CURRENCY.has(tokens[end + 1]?.word ?? '')
      const hasScale = run.some((t) => t.word in SCALES || t.word in FRACTIONS)
      if (hasScale || withMoney) found.push({ at: tokens[i].at, draft: amountDraft(run.map((t) => t.raw).join(' '), wordsValue(run.map((t) => t.word))) })
      i = end
    }
  }
  return found
}

function chip(draft: Draft): Draft {
  if (draft.value === null) return { ...draft, chip_hi: `आपने कहा: "${draft.heard}"। कृपया संख्या लिखकर बताइए।`, chip_en: `You said "${draft.heard}". Please type the number.` }
  return { ...draft, chip_hi: `${draft.value} — सही है?`, chip_en: `${draft.value} — is that right?` }
}

/** Every amount and date of `text` in the order they were said, numbered m1, m2 and so on. `year` completes a date. */
export function findMentions(text: string, year: number): Mention[] {
  const { drafts, rest } = findDates(text, year)
  const kal = [...rest.matchAll(/[^\s,।?!]+/gu)]
    .filter((m) => KAL.has(m[0].toLowerCase()))
    .map((m) => ({ at: m.index, draft: { kind: 'date', heard: m[0], value: null, value_paise: null, value_date: null, chip_hi: KAL_CHIP_HI, chip_en: KAL_CHIP_EN } as Draft }))
  return [...drafts, ...findAmounts(rest), ...kal]
    .toSorted((a, b) => a.at - b.at)
    .map(({ draft }, i) => ({ id: `m${i + 1}`, ...(draft.kind === 'date' && draft.value === null ? draft : chip(draft)) }))
}
