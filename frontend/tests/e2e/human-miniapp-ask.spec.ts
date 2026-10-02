/**
 * A person talks to Ask Chhatri (fs-05, n2_ask_chhatri): suggestions, a typed question, an answer with clause chips and
 * sources, the scam warning, explain-first (a bigger-loss question opens one case, not two), the next action, empty and
 * double-click input, offline and a lost connection. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-ask`.
 */
import { expect, test, type Page } from '@playwright/test'

import { anilAt1705, APP, expectCleanScreen, goWithin, guardErrors, has, outage } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp') || !has('n2_ask_chhatri'), 'needs n1_miniapp and n2_ask_chhatri')
test.use({ viewport: { width: 390, height: 844 } })

async function ask(page: Page, question: string): Promise<void> {
  await page.getByTestId('ask-input').fill(question)
  await page.getByTestId('ask-send').click()
}

test('a fresh merchant sees only questions that apply, and a typed question gets a sourced answer', async ({ page }) => {
  const errors = guardErrors(page)
  await page.goto(`${APP}?lang=en&screen=ask`)
  await expect(page.getByTestId('screen-ask')).toHaveAttribute('data-state', 'empty')
  await expect(page.getByTestId('ask-suggest').filter({ hasText: 'Why did I get this amount?' })).toHaveCount(0)
  await expect(page.getByTestId('ask-send')).toBeDisabled()
  await ask(page, 'What is the waiting period?')
  const answer = page.getByTestId('ask-answer')
  await expect(answer).toContainText('7 days')
  await expect(page.getByTestId('ask-clause').first()).toContainText('C5')
  await expect(page.getByTestId('ask-footer')).toContainText('SIMULATED')
  await expect(page.getByTestId('ask-input')).toHaveValue('')
  await expectCleanScreen(page)
  expect(errors).toEqual([])
})

test('whitespace only cannot be sent, and a double click sends one question', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await page.getByTestId('ask-input').fill('   ')
  await expect(page.getByTestId('ask-send')).toBeDisabled()
  await page.getByTestId('ask-input').fill('What is covered?')
  await page.getByTestId('ask-send').dblclick()
  await expect(page.getByTestId('ask-answer')).toHaveCount(1)
  await expect(page.getByTestId('ask-entry')).toHaveCount(1)
})

test('a question over 500 characters shows the counter and cannot be sent', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await page.getByTestId('ask-input').fill('a'.repeat(501))
  await expect(page.getByTestId('ask-counter')).toContainText('501/500')
  await expect(page.getByTestId('ask-send')).toBeDisabled()
  await page.getByTestId('ask-input').fill('a'.repeat(500))
  await expect(page.getByTestId('ask-send')).toBeEnabled()
})

test('a scam message gets the warning, not an answer, and the person can ask again', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await ask(page, 'Someone called and asked for my OTP to pay my claim')
  await expect(page.getByTestId('ask-scam')).toContainText('scam')
  await expect(page.getByTestId('ask-answer')).toContainText(/does not ask for your OTP/i)
  await expect(page.getByTestId('ask-next')).toContainText('Ask another question')
})

test('a question Chhatri cannot answer is handed to the team, never guessed', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await ask(page, 'can you give me a loan')
  await expect(page.getByTestId('ask-answer')).toContainText("don't have an answer")
  await expect(page.getByTestId('ask-next')).toContainText('Talk to the team')
})

test('after a payout: why shows the formula with sources; bigger loss opens one case even when asked twice', async ({ page }) => {
  const errors = guardErrors(page)
  await anilAt1705(page)
  await goWithin(page, '/merchant/S-0142/app?lang=en&screen=ask')
  await page.getByTestId('ask-suggest').filter({ hasText: 'Why did I get this amount?' }).click()
  await expect(page.getByTestId('ask-answer-text')).toContainText('½ × ₹4,380 × 63% = ₹1,380')
  await expect(page.getByTestId('ask-facts')).toContainText('SIMULATED')
  await expect(page.getByTestId('ask-clause').first()).toContainText('C4')
  await ask(page, 'My loss was bigger')
  await expect(page.getByTestId('ask-answer-text').last()).toContainText("I'm sending this to our team")
  const chip = await page.getByTestId('ask-answer').last().innerText()
  const caseId = /case (C-\d+)/.exec(chip)?.[1]
  expect(caseId).toBeTruthy()
  await ask(page, 'My loss was bigger')
  await expect(page.getByTestId('ask-answer').last()).toContainText(`already with our team`)
  await expect(page.getByTestId('ask-answer').last()).toContainText(`case ${caseId}`)
  await page.getByTestId('ask-next').last().click()
  await expect(page).toHaveURL(/screen=claims/)
  expect(errors).toEqual([])
})

test('offline: the composer says so and Send is off; online again it recovers', async ({ page, context }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await expect(page.getByTestId('screen-ask')).toHaveAttribute('data-state', 'empty')
  await page.getByTestId('ask-input').fill('What is covered?')
  await context.setOffline(true)
  await expect(page.getByTestId('ask-offline')).toBeVisible()
  await expect(page.getByTestId('ask-send')).toBeDisabled()
  await expect(page.getByTestId('ask-input')).toHaveValue('What is covered?')
  await context.setOffline(false)
  await expect(page.getByTestId('ask-offline')).toHaveCount(0)
  await expect(page.getByTestId('ask-send')).toBeEnabled()
})

test('a lost connection keeps the typed text and Try again works', async ({ page }) => {
  await page.goto(`${APP}?lang=en&screen=ask`)
  await expect(page.getByTestId('screen-ask')).toHaveAttribute('data-state', 'empty')
  await outage(page, 1500)
  await ask(page, 'What is covered?')
  await expect(page.getByTestId('ask-failed')).toBeVisible()
  await expect(page.getByTestId('ask-input')).toHaveValue('What is covered?')
  await expect.poll(async () => { await page.getByTestId('ask-retry').click(); return page.getByTestId('ask-answer').count() }, { timeout: 8000 }).toBe(1)
})

test('Hindi: the box, the suggestions and an answer are in Hindi', async ({ page }) => {
  await page.goto(`${APP}?lang=hi&screen=ask`)
  await expect(page.getByTestId('ask-suggest').first()).toContainText(/[ऀ-ॿ]/)
  await ask(page, 'वेटिंग पीरियड क्या है?')
  await expect(page.getByTestId('ask-answer-text')).toContainText(/[ऀ-ॿ]/)
  await expectCleanScreen(page)
})
