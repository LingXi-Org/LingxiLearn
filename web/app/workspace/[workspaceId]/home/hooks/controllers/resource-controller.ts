import type { MothershipResource } from '@/lib/copilot/resources/types'
import type { AgentTaskSnapshot } from '@/lib/lingxi/types'

function normalizeArtifactKind(artifact: string): string {
  if (artifact === 'lesson_intro') return 'lesson-intro'
  if (artifact === 'lecture_deck') return 'lecture-deck'
  return artifact
}

export function artifactResourceId(taskId: string, artifact: string): string {
  return `lingxi-artifact:${taskId}:${normalizeArtifactKind(artifact)}`
}

export function artifactResources(task: AgentTaskSnapshot | null): MothershipResource[] {
  if (!task) return []
  const entries: Array<{
    key: keyof AgentTaskSnapshot['artifacts']
    title: string
    path?: string
  }> = [
    { key: 'lesson_intro', title: '课程引入', path: task.artifacts.lesson_intro?.url },
    { key: 'lecture_deck', title: '交互式讲义', path: task.artifacts.lecture_deck?.url },
    { key: 'quiz', title: '知识检测' },
    { key: 'visual', title: '交互式可视化', path: task.artifacts.visual?.url },
  ]
  const graphResource: MothershipResource = {
    type: 'generic',
    id: `runtime-graph:${task.id}`,
    title: '实时运行图',
  }
  const unlocked = new Set(
    (task.delivery?.queue ?? [])
      .filter((item) => item.state === 'unlocked' || item.state === 'consumed')
      .map((item) => item.artifact)
  )
  const hasDeliveryGate = (task.delivery?.queue ?? []).length > 0
  const order = task.delivery?.order ?? []
  const resources = entries
    .filter(({ key }) => {
      const artifact = normalizeArtifactKind(key)
      return Boolean(task.artifacts[key]?.available) && (!hasDeliveryGate || unlocked.has(artifact))
    })
    .sort(
      (left, right) =>
        order.indexOf(normalizeArtifactKind(left.key)) -
        order.indexOf(normalizeArtifactKind(right.key))
    )
    .map(({ key, title, path }) => ({
      type: 'file' as const,
      id: artifactResourceId(task.id, key),
      title,
      path,
    }))
  return [graphResource, ...resources]
}
