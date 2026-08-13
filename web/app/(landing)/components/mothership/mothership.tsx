import type { ComponentType, ReactNode } from 'react'
import {
  IsoBuildIllustration,
  IsoIngestIllustration,
  IsoIntegrateIllustration,
  IsoMonitorIllustration,
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
    word: '集成',
    Mark: IsoIntegrateIllustration,
    size: 180,
    definition: (
      <>
        Sim 目录中的 1,000+ 个集成，
        <br />
        让智能体连接并操作你的工具。
      </>
    ),
  },
  {
    word: '上下文',
    Mark: IsoIngestIllustration,
    size: 170,
    definition: '将数据以语义方式存储在 Sim 中，作为智能体推理所需的记忆。',
  },
  {
    word: '构建',
    Mark: IsoBuildIllustration,
    size: 176,
    definition: '在可视化构建器中编排智能体逻辑，也可以直接向 Sim 描述需求。',
  },
  {
    word: '监控',
    Mark: IsoMonitorIllustration,
    size: 174,
    definition: '深入查看 Sim 中的每次运行：实时追踪、日志和实际成本。',
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
        <span className='block text-[var(--text-primary)]'>
          AI 智能体所需的一切，集中于一个工作空间。
        </span>
        <span className='block text-[var(--text-body)]'>构建、运行并监控每一个智能体。</span>
      </h2>

      <ul className='mt-16 grid grid-cols-4 gap-8 max-sm:mt-8 max-sm:grid-cols-1 max-sm:gap-10 max-lg:mt-12 max-lg:grid-cols-2 max-lg:gap-x-8 max-lg:gap-y-12'>
        {AREAS.map(({ word, Mark, size, definition }) => (
          <li key={word} className='flex flex-col gap-[22px]'>
            <div className='flex size-[148px] items-center justify-center'>
              <Mark size={size} />
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
