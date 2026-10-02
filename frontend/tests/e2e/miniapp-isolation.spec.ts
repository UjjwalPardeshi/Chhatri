/**
 * Mini-app isolation (design-system 13.6, AC-05; card 7.1 leftover). Run with the flag on:
 * `E2E_FEATURES=n1_miniapp npx playwright test --project=mock miniapp-isolation`.
 * 1. The console's computed styles on /claims are equal before and after the lazy mini-app chunk (and its Tailwind CSS) loaded.
 * 2. Under prefers-reduced-motion an `animate-in duration-ui` element inside the mini-app computes 1 ms or less.
 * Navigation stays in-app because a full reload restarts the mock backend.
 */
import { expect, test, type Page } from '@playwright/test'

const FLAG_ON = (process.env.E2E_FEATURES ?? '').split(',').map((name) => name.trim()).includes('n1_miniapp')

test.skip(!FLAG_ON, 'the mini-app is behind n1_miniapp: run with E2E_FEATURES=n1_miniapp')

const PROPS = ['color', 'background-color', 'font-family', 'font-size', 'font-weight', 'line-height', 'letter-spacing', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'margin-top', 'margin-bottom', 'border-top-width', 'border-top-color', 'border-radius', 'box-shadow', 'display', 'text-transform']
const SELECTORS = ['.btn', 'h1', '.table', '.card', '.badge']

type Styles = Record<string, Record<string, string> | null>

async function consoleStyles(page: Page): Promise<Styles> {
  return page.evaluate(
    ({ selectors, props }) => {
      const out: Record<string, Record<string, string> | null> = {}
      for (const selector of selectors) {
        const el = document.querySelector(selector)
        if (!el) {
          out[selector] = null
          continue
        }
        const computed = getComputedStyle(el)
        out[selector] = Object.fromEntries(props.map((prop) => [prop, computed.getPropertyValue(prop)]))
      }
      return out
    },
    { selectors: SELECTORS, props: PROPS },
  )
}

async function openClaims(page: Page): Promise<void> {
  await page.getByRole('link', { name: /^claims/i }).first().click()
  await expect(page).toHaveURL(/\/claims/)
  await expect(page.locator('.app')).toBeVisible()
}

test('the console keeps its computed styles on /claims after the mini-app chunk has loaded', async ({ page }) => {
  await page.goto('/claims?lang=en')
  await expect(page.locator('.app')).toBeVisible()
  await expect(page.locator('h1').first()).toBeVisible()
  const before = await consoleStyles(page)
  expect(Object.values(before).filter((found) => found !== null).length).toBeGreaterThan(0)

  await page.getByRole('link', { name: /merchant phone/i }).first().click()
  await expect(page.getByTestId('screen-home')).toBeVisible()
  await expect(page.getByTestId('app-root')).toHaveClass(/miniapp/)
  await openClaims(page)
  await expect(page.locator('h1').first()).toBeVisible()

  expect(await consoleStyles(page)).toEqual(before)
})

test.describe('with reduced motion on', () => {
  test.use({ reducedMotion: 'reduce' })

  test('an animate-in element inside the mini-app runs in 1 ms or less', async ({ page }) => {
    await page.goto('/merchant/S-0142/app?lang=en')
    await expect(page.getByTestId('screen-home')).toBeVisible()
    const timing = await page.evaluate(() => {
      const root = document.querySelector('.miniapp')
      if (!root) throw new Error('no .miniapp root')
      const probe = document.createElement('div')
      probe.className = 'animate-in duration-ui fade-in'
      root.appendChild(probe)
      const computed = getComputedStyle(probe)
      const result = { animation: computed.animationDuration, transition: computed.transitionDuration }
      probe.remove()
      return result
    })
    const seconds = [...timing.animation.split(','), ...timing.transition.split(',')].map((part) => Number.parseFloat(part))
    for (const value of seconds) expect(value).toBeLessThanOrEqual(0.001)
  })
})
