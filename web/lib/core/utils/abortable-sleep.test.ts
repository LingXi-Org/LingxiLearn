/**
 * @vitest-environment node
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sleepUntilAborted } from '@/lib/core/utils/abortable-sleep'

describe('sleepUntilAborted', () => {
	beforeEach(() => {
		vi.useFakeTimers()
	})

	afterEach(() => {
		vi.useRealTimers()
	})

	it('resolves after the specified delay', async () => {
		const promise = sleepUntilAborted(1000, new AbortController().signal)

		vi.advanceTimersByTime(999)
		let resolved = false
		void promise.then(() => {
			resolved = true
		})
		await Promise.resolve()
		expect(resolved).toBe(false)

		vi.advanceTimersByTime(1)
		await expect(promise).resolves.toBeUndefined()
	})

	it('resolves immediately when the signal aborts', async () => {
		const controller = new AbortController()
		const promise = sleepUntilAborted(1000, controller.signal)

		controller.abort()

		await expect(promise).resolves.toBeUndefined()
		expect(vi.getTimerCount()).toBe(0)
	})

	it('resolves immediately for an already-aborted signal', async () => {
		const controller = new AbortController()
		controller.abort()

		await expect(sleepUntilAborted(1000, controller.signal)).resolves.toBeUndefined()
		expect(vi.getTimerCount()).toBe(0)
	})
})
