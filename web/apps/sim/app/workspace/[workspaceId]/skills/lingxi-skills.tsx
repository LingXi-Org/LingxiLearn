'use client'

import { useEffect, useState } from 'react'
import { Button, Input } from '@sim/emcn'
import { api } from '@/lib/lingxi/api'
import type { NativeSkill } from '@/lib/lingxi/types'

export function LingxiSkills() {
  const [skills, setSkills] = useState<NativeSkill[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    void api.skills().then((result) => {
      if (active) setSkills(result.skills)
    }).catch(() => {
      if (active) setSkills([])
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => {
      active = false
    }
  }, [])

  const visibleSkills = skills.filter((skill) => {
    const needle = query.trim().toLowerCase()
    return !needle || `${skill.display_name} ${skill.description} ${skill.id}`.toLowerCase().includes(needle)
  })

  return (
    <div className='flex h-full min-h-0 flex-col bg-[var(--bg)]'>
      <header className='flex h-14 shrink-0 items-center justify-between border-b border-[var(--border)] px-6'>
        <div>
          <h1 className='text-[15px] font-medium text-[var(--text-primary)]'>Skills</h1>
          <p className='mt-0.5 text-[12px] text-[var(--text-muted)]'>在输入框中使用 / 调用学习能力</p>
        </div>
        <Button type='button' variant='outline' size='sm' onClick={() => window.alert('未接入：Skill 创建功能尚未连接')}>
          新建 Skill
        </Button>
      </header>
      <div className='min-h-0 flex-1 overflow-y-auto p-6'>
        <div className='mx-auto max-w-[860px]'>
          <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder='搜索 Skills…' />
          {loading ? (
            <p className='py-10 text-center text-[13px] text-[var(--text-muted)]'>正在加载…</p>
          ) : visibleSkills.length === 0 ? (
            <div className='mt-4 rounded-[12px] border border-dashed border-[var(--border)] p-8 text-center text-[13px] text-[var(--text-muted)]'>
              {skills.length === 0 ? '暂无可用 Skill' : '没有匹配的 Skill'}
            </div>
          ) : (
            <div className='mt-4 grid gap-3 sm:grid-cols-2'>
              {visibleSkills.map((skill) => (
                <article key={skill.id} className='rounded-[12px] border border-[var(--border)] bg-[var(--surface-2)] p-4'>
                  <div className='flex items-start justify-between gap-3'>
                    <div className='min-w-0'>
                      <h2 className='truncate text-[14px] font-medium text-[var(--text-primary)]'>/{skill.id}</h2>
                      <p className='mt-1 text-[13px] text-[var(--text-secondary)]'>{skill.display_name}</p>
                    </div>
                    <span className='rounded-full bg-[var(--surface-3)] px-2 py-1 text-[10px] text-[var(--text-muted)]'>已接入</span>
                  </div>
                  <p className='mt-3 line-clamp-3 text-[12px] leading-5 text-[var(--text-muted)]'>{skill.description}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
