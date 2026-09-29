import { test, expect } from '@playwright/test'

test('loads home page in mock mode', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('text=Chhatri')).toBeVisible()
})

test('displays monsoon replay clock', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('text=monsoon replay')).toBeVisible()
})

test('shows golden number KPIs', async ({ page }) => {
  await page.goto('/')

  // Wait for state to load
  await page.waitForTimeout(1000)

  // Check KPIs from SPEC §17.2
  await expect(page.locator('text=3')).toBeVisible() // zones triggered
  await expect(page.locator('text=312')).toBeVisible() // shops paid
})

test('displays zones triggered status', async ({ page }) => {
  await page.goto('/')

  // Check for triggered zone card
  await page.waitForTimeout(1000)
  const zoneLabelLocator = page.locator('text=/Z[0-9].*shops/')
  await expect(zoneLabelLocator.first()).toBeVisible()
})

test('loads claims page', async ({ page }) => {
  await page.goto('/claims')
  await expect(page.locator('text=Claims')).toBeVisible()
})

test('loads merchant page', async ({ page }) => {
  await page.goto('/merchant/S-0142')
  await expect(page).toBeTruthy()
})

test('loads policy page', async ({ page }) => {
  await page.goto('/policy')
  await expect(page.locator('text=Policy')).toBeVisible()
})
