import type { ComponentType, ReactNode } from 'react'
import {
  IsoBuildIllustration,
  IsoIngestIllustration,
  IsoIntegrateIllustration,
} from '@/app/(landing)/components/mothership/components/iso-marks'

/**
 * Landing Sim section - the high-level "how Sim works" overview that sets up the
 * {@link Features} deep-dive. A two-line heading frames Sim as one workspace for
 * the whole platform; below, four columns call out its main areas (Integrate ·
 * Context · Build · Monitor), each paired with an abstract circle "goo"
 * mark and a one-line definition. These are the same four areas Features then
 * shows in real product UI, framed here in fewer words, from the "what it is"
 * angle, so the overview and the deep-dive don't repeat each other.
 *
 * The marks are the only client islands in this section: interactive brand
 * glyphs (subtle hover breathe/rotate); the section itself stays server-rendered.
 *
 * Inter-section spacing is owned by the `<main>` flex `gap` in `landing.tsx`;
 * this section carries no vertical padding. Horizontal padding (`px-20`) matches
 * the sections above, and the section is capped at the shared `max-w-[1460px]`.
 */

type GooMark = ComponentType<{ size?: number; className?: string }>

interface Area {
  word: string
  /** Abstract circle goo-mark paired with the area. */
  Mark: GooMark
  /**
   * Per-mark render size, tuned so the collection reads as one optical weight.
   * The marks have different shape ratios (a full cube vs a flat lattice), so a
   * uniform size makes some look bigger; these equalize their visual footprint.
   */
  size: number
  definition: ReactNode
}

const AREAS: Area[] = [
  {
    word: '可视化',
    Mark: IsoIntegrateIllustration,
    size: 180,
    definition: (
      <>
        将抽象知识转化为交互式课件、图解与练习，
        <br />
        让知识被看见、被理解、被掌握。
      </>
    ),
  },
  {
    word: '理解',
    Mark: IsoIngestIllustration,
    size: 170,
    definition: '所有工作以知识状态、学习目标与掌握状态为纲，形成个性化学习上下文。',
  },
  {
    word: '协作',
    Mark: IsoBuildIllustration,
    size: 176,
    definition: '多个专业 Agent 基于 Skill 自动组合，并行完成讲解、练习与反馈任务。',
  },
  {
    word: '成长',
    Mark: IsoIngestIllustration,
    size: 174,
    definition: '持续分析学习过程，根据反馈动态调整教学策略。',
  },
]

export function Mothership() {
  return (
    <section
      id='mothership'
      aria-labelledby='mothership-heading'
      className='mx-auto w-full max-w-[1460px] px-20 max-sm:px-5 max-lg:px-8'
    >
      <h2
        id='mothership-heading'
        className='max-w-[1200px] text-balance text-[28px] leading-[1.2] max-sm:text-[22px]'
      >
        <span className='block text-[var(--text-primary)]'>一个全闭环的 AI 学习工作空间</span>
        <span className='block text-[var(--text-body)]'>
          让多智能体理解学习目标、协同完成任务，并实时反馈每一步学习进展。
        </span>
      </h2>

      <ul className='mt-16 grid grid-cols-4 gap-8 max-sm:mt-8 max-sm:grid-cols-1 max-sm:gap-10 max-lg:mt-12 max-lg:grid-cols-2 max-lg:gap-x-8 max-lg:gap-y-12'>
        {AREAS.map(({ word, Mark, size, definition }) => (
          <li key={word} className='flex flex-col gap-[22px]'>
            <div
              data-export-widget='true'
              data-export-title={word}
              className='flex size-[148px] items-center justify-center'
            >
              <Mark size={size} className='translate-x-3 max-sm:translate-x-2' />
            </div>
            <div className='flex flex-col gap-2'>
              <h3 className='text-[var(--text-primary)] text-lg'>{word}</h3>
              <p className='max-w-[250px] text-pretty text-[var(--text-body)] text-sm leading-[1.5]'>
                {definition}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
