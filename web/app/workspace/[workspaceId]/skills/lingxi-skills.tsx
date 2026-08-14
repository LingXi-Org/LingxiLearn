'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/lingxi/api'
import type { NativeSkill } from '@/lib/lingxi/types'

export function LingxiSkills() {
  const [skills, setSkills] = useState<NativeSkill[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<NativeSkill | null>(null)
  const [draft, setDraft] = useState({ name: '', description: '', content: '' })

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

  const reload = () => void api.skills().then((result) => setSkills(result.skills)).catch(() => undefined)
  const openEditor = (skill?: NativeSkill) => {
    setEditor(skill || { id: '', display_name: '', description: '', version: '1.0.0', license: '', compatibility: '', content: '', source: 'personal', is_system: false })
    setDraft({ name: skill?.name || skill?.display_name || '', description: skill?.description || '', content: skill?.content || '' })
  }
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!draft.name.trim() || !editor || editor.is_system) return
    if (editor.id) await api.updateSkill(editor.id, draft)
    else await api.createSkill(draft)
    setEditor(null)
    reload()
  }

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
        <button type='button' className='rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-[12px] text-[var(--text-primary)]' onClick={() => openEditor()}>新建 Skill</button>
      </header>
      <div className='min-h-0 flex-1 overflow-y-auto p-6'>
        <div className='mx-auto max-w-[860px]'>
          <input className='w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[12px] text-[var(--text-primary)]' value={query} onChange={(event) => setQuery(event.target.value)} placeholder='搜索 Skills…' />
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
                    {skill.is_system ? <span className='rounded-full bg-[var(--surface-3)] px-2 py-1 text-[10px] text-[var(--text-muted)]'>系统只读</span> : <div className='flex gap-2'><button type='button' className='text-[11px] text-[var(--text-secondary)] hover:underline' onClick={() => openEditor(skill)}>编辑</button><button type='button' className='text-[11px] text-red-500 hover:underline' onClick={() => void api.deleteSkill(skill.id).then(reload)}>删除</button></div>}
                  </div>
                  <p className='mt-3 line-clamp-3 text-[12px] leading-5 text-[var(--text-muted)]'>{skill.description}</p>
                </article>
              ))}
            </div>
          )}
          {editor && <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4'><form onSubmit={(event) => void save(event)} className='w-full max-w-[560px] space-y-3 rounded-[12px] border border-[var(--border)] bg-[var(--surface-1)] p-5 shadow-xl'><h2 className='text-[14px] font-medium text-[var(--text-primary)]'>{editor.id ? '编辑个人 Skill' : '新建个人 Skill'}</h2><input className='w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[12px] text-[var(--text-primary)]' value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder='名称' /><input className='w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-[12px] text-[var(--text-primary)]' value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} placeholder='描述' /><textarea className='min-h-[180px] w-full rounded-[7px] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 font-mono text-[12px] text-[var(--text-primary)]' value={draft.content} onChange={(event) => setDraft({ ...draft, content: event.target.value })} placeholder='Skill 内容' /><div className='flex justify-end gap-2'><button type='button' className='rounded-[7px] px-3 py-1.5 text-[12px] text-[var(--text-secondary)]' onClick={() => setEditor(null)}>取消</button><button type='submit' className='rounded-[7px] bg-[var(--text-primary)] px-3 py-1.5 text-[12px] text-[var(--text-inverse)]'>保存</button></div></form></div>}
        </div>
      </div>
    </div>
  )
}
