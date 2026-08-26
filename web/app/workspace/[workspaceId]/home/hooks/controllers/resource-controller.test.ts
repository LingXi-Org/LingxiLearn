import { describe, expect, it } from 'vitest'
import type { AgentTaskSnapshot } from '@/lib/lingxi/types'
import {
  artifactResourceId,
  artifactResources,
  persistedTaskResources,
} from './resource-controller'

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

  it('merges sanitized persisted resources without duplicating projected artifacts', () => {
    const task = {
      id: 'task-1',
      resources: [
        { type: 'file', id: '', title: 'Broken' },
        { type: 'browser', id: 'browser-tab:a', title: 'A' },
        { type: 'browser', id: 'browser-tab:b', title: 'B' },
        {
          type: 'file',
          id: 'lingxi-artifact:task-1:lesson-intro',
          title: 'Stored duplicate',
        },
        { type: 'table', id: 'table-1', title: 'Scores' },
      ],
      artifacts: {
        lesson_intro: { available: true, url: '/intro' },
        lecture_deck: { available: false },
        quiz: { available: false },
        visual: { available: false },
      },
      delivery: { order: ['lesson-intro'], queue: [], cursor: 0 },
    } as AgentTaskSnapshot

    expect(persistedTaskResources(task)).toEqual([
      { type: 'browser', id: 'browser-session', title: 'Browser' },
      {
        type: 'file',
        id: 'lingxi-artifact:task-1:lesson-intro',
        title: 'Stored duplicate',
      },
      { type: 'table', id: 'table-1', title: 'Scores' },
    ])
    expect(artifactResources(task)).toEqual([
      { type: 'generic', id: 'runtime-graph:task-1', title: '实时运行图' },
      {
        type: 'file',
        id: 'lingxi-artifact:task-1:lesson-intro',
        title: '课程引入',
        path: '/intro',
      },
      { type: 'browser', id: 'browser-session', title: 'Browser' },
      { type: 'table', id: 'table-1', title: 'Scores' },
    ])
  })
})
