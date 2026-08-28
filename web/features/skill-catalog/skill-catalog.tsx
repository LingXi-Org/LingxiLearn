'use client'

import { useCallback, useEffect, useId, useState } from 'react'
import type { Skill } from '@/entities/skill/model'
import { skillApi } from '@/shared/api/client'
import { EmptyState, ErrorState, LoadingState } from '@/shared/ui/async-state'

export function SkillCatalog() {
  const [skills, setSkills] = useState<Skill[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const nameId = useId()
  const descriptionId = useId()
  const contentId = useId()

  const load = useCallback(async () => {
    try {
      const response = await skillApi.list()
      setSkills(response.skills)
      setError(null)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load skills')
    }
  }, [])

  useEffect(() => void load(), [load])

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setCreating(true)
    try {
      await skillApi.create({
        name: String(form.get('name') ?? ''),
        description: String(form.get('description') ?? ''),
        content: String(form.get('content') ?? ''),
      })
      event.currentTarget.reset()
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to create skill')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className='split-layout'>
      <form className='prompt-card sticky-card' onSubmit={create}>
        <span className='eyebrow'>Personal skill</span>
        <h1>Teach Lingxi a method.</h1>
        <label htmlFor={nameId}>Name</label>
        <input id={nameId} name='name' required />
        <label htmlFor={descriptionId}>Description</label>
        <input id={descriptionId} name='description' required />
        <label htmlFor={contentId}>Instructions</label>
        <textarea id={contentId} name='content' rows={8} required />
        <button className='button primary' disabled={creating} type='submit'>
          {creating ? 'Saving…' : 'Create skill'}
        </button>
      </form>
      <div className='stack-md'>
        {error && <ErrorState message={error} />}
        {skills === null ? (
          <LoadingState />
        ) : skills.length === 0 ? (
          <EmptyState
            title='No skills available'
            description='Create a reusable learning method.'
          />
        ) : (
          skills.map((skill) => (
            <article className='data-card wide' key={skill.id}>
              <div className='card-heading'>
                <span className='file-mark'>{skill.source}</span>
                <span>v{skill.version}</span>
              </div>
              <h2>{skill.display_name}</h2>
              <p>{skill.description}</p>
              <div className='card-actions'>
                {!skill.is_system && (
                  <button
                    className='danger-link'
                    type='button'
                    onClick={() => void skillApi.remove(skill.id).then(load)}
                  >
                    Delete
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  )
}
