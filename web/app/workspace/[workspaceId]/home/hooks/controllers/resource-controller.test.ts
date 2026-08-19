import { describe, expect, it } from 'vitest'
import type { AgentTaskSnapshot } from '@/lib/lingxi/types'
import { artifactResourceId, artifactResources } from './resource-controller'

describe('artifact resource projection', () => {
  it('uses canonical artifact identity and respects delivery gates', () => {
    const task = {
      id: 'task-1',
      artifacts: {
        lesson_intro: { available: true, url: '/intro' },
        lecture_deck: { available: true, url: '/deck' },
        quiz: { available: false },
        visual: { available: false, url: '' },
      },
      delivery: {
        order: ['lesson-intro', 'lecture-deck'],
        queue: [
          { artifact: 'lesson-intro', task_key: 'intro', state: 'unlocked' },
          { artifact: 'lecture-deck', task_key: 'deck', state: 'queued' },
        ],
        cursor: 0,
      },
    } as AgentTaskSnapshot
    expect(artifactResourceId(task.id, 'lesson_intro')).toBe(
      'lingxi-artifact:task-1:lesson-intro'
    )
    expect(artifactResources(task).map((resource) => resource.id)).toEqual([
      'runtime-graph:task-1',
      'lingxi-artifact:task-1:lesson-intro',
    ])
  })
})
