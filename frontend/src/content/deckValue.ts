/**
 * Deck slides 10 (USP) and 11 (who benefits), exact wording. The USP table compares Chhatri with a
 * traditional merchant claim and weather-only cover; its sources are the deck's.
 */

export const USP = Object.freeze({
  title: 'What Chhatri adds to merchant insurance',
  columns: ['Traditional merchant claim', 'Weather-only cover', 'Chhatri'] as const,
  rows: [
    { label: 'What starts the claim', cells: ['The merchant files it', 'A weather reading', 'The shop’s own sales data'] },
    { label: 'Proof needed', cells: ['Bills, photos and forms', 'None', 'None for area events; one photo for personal ones'] },
    { label: 'Matches the real loss', cells: ['Assessed case by case', 'Often not: a one-in-three chance of missing a total loss in one study', 'Measured from actual sales'] },
    { label: 'Time to money', cells: ['30–60 days (Paytm’s earlier plans)', 'Weeks (SEWA heat cover)', 'Same day'] },
    { label: 'Loan instalment on a bad day', cells: ['Still due', 'Still due', 'Paused automatically'] },
    { label: 'Hard to game', cells: ['Documents can be faked', 'Yes', 'Area-level trigger, KYC and date checks, waiting period'] },
  ] as const,
  caption: 'Chhatri doesn’t replace Paytm’s merchant plan. It gives it claims that start themselves.',
  sources: 'Sources: Assurekit-Paytm case study; NPR, Jul 2025; Clarke et al. 2012, via Cornell NEUDC',
})

export const BENEFITS: readonly { who: string; what: string }[] = [
  { who: 'Merchants', what: 'Money on the day they lose it, no forms, and no instalment squeeze' },
  { who: 'Insurer', what: 'Losses measured, not guessed, and far cheaper claims to run' },
  { who: 'Paytm', what: 'More merchants who renew, more insurance revenue, fewer missed instalments' },
]
