'use client'

import type { ReactNode } from 'react'
import { useQueryStates } from 'nuqs'
import { DEMO_HREF, SIGNUP_HREF } from '@/app/(landing)/constants'
import {
  PricingCard,
  type PricingCardCta,
  type PricingCardSection,
} from '@/app/(landing)/pricing/components/pricing-card'
import { pricingParsers, pricingUrlKeys } from '@/app/(landing)/pricing/search-params'

const ANNUAL_DISCOUNT_RATE = 0.15
const PLANS = [
  { name: '开放版', monthly: 0, cta: '开始学习' },
  { name: '成长版', monthly: 19, cta: '开始学习' },
  { name: '团队版', monthly: 49, cta: '开始学习' },
  { name: '机构版', monthly: null, cta: '联系团队' },
] as const

const FEATURE_SECTIONS: PricingCardSection[] = [
  {
    key: 'learning',
    title: '学习能力',
    rows: [
      { label: '课程引入与讲义', value: true },
      { label: '知识检测', value: true },
      { label: '知识图谱', value: true },
      { label: '可视化讲解', value: true },
    ],
  },
  {
    key: 'support',
    title: '服务支持',
    rows: [
      { label: '个人学习记录', value: true },
      { label: '任务历史', value: '保留 30 天' },
      { label: '团队协作', value: false },
    ],
  },
]

function sectionsForPlan(index: number): PricingCardSection[] {
  return FEATURE_SECTIONS.map((section) => ({
    ...section,
    rows: section.rows.map((row) => ({
      ...row,
      value:
        index === 0 && row.label === '任务历史'
          ? '保留 7 天'
          : index < 3 || row.label !== '团队协作'
            ? row.value
            : false,
    })),
  }))
}

function ctaFor(index: number): PricingCardCta {
  return {
    label: PLANS[index].cta,
    variant: index === 3 ? 'primary' : 'border-shadow',
    href: index === 3 ? DEMO_HREF : SIGNUP_HREF,
  }
}

export interface PricingPlansProps {
  heading: ReactNode
}

export function PricingPlans({ heading }: PricingPlansProps) {
  const [{ billing }, setParams] = useQueryStates(pricingParsers, pricingUrlKeys)
  const isAnnual = billing === 'annual'
  const discountPct = Math.round(ANNUAL_DISCOUNT_RATE * 100)

  return (
    <>
      <div className='flex flex-col items-center gap-4'>
        {heading}
        <div className='flex items-center gap-1 rounded-lg border border-[var(--border-1)] bg-[var(--surface-2)] p-1 text-xs'>
          {(['monthly', 'annual'] as const).map((period) => (
            <button
              key={period}
              type='button'
              className={`rounded-md px-3 py-1.5 ${billing === period ? 'bg-[var(--text-primary)] text-[var(--text-inverse)]' : 'text-[var(--text-muted)]'}`}
              onClick={() => void setParams({ billing: period })}
            >
              {period === 'annual' ? `按年付（省 ${discountPct}%）` : '按月付'}
            </button>
          ))}
        </div>
      </div>
      <div className='grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4'>
        {PLANS.map((plan, index) => {
          const monthly = plan.monthly
          const price =
            monthly === null
              ? '定制'
              : `$${isAnnual ? Math.round(monthly * (1 - ANNUAL_DISCOUNT_RATE)) : monthly}`
          return (
            <PricingCard
              key={plan.name}
              name={plan.name}
              price={price}
              priceSubtext={
                monthly === null
                  ? '为学校和团队设计'
                  : monthly === 0
                    ? '免费开始'
                    : isAnnual
                      ? '每人/月，按年计费'
                      : '每人/月，按月计费'
              }
              discountLabel={isAnnual && monthly ? `${discountPct}% off` : undefined}
              cta={ctaFor(index)}
              sections={sectionsForPlan(index)}
            />
          )
        })}
      </div>
    </>
  )
}
