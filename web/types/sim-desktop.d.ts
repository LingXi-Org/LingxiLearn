import type { SimDesktopApi } from '@/lib/desktop/bridge'

declare global {
  interface Window {
    simDesktop?: SimDesktopApi
  }
}
