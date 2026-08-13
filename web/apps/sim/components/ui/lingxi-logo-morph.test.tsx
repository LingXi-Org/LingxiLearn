/**
 * @vitest-environment jsdom
 */
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it } from 'vitest'
import { LingxiLogoMorph } from '@/components/ui'

afterEach(() => {
  document.body.replaceChildren()
})

describe('LingxiLogoMorph', () => {
  it('renders the production logo and three phase-shifted arc trails', () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const root = createRoot(host)

    act(() => {
      root.render(<LingxiLogoMorph size={28} />)
    })

    const svg = host.querySelector('svg')
    expect(svg?.getAttribute('width')).toBe('28')
    expect(svg?.getAttribute('height')).toBe('28')
    expect(host.querySelectorAll("g[class*='arcOrbit']")).toHaveLength(3)
    expect(host.querySelectorAll("g[class*='arcOrbit'] path")).toHaveLength(9)
    expect(host.querySelector("path[d^='M44.73 40.05']")).not.toBeNull()
    expect(svg?.getAttribute('aria-hidden')).toBe('true')

    act(() => {
      root.unmount()
    })
  })
})
