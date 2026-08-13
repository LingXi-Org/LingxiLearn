'use client'

import { useEffect } from 'react'
import { useParams } from 'next/navigation'
import { useAnimatedPlaceholder } from '@/hooks/use-animated-placeholder'

interface AnimatedPlaceholderEffectProps {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  isInitialView: boolean
}

export function AnimatedPlaceholderEffect({
  textareaRef,
  isInitialView,
}: AnimatedPlaceholderEffectProps) {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const animatedPlaceholder = useAnimatedPlaceholder(isInitialView)
  const placeholder =
    workspaceId === 'lingxi'
      ? isInitialView
        ? '输入知识点或学习目标…'
        : '继续追问这个知识点…'
      : isInitialView
        ? animatedPlaceholder
        : 'Send message to Sim'

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.placeholder = placeholder
    }
  }, [placeholder, textareaRef])

  return null
}
