/**
 * SSE transport for durable event streams.
 *
 * Single owner of reconnect logic, Last-Event-ID tracking, and heartbeat
 * tolerance. Independent from JSON transport (issue #40).
 *
 * The server replays from a durable log, so reconnecting with the last
 * sequence we saw resumes exactly where we left off — no gap, no duplicates.
 */

import { authorizedFetch, apiUrl } from './http'

export type SseOptions = { from?: number; onEnd?: (status: string) => void }

/**
 * Fetch-based SSE keeps the existing durable-log replay contract while sending
 * the same HttpOnly session cookie as normal API calls.
 */
export function subscribeSse<T extends { sequence?: number }>(
  path: string,
  onEvent: (event: T) => void,
  options: SseOptions = {}
): () => void {
  let closed = false
  let finished = false
  let controller: AbortController | null = null
  let retry: ReturnType<typeof setTimeout> | null = null
  let lastSequence = options.from ?? 0

  const scheduleReconnect = () => {
    if (!closed && !finished && !retry) {
      retry = setTimeout(() => {
        retry = null
        void connect()
      }, 1200)
    }
  }

  const dispatch = (eventName: string, data: string) => {
    if (!data) return
    if (eventName === 'stream.end') {
      try {
        const payload = JSON.parse(data) as { status?: string }
        options.onEnd?.(payload.status ?? 'unknown')
      } catch {
        options.onEnd?.('unknown')
      }
      finished = true
      return
    }
    try {
      const event = JSON.parse(data) as T
      if (typeof event.sequence === 'number') lastSequence = event.sequence
      onEvent(event)
    } catch {
      /* Ignore malformed frames rather than losing the stream. */
    }
  }

  const connect = async () => {
    if (closed || finished) return
    controller = new AbortController()
    try {
      const separator = path.includes('?') ? '&' : '?'
      const response = await authorizedFetch(
        apiUrl(`${path}${separator}last_event_id=${lastSequence}`),
        {
          signal: controller.signal,
          headers: {
            Accept: 'text/event-stream',
            'Last-Event-ID': String(lastSequence),
          },
        }
      )
      if (!response.ok || !response.body) {
        if (response.status === 401 || response.status === 403 || response.status === 404) {
          finished = true
          return
        }
        scheduleReconnect()
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let eventName = 'message'
      let dataLines: string[] = []

      const consumeLine = (line: string) => {
        if (line === '') {
          dispatch(eventName, dataLines.join('\n'))
          eventName = 'message'
          dataLines = []
          return
        }
        if (line.startsWith(':')) return
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''))
      }

      while (!closed && !finished) {
        const chunk = await reader.read()
        if (chunk.done) {
          buffer += decoder.decode()
          if (buffer) consumeLine(buffer)
          break
        }
        buffer += decoder.decode(chunk.value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) consumeLine(line.replace(/\r$/, ''))
      }
      reader.releaseLock()
      if (!closed && !finished) scheduleReconnect()
    } catch (cause) {
      if (!closed && !(cause instanceof DOMException && cause.name === 'AbortError')) {
        scheduleReconnect()
      }
    } finally {
      controller = null
    }
  }

  void connect()
  return () => {
    closed = true
    if (retry) clearTimeout(retry)
    retry = null
    controller?.abort()
  }
}
