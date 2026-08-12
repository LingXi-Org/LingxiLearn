'use client'

import * as React from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { Sparkles } from 'lucide-react'
import type { NativeSkill } from '@/lib/types'
import { cn } from './lib/cn'

/**
 * Sim's slash-triggered skills integration. The workspace supplies the skill
 * catalog; menu focus, keyboard navigation, anchoring and selection behavior
 * follow Sim's native SkillsMenuDropdown contract.
 */
export interface SimSkillsMenuHandle {
  open: (anchor?: { left: number; top: number }) => void
  close: () => void
  moveActive: (delta: number) => void
  selectActive: () => boolean
}

interface SimSkillsMenuDropdownProps {
  skills: NativeSkill[]
  onSkillSelect: (skill: NativeSkill) => void
  onClose: () => void
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  pendingCursorRef: React.MutableRefObject<number | null>
  slashQuery?: string
}

export const SimSkillsMenuDropdown = React.memo(
  React.forwardRef<SimSkillsMenuHandle, SimSkillsMenuDropdownProps>(function SimSkillsMenuDropdown(
    { skills, onSkillSelect, onClose, textareaRef, pendingCursorRef, slashQuery },
    ref,
  ) {
    const [open, setOpen] = React.useState(false)
    const [anchorPos, setAnchorPos] = React.useState<{ left: number; top: number } | null>(null)
    const [activeIndex, setActiveIndex] = React.useState(0)
    const contentRef = React.useRef<HTMLDivElement>(null)

    const filteredSkills = React.useMemo(() => {
      const query = (slashQuery ?? '').toLocaleLowerCase().trim()
      if (!query) return skills
      return skills.filter((skill) =>
        `${skill.display_name} ${skill.id} ${skill.description}`.toLocaleLowerCase().includes(query),
      )
    }, [skills, slashQuery])

    const filteredSkillsRef = React.useRef(filteredSkills)
    filteredSkillsRef.current = filteredSkills
    const activeIndexRef = React.useRef(activeIndex)
    activeIndexRef.current = activeIndex

    const doOpen = React.useCallback((anchor?: { left: number; top: number }) => {
      if (anchor) setAnchorPos(anchor)
      setOpen(true)
      setActiveIndex(0)
    }, [])

    const doClose = React.useCallback(() => setOpen(false), [])

    const select = React.useCallback((skill: NativeSkill) => {
      onSkillSelect(skill)
      setOpen(false)
      setActiveIndex(0)
    }, [onSkillSelect])

    const selectRef = React.useRef(select)
    selectRef.current = select

    React.useImperativeHandle(ref, () => ({
      open: doOpen,
      close: doClose,
      moveActive: (delta) => {
        const items = filteredSkillsRef.current
        if (!items.length) return
        setActiveIndex((index) => {
          const next = index + delta
          return next < 0 ? items.length - 1 : next >= items.length ? 0 : next
        })
      },
      selectActive: () => {
        const items = filteredSkillsRef.current
        const skill = items[activeIndexRef.current] ?? items[0]
        if (!skill) return false
        selectRef.current(skill)
        return true
      },
    }), [doOpen, doClose])

    React.useEffect(() => setActiveIndex(0), [slashQuery])

    React.useEffect(() => {
      const row = contentRef.current?.querySelector<HTMLElement>(`[data-filtered-idx="${activeIndex}"]`)
      row?.scrollIntoView({ block: 'nearest' })
    }, [activeIndex, filteredSkills])

    const handleOpenChange = (nextOpen: boolean) => {
      setOpen(nextOpen)
      if (!nextOpen) {
        setAnchorPos(null)
        setActiveIndex(0)
        onClose()
      }
    }

    return (
      <DropdownMenuPrimitive.Root open={open} onOpenChange={handleOpenChange}>
        <DropdownMenuPrimitive.Trigger asChild>
          <div
            style={{
              position: 'fixed',
              left: anchorPos?.left ?? 0,
              top: anchorPos?.top ?? 0,
              width: 0,
              height: 0,
              pointerEvents: 'none',
            }}
          />
        </DropdownMenuPrimitive.Trigger>
        <DropdownMenuPrimitive.Portal>
          <DropdownMenuPrimitive.Content
            ref={contentRef}
            align='start'
            side='top'
            sideOffset={8}
            avoidCollisions
            collisionPadding={8}
            className='z-50 flex max-h-[min(360px,calc(100vh-32px))] max-w-[min(340px,calc(100vw-32px))] flex-col overflow-hidden rounded-[5px] border border-[var(--border-1)] bg-[var(--surface-2)] p-1 shadow-[0_8px_30px_rgb(0_0_0/12%)]'
            onCloseAutoFocus={(event) => {
              event.preventDefault()
              const textarea = textareaRef.current
              if (!textarea) return
              if (pendingCursorRef.current !== null) {
                textarea.setSelectionRange(pendingCursorRef.current, pendingCursorRef.current)
                pendingCursorRef.current = null
              }
              textarea.focus()
            }}
          >
            <div className='min-h-0 overflow-y-auto overscroll-none'>
              {filteredSkills.length ? filteredSkills.map((skill, index) => {
                const active = index === activeIndex
                return (
                  <button
                    key={skill.id}
                    type='button'
                    role='menuitem'
                    data-filtered-idx={index}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => select(skill)}
                    className={cn(
                      'relative flex w-full min-w-0 cursor-pointer select-none items-center gap-2 rounded-[5px] px-2 py-1.5 text-left text-[12px] text-[var(--text-body)] outline-none transition-colors',
                      active && 'bg-[var(--surface-hover)]',
                    )}
                  >
                    <Sparkles className='size-[14px] shrink-0 text-[var(--text-icon)]' />
                    <span className='min-w-0 truncate'>{skill.display_name}</span>
                    <span className='ml-auto max-w-[120px] truncate font-mono text-[10px] text-[var(--text-muted)]'>{skill.id}</span>
                  </button>
                )
              }) : (
                <div className='px-2 py-1.5 text-center text-[12px] text-[var(--text-tertiary)]'>No skills</div>
              )}
            </div>
          </DropdownMenuPrimitive.Content>
        </DropdownMenuPrimitive.Portal>
      </DropdownMenuPrimitive.Root>
    )
  }),
)
