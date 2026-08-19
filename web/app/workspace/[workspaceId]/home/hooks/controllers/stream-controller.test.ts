import { describe, expect, it, vi } from 'vitest'
import type { AgentTaskEvent } from '@/lib/lingxi/types'
import { createStreamController } from './stream-controller'

const event = (sequence: number) => ({ sequence }) as AgentTaskEvent

describe('createStreamController', () => {
  it('subscribes before catch-up, advances the durable cursor, and orders rows', async () => {
    let tick: (() => Promise<void>) | undefined
    let live: ((row: AgentTaskEvent) => void) | undefined
    const seen: number[] = []
    const catchUpV1 = vi.fn(async () => [event(4), event(3)])
    const controller = createStreamController({
      subscribeV0: vi.fn(() => vi.fn()),
      subscribeV1: vi.fn((_from, apply) => {
        live = apply
        return vi.fn()
      }),
      catchUpV1,
      setInterval: ((callback: () => Promise<void>) => {
        tick = callback
        return 1
      }) as unknown as typeof globalThis.setInterval,
      clearInterval: vi.fn(),
    })

    controller.startV1((row) => seen.push(row.sequence))
    live?.(event(2))
    await tick?.()

    expect(catchUpV1).toHaveBeenCalledWith(2)
    expect(seen).toEqual([2, 3, 4])
  })

  it('owns and closes both subscriptions and the catch-up timer', () => {
    const unsubscribeV0 = vi.fn()
    const unsubscribeV1 = vi.fn()
    const clearInterval = vi.fn()
    const controller = createStreamController({
      subscribeV0: vi.fn(() => unsubscribeV0),
      subscribeV1: vi.fn(() => unsubscribeV1),
      catchUpV1: vi.fn(async () => []),
      setInterval: (() => 7) as unknown as typeof globalThis.setInterval,
      clearInterval: clearInterval as unknown as typeof globalThis.clearInterval,
    })

    controller.startV1(vi.fn())
    controller.startV0(9, vi.fn(), vi.fn())
    controller.stop()

    expect(unsubscribeV0).toHaveBeenCalledOnce()
    expect(unsubscribeV1).toHaveBeenCalledOnce()
    expect(clearInterval).toHaveBeenCalledWith(7)
  })
})
