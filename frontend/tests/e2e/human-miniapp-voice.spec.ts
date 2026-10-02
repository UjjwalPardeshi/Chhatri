/**
 * A person asks by voice (fs-05 section 11, n4_voice) with the browser's speech recogniser faked: the first-use notice,
 * the heard text in the box, the amount chip that must be confirmed before Send, an edit that makes a new chip, and
 * no mic at all while the flag is off. `E2E_FEATURES=... npx playwright test --project=mock human-miniapp-voice`.
 */
import { expect, test } from '@playwright/test'

import { anilAt1705, APP, fakeSpeech, goWithin, guardErrors, has } from './human-miniapp-helpers'

test.skip(!has('n1_miniapp') || !has('n2_ask_chhatri'), 'needs n1_miniapp and n2_ask_chhatri')
test.use({ viewport: { width: 390, height: 844 } })

test.describe('with n4_voice on', () => {
  test.skip(!has('n4_voice'), 'needs n4_voice')

  test('the notice comes first and Cancel records nothing', async ({ page }) => {
    await fakeSpeech(page, 'What is covered?')
    await page.goto(`${APP}?lang=en&screen=ask`)
    await page.getByTestId('voice-mic').click()
    await expect(page.getByTestId('voice-notice')).toBeVisible()
    await page.getByTestId('voice-notice-cancel').click()
    await expect(page.getByTestId('voice-notice')).toHaveCount(0)
    await expect(page.getByTestId('ask-input')).toHaveValue('')
    await expect(page.getByTestId('voice-status')).not.toContainText(/listening/i)
  })

  test('an amount heard must be confirmed before Send; the confirmed question opens one case', async ({ page }) => {
    const errors = guardErrors(page)
    await fakeSpeech(page, 'मेरा नुकसान ढाई हज़ार का हुआ')
    await anilAt1705(page)
    await goWithin(page, '/merchant/S-0142/app?lang=hi&screen=ask')
    await page.getByTestId('voice-mic').click()
    await page.getByTestId('voice-notice-continue').click()
    await expect(page.getByTestId('voice-status')).toContainText('सुन रहे हैं')
    await page.getByTestId('voice-mic').click()
    await expect(page.getByTestId('ask-input')).toHaveValue('मेरा नुकसान ढाई हज़ार का हुआ')
    await expect(page.getByTestId('ask-send')).toBeDisabled()
    await expect(page.getByTestId('ask-send-hint')).toBeVisible()
    await expect(page.getByTestId(/^voice-chip-/).first()).toContainText('₹2,500')
    await page.getByTestId(/^voice-chip-right-/).first().click()
    await expect(page.getByTestId('ask-send')).toBeEnabled()
    await page.getByTestId('ask-send').click()
    await expect(page.getByTestId('ask-answer')).toContainText(/C-\d+/)
    expect(errors).toEqual([])
  })

  test('editing the heard text to add an amount needs a new confirmation', async ({ page }) => {
    await fakeSpeech(page, 'मेरा नुकसान ढाई हज़ार का हुआ')
    await anilAt1705(page)
    await goWithin(page, '/merchant/S-0142/app?lang=hi&screen=ask')
    await page.getByTestId('voice-mic').click()
    await page.getByTestId('voice-notice-continue').click()
    await page.getByTestId('voice-mic').click()
    await page.getByTestId(/^voice-chip-right-/).first().click()
    await expect(page.getByTestId('ask-send')).toBeEnabled()
    await page.getByTestId('ask-input').fill('मेरा नुकसान 3000 रुपये का हुआ')
    await expect(page.getByTestId('ask-send')).toBeDisabled()
    await expect(page.getByTestId(/^voice-chip-/).first()).toContainText('₹3,000')
  })
})

test.describe('with n4_voice off', () => {
  test.skip(has('n4_voice'), 'only when n4_voice is off')
  test('there is no mic and no voice notice', async ({ page }) => {
    await fakeSpeech(page, 'What is covered?')
    await page.goto(`${APP}?lang=en&screen=ask`)
    await expect(page.getByTestId('ask-input')).toBeVisible()
    await expect(page.getByTestId('voice-mic')).toHaveCount(0)
    await expect(page.getByTestId('voice-status')).toHaveCount(0)
  })
})
