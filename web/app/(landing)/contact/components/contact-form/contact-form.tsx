'use client'

import { useState } from 'react'
import { Button } from '@/components/ui-kit'

const TOPICS = ['产品咨询', '课程合作', '技术支持', '其他']

export function ContactForm() {
  const [submitted, setSubmitted] = useState(false)

  if (submitted) {
    return (
      <div className='flex flex-col items-center px-4 py-12 text-center'>
        <div className='flex size-12 items-center justify-center rounded-full bg-[var(--brand-accent)]/10 text-[var(--brand-accent)]'>
          ✓
        </div>
        <h2 className='mt-5 text-[var(--text-primary)] text-xl'>信息已准备好</h2>
        <p className='mt-2 max-w-sm text-[var(--text-muted)] text-sm leading-6'>
          我们会通过你留下的邮箱与你联系。
        </p>
        <button
          type='button'
          onClick={() => setSubmitted(false)}
          className='mt-5 text-[var(--text-primary)] text-sm underline underline-offset-2'
        >
          再提交一份
        </button>
      </div>
    )
  }

  return (
    <form
      className='flex flex-col gap-4'
      onSubmit={(event) => {
        event.preventDefault()
        setSubmitted(true)
      }}
    >
      <h2 className='text-[var(--text-primary)] text-xl'>联系我们</h2>
      <p className='text-[var(--text-muted)] text-sm'>留下你的问题，我们会尽快回复。</p>
      <label className='flex flex-col gap-2 text-[var(--text-muted)] text-sm'>
        姓名
        <input
          required
          name='name'
          className='rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-[var(--text-body)] outline-none focus:border-[var(--text-primary)]'
        />
      </label>
      <label className='flex flex-col gap-2 text-[var(--text-muted)] text-sm'>
        邮箱
        <input
          required
          type='email'
          name='email'
          className='rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-[var(--text-body)] outline-none focus:border-[var(--text-primary)]'
        />
      </label>
      <label className='flex flex-col gap-2 text-[var(--text-muted)] text-sm'>
        主题
        <select
          required
          name='topic'
          defaultValue=''
          className='rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-[var(--text-body)] outline-none focus:border-[var(--text-primary)]'
        >
          <option value='' disabled>
            请选择
          </option>
          {TOPICS.map((topic) => (
            <option key={topic}>{topic}</option>
          ))}
        </select>
      </label>
      <label className='flex flex-col gap-2 text-[var(--text-muted)] text-sm'>
        留言
        <textarea
          required
          name='message'
          rows={5}
          className='resize-y rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-[var(--text-body)] outline-none focus:border-[var(--text-primary)]'
        />
      </label>
      <Button type='submit' variant='primary'>
        发送留言
      </Button>
    </form>
  )
}
