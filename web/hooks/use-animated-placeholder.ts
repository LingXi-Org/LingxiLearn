import { useEffect, useRef, useState } from 'react'

const PLACEHOLDER_PREFIX = '输入灵犀学习主题：'
const PLACEHOLDER_SUFFIXES = [
  '梳理一个复杂概念…',
  '生成一份课程讲义…',
  '检测我的知识掌握情况…',
  '把知识点可视化…',
] as const

const TYPE_SPEED_MS = 60
const DELETE_SPEED_MS = 35
const PAUSE_AFTER_TYPING_MS = 2000
const PAUSE_AFTER_DELETING_MS = 400

export function useAnimatedPlaceholder(enabled = true): string {
  const [text, setText] = useState(PLACEHOLDER_PREFIX)
  const stateRef = useRef({
    suffixIndex: 0,
    charIndex: 0,
    phase: 'typing' as 'typing' | 'paused' | 'deleting' | 'waiting',
  })

  useEffect(() => {
    if (!enabled) return

    const tick = () => {
      const state = stateRef.current
      const suffix = PLACEHOLDER_SUFFIXES[state.suffixIndex]

      switch (state.phase) {
        case 'typing':
          state.charIndex += 1
          setText(PLACEHOLDER_PREFIX + suffix.slice(0, state.charIndex))
          if (state.charIndex >= suffix.length) {
            state.phase = 'paused'
            return PAUSE_AFTER_TYPING_MS
          }
          return TYPE_SPEED_MS
        case 'paused':
          state.phase = 'deleting'
          return DELETE_SPEED_MS
        case 'deleting':
          state.charIndex -= 1
          setText(PLACEHOLDER_PREFIX + suffix.slice(0, state.charIndex))
          if (state.charIndex <= 0) {
            state.phase = 'waiting'
            return PAUSE_AFTER_DELETING_MS
          }
          return DELETE_SPEED_MS
        case 'waiting':
          state.suffixIndex = (state.suffixIndex + 1) % PLACEHOLDER_SUFFIXES.length
          state.charIndex = 0
          state.phase = 'typing'
          return TYPE_SPEED_MS
      }
    }

    let timer: ReturnType<typeof setTimeout>
    const schedule = () => {
      timer = setTimeout(schedule, tick())
    }
    timer = setTimeout(schedule, TYPE_SPEED_MS)

    return () => clearTimeout(timer)
  }, [enabled])

  return enabled ? text : PLACEHOLDER_PREFIX
}
