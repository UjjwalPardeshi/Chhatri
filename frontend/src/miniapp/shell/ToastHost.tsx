/**
 * The one toast host of the mini-app (`app-toast-host`, design system 5.2): a sonner `Toaster` inside `.miniapp`, so a
 * toast stays in the phone frame (`contain: layout` confines it). A screen calls `toast(...)` and shows the result of
 * the action on the page as well; the toast is a polite live region and stays six seconds, pausing on hover and focus.
 */
import { Toaster } from '../ui/sonner'

/** The app bar is 56 px high: a toast sits just under it, on a phone and in the frame alike (sonner has one offset for each). */
const APP_BAR_CLEARANCE_PX = 64
const TOAST_MS = 6000

export function ToastHost() {
  return (
    <div data-testid="app-toast-host">
      <Toaster position="top-center" offset={APP_BAR_CLEARANCE_PX} mobileOffset={APP_BAR_CLEARANCE_PX} duration={TOAST_MS} />
    </div>
  )
}
