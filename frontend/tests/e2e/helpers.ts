/** Shared steps for the console smoke suite (SPEC §22; runs in mock and live projects). */
import { expect, type Page } from '@playwright/test'

export const IS_MOCK = !process.env.CONSOLE_URL
/** Test hooks of the mock backend (set in src/main.tsx). */
export const MOCK_HOOK = '__chhatriMock'
export const FONT_HOSTS = /fonts\.googleapis\.com|fonts\.gstatic\.com/

/** Opens the console once; every later step navigates in-app (a reload restarts the mock). */
export async function openConsole(page: Page, path = '/live'): Promise<void> {
  await page.goto(path)
  await expect(page.locator('.clock-label')).toContainText('Mumbai')
}

export async function loadScenario(page: Page, value: string, clockText: string): Promise<void> {
  await page.getByRole('combobox', { name: 'Scenario' }).selectOption(value)
  await expect(page.locator('.clock-label')).toContainText(clockText)
}

export async function seek(page: Page, hhmm: string): Promise<void> {
  const input = page.getByRole('textbox', { name: 'Seek to time (HH:MM)' })
  await input.fill(hhmm)
  await page.getByRole('button', { name: 'Seek', exact: true }).click()
  await expect(page.locator('.clock-label')).toContainText(hhmm)
}

export async function goTo(page: Page, link: string): Promise<void> {
  await page.getByRole('navigation', { name: 'Pages' }).getByRole('link', { name: link, exact: false }).click()
}
